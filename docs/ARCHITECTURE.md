# Architecture — Sentinel Report

## Principe de conception

Sentinel Report suit le principe de **composition sans couplage** :
les collecteurs lisent leurs sources en lecture seule et ne modifient
jamais le code de Sentinel ou Spook. Tout est regroupé dans un seul
`custom_component` — une seule vignette dans HA.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Home Assistant Core                         │
│                                                                 │
│  ┌──────────────┐    ┌────────────────────────┐                 │
│  │   sentinel   │    │   issue_registry (HA)  │                 │
│  │  (GuiPoM)    │    │   domaine: "spook"     │                 │
│  └──────┬───────┘    └───────────┬────────────┘                 │
│         │ lecture seule          │ lecture seule                │
│         ▼                        ▼                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              custom_components/sentinel_report/          │   │
│  │                                                          │   │
│  │  collectors/sentinel.py   collectors/spook.py            │   │
│  │  ┌──────────────────┐    ┌──────────────────┐            │   │
│  │  │ StabilityWatcher │    │  _collect_issues │            │   │
│  │  │ _collect_items() │    │  _build_label()  │            │   │
│  │  └────────┬─────────┘    └────────┬─────────┘            │   │
│  │           │                       │                      │   │
│  │  hass.data[DATA_KEY_SENTINEL]  hass.data[DATA_KEY_SPOOK] │   │
│  │  hass.data[DATA_KEY_STABILITY] hass.data[DATA_KEY_RESOLVED]  │   │
│  │           │                       │                      │   │
│  │           └──────────┬────────────┘                      │   │
│  │                      ▼                                   │   │
│  │              __init__.py (_do_generate)                  │   │
│  │              reporter.py (generate_report)               │   │
│  │              sensor.py   (sensor HA)                     │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                       │
└─────────────────────────┼───────────────────────────────────────┘
                          │ écriture disque
                          ▼
               /share/sentinel_report.txt
               /share/sentinel_report_history/
```

## Modules

### `__init__.py` — Orchestrateur

- Configure les collecteurs au démarrage (`async_setup_entry`)
- Enregistre les services `generate` et `purge_history`
- Déclenche `_do_generate` au boot (délai 5s) et via le service
- Gère les notifications HA persistantes et companion app
- Détecte Spook via `hass.config.components` / `config_entries`

### `collectors/sentinel.py` — Collecteur Sentinel

- Lit `hass.data["sentinel"]` en lecture seule
- Filtre les états transitoires (`not_loaded`, `setup_in_progress`)
- Exclut Sentinel Report de ses propres rapports
- S'abonne au dispatcher `sentinel_update` pour les mises à jour temps réel
- **`StabilityWatcher`** : détecte les cycles d'instabilité, déclenche
  la génération automatique après expiration du timer de stabilité
- Enrichit les items avec les métadonnées de stabilité (cycles, durée)

### `collectors/spook.py` — Collecteur Spook

- Lit `homeassistant.helpers.issue_registry` filtré sur `domain == "spook"`
- Parse les `translation_placeholders` pour construire des labels lisibles
- Compatible Spook 5.x (nouveaux types : `dead_entities`, `stale_access_tokens`,
  `automation_unknown_trigger_references`, etc.)
- Écoute `repairs_issue_registry_updated` pour les mises à jour temps réel
- Collecte différée au `homeassistant_started` (le registry se peuple après le boot)

### `reporter.py` — Générateur de rapport

- Fonction pure : `generate_report(...) → (str, bool, bool)`
- Sections : `SENTINEL PROBLEMS`, `SPOOK REPAIRS`, `INCIDENTS RÉSOLUS`
- Enrichissement `SENTINEL PROBLEMS` avec mention "N'a pas redémarré"
- Testable unitairement sans instance HA

### `sensor.py` — Sensor HA

- `sensor.sentinel_report_problems` : nombre total de problèmes
- Attributs : `sentinel_errors`, `sentinel_warnings`, `spook_issues`,
  `last_generated`, `report_path`, `version`
- Mis à jour via dispatcher `sentinel_report_report_updated`

### `config_flow.py` — Configuration UI

- Config flow initial + options flow
- Validation : chemin absolu, nom de fichier, délai stabilité (60 → 3600s)
- Enregistrement automatique dans `allowlist_external_dirs`
- Menu déroulant `notify.mobile_app_*` pour le smartphone administrateur

## Flux de données

```
homeassistant_started + 5s
        │
        └─▶ _do_generate()
                ├─▶ hass.data[DATA_KEY_SENTINEL]  (collecté au boot)
                ├─▶ hass.data[DATA_KEY_SPOOK]     (collecté après 5s)
                ├─▶ hass.data[DATA_KEY_RESOLVED]  (incidents résolus en attente)
                ├─▶ reporter.generate_report(...)
                ├─▶ reporter.write_report(latest)
                ├─▶ reporter.write_history(horodaté)
                ├─▶ reporter.purge_history()
                ├─▶ async_dispatcher_send(SIGNAL_REPORT_UPDATED)
                ├─▶ persistent_notification (si configuré)
                └─▶ notify.mobile_app_* (si configuré)

sentinel_update (dispatcher GuiPoM)
        └─▶ collectors/sentinel._refresh()
        └─▶ StabilityWatcher.on_item_update()
                └─▶ (si timer expiré + cycles ≥ 2) → _do_generate(alert_type=...)

repairs_issue_registry_updated (event HA natif)
        └─▶ collectors/spook._refresh()

service sentinel_report.generate
        └─▶ _do_generate()

service sentinel_report.purge_history
        └─▶ reporter.purge_history()
```

## Clés `hass.data`

Toutes définies dans `const.py` — point de vérité unique.

| Clé | Type | Contenu |
|-----|------|---------|
| `DATA_KEY_SENTINEL` | `list[dict]` | Items unhealthy Sentinel |
| `DATA_KEY_SPOOK` | `list[dict] \| None` | Issues Spook (None si absent) |
| `DATA_KEY_STABILITY` | `dict[str, dict]` | Méta stabilité par item_id |
| `DATA_KEY_RESOLVED` | `list[dict]` | Incidents résolus en attente (vidé après generate) |
