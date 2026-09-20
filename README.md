# Sentinel Report

> Rapport de santé unifié pour Home Assistant — agrège **Sentinel** et **Spook**
> dans un fichier texte unique, sans modifier leur code source.

[![CI](https://github.com/systemedomotiqueresilient/ha-sentinel-report/actions/workflows/ci.yml/badge.svg)](https://github.com/systemedomotiqueresilient/ha-sentinel-report/actions)
[![Version](https://img.shields.io/badge/version-0.6.2-blue)](VERSION)
[![HA](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-brightgreen)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## Pourquoi ce projet ?

[Sentinel](https://github.com/GuiPoM/ha-sentinel) surveille la santé de tes
intégrations, appareils et add-ons. [Spook](https://github.com/frenck/spook)
détecte les références cassées dans tes automatisations. Les deux sont excellents,
mais leurs alertes restent dans l'interface HA.

**Sentinel Report** centralise tout dans un fichier texte consultable depuis
n'importe quel outil (Watchman, Grafana, cron, script shell…), au format proche
de [Watchman](https://github.com/dummylabs/thewatchman).

## Architecture

Un seul custom_component qui embarque ses collecteurs en interne :

```
custom_components/
└── sentinel_report/
    ├── collectors/
    │   ├── sentinel.py    ← lit Sentinel en lecture seule
    │   ├── spook.py       ← lit Spook en lecture seule (optionnel)
    │   └── ha_repairs.py  ← lit les HA Repairs natifs HA
    ├── __init__.py        ← orchestrateur + services
    ├── sensor.py          ← sensor HA
    ├── reporter.py        ← génération du fichier rapport
    └── config_flow.py     ← configuration UI
```

Sentinel et Spook ne sont jamais modifiés — lecture seule uniquement.

→ Voir [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) pour le détail complet.

## Fonctionnalités

- 📄 Rapport texte unifié Sentinel + Spook dans `/share/sentinel_report.txt`
- 🕒 Génération automatique au démarrage de HA + service manuel `sentinel_report.generate`
- 📦 Archivage horodaté des rapports contenant des problèmes (`sentinel_report_history/`)
- 🛡️ **HA Repairs** : détection des deprecated warnings natifs HA (cassants dans une future version)
- 🧹 Purge automatique de l'historique (N fichiers ou X jours) + service `sentinel_report.purge_history`
- 🔔 Notification HA persistante optionnelle en cas de problèmes détectés
- 📊 Sensor `sensor.sentinel_report_problems` pour les automatisations et dashboards
- 🖥️ Config flow UI — configuration depuis l'interface HA, une seule vignette
- 🔒 Enregistrement automatique dans `allowlist_external_dirs`
- ⚡ Mises à jour en temps réel via le dispatcher Sentinel et le repair registry HA
- 🔄 **StabilityWatcher** : détecte les cycles de plantage/restart et génère automatiquement
  un rapport après stabilisation, avec comptage des cycles et durée d'instabilité
- 📱 **Notifications companion app** : push sur le smartphone administrateur pour les
  échecs de restart, résolutions d'instabilité, nouveaux rapports

## Exemple de rapport

```
==========================================
  HA SENTINEL REPORT
  Version : 0.6.2
  Generated: 2026-08-31 07:30:00
==========================================

--- SENTINEL PROBLEMS (3) ---

  [INTEGRATIONS]
  [ERROR] Netatmo (netatmo) — setup_error since 2026-08-31 06:00:00
           → Reason: Token expired | Failures: 3
  [WARNING] Z-Wave JS (zwave_js) — setup_retry since 2026-08-31 07:01:00

  [DEVICES]
  [ERROR] Ampoule salon (hue) — unavailable since 2026-08-31 05:45:00

--- SPOOK REPAIRS (4) ---
  [WARNING] [lovelace_unknown_entity_references] — dashboard: Maison — entities: light.old_lamp
  [WARNING] [dead_entities] — integration: Tuya — entities: switch.old_device
  [WARNING] [automation_unknown_trigger_references] — automation: My Auto — triggers: device_tracker.left_home
  [WARNING] [unused_blueprints] — domain: automation — blueprint: Zone Notification

--- HA REPAIRS (3) ---
  [WARNING] [homeassistant/deprecated_trigger_any] — behavior: any
             → ⚠️  Cassant dans HA 2027.1
  [WARNING] [http/config_yaml_deprecated]
             → ⚠️  Cassant dans HA 2027.2
  [WARNING] [smtp/smtp_config_deprecation_warning]
             → ⚠️  Cassant dans HA 2027.1

--- INCIDENTS RÉSOLUS (1) ---
  [RESOLVED] Zigbee2MQTT Bridge
             → Stable depuis 2026-08-31 07:32:15 | 2 cycles d'instabilité sur 3 min 12 sec
             → Première défaillance : 2026-08-31 07:29:03

==========================================
  ✖ 2 sentinel errors, 1 sentinel warning, 4 spook issues, 1 incident résolu
==========================================
```

## Installation

### 1. Copier le dossier

Copier **un seul dossier** dans `/config/custom_components/` :

```
/config/custom_components/sentinel_report/
```

### 2. Redémarrer Home Assistant

### 3. Configurer via l'interface

**Paramètres → Appareils et services → Ajouter une intégration → Sentinel Report**

Renseigner le dossier de destination, le nom du fichier, et les options souhaitées.
Le dossier sera automatiquement ajouté à `allowlist_external_dirs`.
Les collecteurs Sentinel et Spook sont initialisés automatiquement.

→ Guide complet : [docs/SETUP.md](docs/SETUP.md)

## Options disponibles

| Option | Description | Défaut |
|--------|-------------|--------|
| Dossier de destination | Chemin absolu du rapport | `/share` |
| Nom du fichier | Nom du fichier rapport | `sentinel_report.txt` |
| Inclure les warnings | Warnings Sentinel dans le rapport | ✅ |
| Archiver les rapports | Copies horodatées si problèmes détectés | ✅ |
| HA Repairs | Inclure les deprecated warnings natifs HA | ✅ |
| Mode de purge | `disabled` / `keep_files` / `keep_days` | `keep_files` |
| Nombre de fichiers | Fichiers à conserver (mode `keep_files`) | `30` |
| Nombre de jours | Jours à conserver (mode `keep_days`) | `30` |
| Délai de stabilité | Secondes avant génération auto (60 → 3600) | `60` |
| Notifications HA | Notification persistante si problèmes | ❌ |
| Seuil HA | Erreurs uniquement / Tout | `errors_only` |
| Smartphone admin | Entité `notify.mobile_app_*` | aucun |
| Types d'alertes | Push sur : rapport / problèmes / restart fail / résolution | aucun |

## Déclenchement

**Au démarrage** : automatique, 5 secondes après `homeassistant_started`

**Manuellement** : service `sentinel_report.generate`

**Via automatisation** :
```yaml
automation:
  alias: "Rapport Sentinel — toutes les heures"
  trigger:
    - platform: time_pattern
      hours: "/1"
  action:
    - service: sentinel_report.generate
```

**Purge manuelle** : service `sentinel_report.purge_history`

## Sensor HA

Le sensor `sensor.sentinel_report_problems` expose le nombre total de problèmes :

| Attribut | Description |
|----------|-------------|
| `state` | Nombre total de problèmes |
| `sentinel_errors` | Erreurs Sentinel |
| `sentinel_warnings` | Warnings Sentinel |
| `spook_issues` | Issues Spook (si disponible) |
| `last_generated` | Date de la dernière génération |
| `report_path` | Chemin du fichier rapport |
| `version` | Version de Sentinel Report |

## Prérequis

| Composant | Version | Obligatoire |
|-----------|---------|-------------|
| Home Assistant OS | 2024.1+ | ✅ |
| [Sentinel (GuiPoM)](https://github.com/GuiPoM/ha-sentinel) | 0.7.x+ | ✅ |
| [Spook (frenck)](https://github.com/frenck/spook) | 5.x+ | ⬜ optionnel |

## Contribuer

Les contributions sont les bienvenues ! Voir [CONTRIBUTING.md](CONTRIBUTING.md).

Les collecteurs (`collectors/sentinel.py` et `collectors/spook.py`) lisent leurs
dépendances en lecture seule — le code de GuiPoM/ha-sentinel et de frenck/spook
ne doit jamais être modifié.

## Crédits

- [GuiPoM](https://github.com/GuiPoM) — ha-sentinel
- [frenck](https://github.com/frenck) — spook
- [dummylabs](https://github.com/dummylabs) — thewatchman (inspiration du format)

## Licence

[MIT](LICENSE)
