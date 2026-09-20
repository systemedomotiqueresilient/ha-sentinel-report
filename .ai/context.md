# Contexte IA — Sentinel Report

## Ce que fait ce projet

Sentinel Report est un custom_component Home Assistant qui génère un rapport
texte unifié (`/share/sentinel_report.txt`) en agrégeant les données de
surveillance de **Sentinel** (GuiPoM) et les issues de réparation de
**Spook** (frenck).

**Principe fondamental :** lecture seule sur les dépendances — le code de
Sentinel et de Spook n'est jamais modifié.

## Architecture (v0.6.1)

Un seul `custom_components/sentinel_report/` avec collecteurs internes :

```
sentinel_report/
├── collectors/
│   ├── sentinel.py   ← lit hass.data["sentinel"] + StabilityWatcher
│   └── spook.py      ← lit issue_registry filtré sur "spook"
├── __init__.py       ← orchestrateur + services + notifications
├── config_flow.py    ← UI config + validation
├── const.py          ← toutes les constantes (VERSION, DATA_KEY_*, CONF_*, etc.)
├── reporter.py       ← generate_report() → (str, bool, bool)
├── sensor.py         ← sensor.sentinel_report_problems
├── services.yaml
├── strings.json
└── translations/fr.json + en.json
```

## Fichiers clés

| Fichier | Rôle |
|---------|------|
| `collectors/sentinel.py` | Lit Sentinel, StabilityWatcher, filtre transitoires/exclus |
| `collectors/spook.py` | Lit issue_registry Spook, parse placeholders |
| `__init__.py` | async_setup_entry, _do_generate, notifications |
| `reporter.py` | Fonction pure génération rapport + purge historique |
| `const.py` | Point de vérité unique : VERSION, DATA_KEY_*, CONF_*, ALERT_* |
| `config_flow.py` | Validation chemin + délai stabilité (60→3600s) + companion app |

## Clés hass.data

| Clé | Type | Contenu |
|-----|------|---------|
| `DATA_KEY_SENTINEL` | `list[dict]` | Items unhealthy Sentinel |
| `DATA_KEY_SPOOK` | `list[dict] \| None` | Issues Spook (None si absent) |
| `DATA_KEY_STABILITY` | `dict[str, dict]` | Méta stabilité par item_id |
| `DATA_KEY_RESOLVED` | `list[dict]` | Incidents résolus — vidé après generate |

## Règles absolues pour l'IA

1. **Ne jamais modifier** `hass.data["sentinel"]` ni le code de GuiPoM
2. **Ne jamais modifier** le code de frenck/spook
3. Tout accès Sentinel passe par `hass.data["sentinel"]` uniquement
4. Tout accès Spook passe par `homeassistant.helpers.issue_registry`
5. `reporter.py` doit rester une fonction pure sans dépendance HA
6. **Toujours mettre à jour `const.py` ET `VERSION` ensemble** lors d'un
   changement de version — ne jamais oublier l'un ou l'autre
7. Les collecteurs (`collectors/`) ne doivent jamais appeler `_do_generate`
   directement — ils utilisent le `generate_callback` passé en paramètre
8. `DATA_KEY_RESOLVED` est vidé (`pop`) après chaque `_do_generate` —
   ne jamais l'accumuler

## Compatibilité Spook

- v5.1.0 : ajout `areas`, `resources`, `triggers`, `conditions`, `dead_entities`,
  `stale_access_tokens`, `orphaned_statistics`
- v5.3.0 : suppression `dead_entities`, `stale_access_tokens`, `orphaned_statistics`
  (retirés de Spook) — notre code reste compatible sans modification

## StabilityWatcher (v0.6.1)

- Seuil minimum : `STABILITY_MIN_CYCLES = 2` cycles pour déclencher la logique
- Timer : `stability_delay` secondes (60 → 3600, configurable)
- Résultat `resolved` : alimente `DATA_KEY_RESOLVED`, génère rapport avec section
  `INCIDENTS RÉSOLUS`, alert_type = `on_resolved`
- Résultat `restart_failed` : enrichit l'item dans `DATA_KEY_STABILITY`,
  alert_type = `on_restart_fail`
- `DATA_KEY_RESOLVED` est consommé et vidé à chaque `_do_generate`

## Types d'alertes companion app

| Constante | Déclencheur |
|-----------|-------------|
| `ALERT_ON_REPORT` | Chaque nouveau rapport écrit |
| `ALERT_ON_PROBLEMS` | Rapport avec problèmes |
| `ALERT_ON_RESTART_FAIL` | Timer expiré, item toujours en erreur |
| `ALERT_ON_RESOLVED` | Timer expiré, item revenu à la normale |

## Stack technique

- Python 3.12
- Home Assistant OS 2024.1+
- Lint : ruff
- Tests : pytest + pytest-asyncio + pytest-cov
- CI : Gitea Actions + GitHub Actions (5 jobs : lint, tests, versions, yaml, translations)
