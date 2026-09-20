# Guide d'installation détaillé

## Prérequis

| Composant | Version minimale | Obligatoire |
|-----------|-----------------|-------------|
| Home Assistant OS | 2024.1 | Oui |
| [Sentinel (GuiPoM)](https://github.com/GuiPoM/ha-sentinel) | 0.7.x | Oui |
| [Spook (frenck)](https://github.com/frenck/spook) | 5.x | Non |

## Installation manuelle

### 1. Copier le dossier

Depuis ce dépôt, copier **un seul dossier** dans `/config/custom_components/` :

```
/config/custom_components/
└── sentinel_report/
    ├── collectors/
    │   ├── sentinel.py
    │   └── spook.py
    ├── __init__.py
    ├── config_flow.py
    ├── const.py
    ├── manifest.json
    ├── reporter.py
    ├── sensor.py
    ├── services.yaml
    ├── strings.json
    └── translations/
        ├── fr.json
        └── en.json
```

Via SSH :

```bash
cp -r /chemin/vers/custom_components/sentinel_report /config/custom_components/
```

### 2. Redémarrer Home Assistant

### 3. Configurer via l'interface

Aller dans **Paramètres → Appareils et services → Ajouter une intégration → Sentinel Report**

Renseigner :
- **Dossier de destination** : `/share` (ou tout autre chemin absolu)
- **Nom du fichier** : `sentinel_report.txt`
- **Délai de stabilité** : 60 secondes minimum
- **Smartphone administrateur** : choisir parmi les `notify.mobile_app_*` disponibles
- Les autres options selon tes préférences

Le dossier sera automatiquement ajouté à `allowlist_external_dirs`.

> **Note** : plus besoin de configurer `configuration.yaml` — tout se fait via l'interface.
> Le fallback yaml reste supporté pour compatibilité.

### 4. Vérifier les logs

```
Paramètres → Système → Journaux → filtrer "sentinel_report"
```

Les lignes attendues au démarrage :

```
INFO  collecteur sentinel : initialisé (stability_delay=60s).
INFO  collecteur spook    : initialisé.
INFO  Sentinel Report 0.6.1 initialisé (config flow) — rapport : /share/sentinel_report.txt
INFO  Sentinel Report écrit dans /share/sentinel_report.txt
```

## Vérifier le rapport

Le fichier `/share/sentinel_report.txt` est accessible depuis :

- L'add-on **File editor** → `/share/sentinel_report.txt`
- Le partage réseau Samba de HA → `\\homeassistant\share\`
- SSH : `cat /share/sentinel_report.txt`

## Déclencher manuellement

**Outils développeur → Actions :**

```yaml
action: sentinel_report.generate
```

**Purge manuelle de l'historique :**

```yaml
action: sentinel_report.purge_history
```

**Via une automatisation :**

```yaml
automation:
  alias: "Rapport Sentinel — toutes les heures"
  trigger:
    - platform: time_pattern
      hours: "/1"
  action:
    - action: sentinel_report.generate
```

## Désinstallation

1. Supprimer la config entry dans **Paramètres → Appareils et services**
   (bouton ⋮ → Supprimer)
2. Supprimer le dossier `/config/custom_components/sentinel_report/`
3. Redémarrer Home Assistant

## Migration depuis v0.5.0

Si tu avais les anciens composants séparés :

1. Supprimer les config entries `sentinel_report_sentinel` et `sentinel_report_spook`
   depuis **Paramètres → Appareils et services**
2. Supprimer les dossiers `/config/custom_components/sentinel_report_sentinel/`
   et `/config/custom_components/sentinel_report_spook/`
3. Copier le nouveau dossier `sentinel_report/` complet
4. Redémarrer Home Assistant
