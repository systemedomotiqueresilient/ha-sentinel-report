# Changelog

Toutes les modifications notables de ce projet sont documentées ici.
Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet respecte le [Versioning Sémantique](https://semver.org/lang/fr/).

---

## [Unreleased]

---

## [0.6.2] — 2026-09-07

### Added
- **Collecteur `collectors/ha_repairs.py`** : lit toutes les issues du repair
  registry HA natif (deprecated warnings, configurations obsolètes, migrations
  en attente) en excluant le domaine `spook` (géré par son propre collecteur)
- **Section `--- HA REPAIRS ---`** dans le rapport avec affichage de la version
  de rupture (`⚠️  Cassant dans HA x.y`) quand disponible
- **Option `include_ha_repairs`** dans le config flow (activée par défaut)
- **Alerte companion app `on_ha_repair`** : notification push quand des HA Repairs
  sont détectés
- `DATA_KEY_HA_REPAIRS` dans `const.py`
- `HA_REPAIRS_EXCLUDED_DOMAINS` : liste des domaines exclus du collecteur
  (actuellement `{"spook"}`)

### Changed
- `generate_report()` accepte maintenant `ha_repairs` comme 3ème paramètre
  (signature : `sentinel_items, spook_issues, ha_repairs, resolved_incidents, ...`)
- `_do_generate()` passe `ha_repairs` à `generate_report()` et intègre le
  compteur dans le sensor et les notifications
- `_extract_conf()` : typage encore plus défensif avec `or DEFAULT_*` pour
  éviter les `None` venant des selectors HA
- `_get_defaults_v062()` : injection des défauts de migration depuis v0.6.1
- `COMPANION_ALERT_OPTIONS` étendu avec `on_ha_repair`
- Traductions fr/en/strings.json : nouveau champ `include_ha_repairs` et
  nouvelle option selector `on_ha_repair`

---

## [0.6.1] — 2026-09-01

### Added
- **StabilityWatcher** dans `collectors/sentinel.py` : détecte les cycles
  d'instabilité (plantage/restart répétés) et déclenche automatiquement
  la génération du rapport après stabilisation
- **Délai de stabilité** configurable dans le config flow (60 → 3600 secondes,
  défaut 60s) avec validation bloquante si < 60s
- **Section `INCIDENTS RÉSOLUS`** dans le rapport : affichée uniquement dans
  le rapport généré à la résolution, disparaît au prochain generate manuel.
  Contient : nom, cycles d'instabilité, durée totale, horodatage d'origine
- **Enrichissement `SENTINEL PROBLEMS`** : mention "N'a pas redémarré après
  X échec(s) sur Y min Z sec" si toujours en erreur à expiration du timer
- **Génération automatique** déclenchée par le StabilityWatcher (en plus du
  démarrage et du service manuel)
- **Notifications companion app** : nouveau champ "Smartphone administrateur"
  (menu déroulant `notify.mobile_app_*`) et choix multiple des types d'alertes :
  - À chaque nouveau rapport
  - Si le rapport contient des problèmes
  - Échec de restart (timer expiré, toujours en erreur)
  - Résolution d'instabilité
- Nouvelles clés `hass.data` : `DATA_KEY_STABILITY`, `DATA_KEY_RESOLVED`
- Nouvelles constantes : `CONF_STABILITY_DELAY`, `CONF_COMPANION_DEVICE`,
  `CONF_COMPANION_ALERTS`, `COMPANION_ALERT_OPTIONS`, `STABILITY_MIN_CYCLES`

### Changed
- `generate_report()` retourne maintenant un tuple `(str, bool, bool)` :
  `(content, has_problems, has_resolved)`
- `collector_sentinel.async_setup()` accepte maintenant `stability_delay`
  et `generate_callback` en paramètres
- `_make_generate_callback()` crée le callback passé au StabilityWatcher
- L'archivage horodaté est déclenché aussi sur `has_resolved` (pas seulement
  `has_problems`)
- Traductions fr/en/strings.json : 5 nouveaux champs + section selector
  `companion_alerts`

---

## [0.6.0] — 2026-08-31

### Added
- Collecteurs intégrés dans `sentinel_report/collectors/` — une seule vignette
  dans Paramètres → Appareils et services (plus de `sentinel_report_sentinel`
  et `sentinel_report_spook` visibles indépendamment)
- Détection automatique de Spook via `_is_spook_available()` — le collecteur
  Spook est initialisé si et seulement si Spook est chargé
- `manifest.json` simplifié : `dependencies: ["sentinel"]`, `after_dependencies: ["spook"]`

### Changed
- Code des collecteurs déplacé de `custom_components/sentinel_report_sentinel/` et
  `custom_components/sentinel_report_spook/` vers
  `custom_components/sentinel_report/collectors/sentinel.py` et `collectors/spook.py`
- Tests mis à jour pour importer depuis les nouveaux chemins internes
- `_flatten_placeholder` filtre maintenant les domaines HA seuls (mqtt, tuya…)
  qui apparaîssaient entre les entity_id dans Spook 5.1.0

### Migration depuis v0.5.0
1. Supprimer les dossiers `custom_components/sentinel_report_sentinel/` et
   `custom_components/sentinel_report_spook/` de ton instance HA
2. Supprimer leurs config entries depuis Paramètres → Appareils et services
   (bouton ⋮ → Supprimer) avant de redémarrer
3. Copier le nouveau `custom_components/sentinel_report/` complet
4. Redémarrer Home Assistant

### Deprecated
- `custom_components/sentinel_report_sentinel/` — conservé dans le repo
  pour référence mais plus nécessaire à l'installation
- `custom_components/sentinel_report_spook/` — idem

---

## [0.5.0] — 2026-08-30

### Added
- Purge automatique de l'historique à chaque génération de rapport
  - Mode `keep_files` : conserver les N derniers fichiers (défaut: 30)
  - Mode `keep_days` : conserver les fichiers des X derniers jours (défaut: 30)
  - Mode `disabled` : pas de purge
- Service `sentinel_report.purge_history` pour une purge manuelle immédiate
- Configuration via le config flow UI et l'options flow (3 nouveaux champs)
- Configuration via `configuration.yaml` (fallback) : `purge_mode`, `purge_keep_files`, `purge_keep_days`
- 18 tests unitaires couvrant tous les cas de purge (`tests/test_purge.py`)
- Compatibilité Spook 5.1.0 : `_build_label` étendu avec les nouveaux placeholders
  (`areas`, `resources`, `triggers`, `conditions`, `integration`, `token`, `owner`, `last_active`)

### Changed
- `services.yaml` : documentation du service `generate` mise à jour + ajout de `purge_history`
- `translations/fr.json` et `en.json` : 3 nouvelles clés pour les options de purge

---

## [0.4.0] — 2026-08-29

### Added
- Tests d'intégration sur le config flow : validation de chemin, schéma voluptuous,
  seuils de notification, valeurs par défaut (`tests/test_config_flow.py`)
- Tests unitaires des collecteurs avec mocks HA : filtrage des états transitoires,
  exclusion des domaines, formatage des items, normalisation de sévérité Spook,
  aplatissement des placeholders, collecte d'issues (`tests/test_collectors.py`)
- Tests unitaires des constantes de filtrage (`tests/test_sentinel_filter.py`)
- CI : couverture de code via `pytest-cov` avec seuil minimum à 60%
- CI : job `translations` vérifiant la cohérence des clés entre `fr.json` et `en.json`
- `pyproject.toml` : configuration `pytest-asyncio` et `coverage`

### Changed
- `requirements_dev.txt` : ajout de `pytest-asyncio`, `pytest-cov`, `homeassistant`
- CI Gitea et GitHub : 5 jobs indépendants (lint, tests+coverage, versions, yaml, translations)
- Compatibilité Spook 5.1.0 : `_build_label` étendu avec les nouveaux types de placeholders
  (`areas`, `resources`, `triggers`, `conditions`, `integration`, `token`, `owner`, `last_active`)
  pour les 23 nouveaux repairs (dead entities, missing resources, area refs, trigger/condition refs,
  stale access tokens, etc.) — aucune modification de l'API, rétrocompatible avec Spook 4.x

---

## [0.3.1] — 2026-08-27

### Added
- Création automatique des config entries de `sentinel_report_sentinel` et
  `sentinel_report_spook` au premier démarrage de `sentinel_report` — plus
  besoin de déclarer les collecteurs dans `configuration.yaml`
- Config flow minimal (sans formulaire) pour chaque collecteur, permettant
  la création programmatique par l'orchestrateur
- `sentinel_report_spook` resté optionnel : si Spook n'est pas installé,
  la création de sa config entry échoue silencieusement

### Changed
- `CONFIG_SCHEMA` supprimé des collecteurs — ils n'ont plus besoin
  d'être déclarés dans `configuration.yaml`
- `async_setup` remplacé par `async_setup_entry` dans les deux collecteurs
- `manifest.json` des collecteurs : `config_flow: true`

### Migration depuis v0.3.0
- Retirer les lignes `sentinel_report_sentinel:` et `sentinel_report_spook:`
  de `configuration.yaml` après mise à jour — elles ne sont plus nécessaires
- Les config entries seront créées automatiquement au redémarrage

---

## [0.3.0] — 2026-08-27

### Added
- Config flow UI — configuration depuis l'interface HA sans toucher à `configuration.yaml`
  (Paramètres → Appareils et services → Ajouter une intégration → Sentinel Report)
- Options flow — modification de la configuration après installation via le bouton Configurer
- Enregistrement automatique du dossier de rapport dans `allowlist_external_dirs` à
  l'installation et à chaque changement de chemin dans les options
- Notifications HA persistantes optionnelles (`persistent_notification`) en cas de problèmes,
  avec seuil configurable : erreurs uniquement ou tous les problèmes
- Support double mode : config flow (recommandé) + `configuration.yaml` (fallback)
- Traductions fr/en pour le config flow (`translations/fr.json`, `translations/en.json`)
- Rechargement automatique de l'integration quand les options changent
- Validation du chemin et du nom de fichier dans le config flow avec messages d'erreur
  explicites

### Changed
- `manifest.json` : `config_flow: true`
- `sensor.py` : supporte `async_setup_entry` (config flow) et `async_setup_platform`
  (yaml legacy) sans duplication de code
- `configuration.yaml` reste supporté en fallback pour compatibilité v0.1/v0.2

---

## [0.2.0] — 2026-08-26

### Added
- Sensor HA `sensor.sentinel_report_problems` exposant le nombre total de problèmes
  (Sentinel + Spook) avec attributs détaillés (`sentinel_errors`, `sentinel_warnings`,
  `spook_issues`, `last_generated`, `report_path`, `version`)
- Mise à jour du sensor via dispatcher interne après chaque génération de rapport
- Validation du chemin de rapport au démarrage — warning clair si le dossier
  n'est pas accessible en écriture
- Tests unitaires couvrant le flag `has_problems` (tuple retourné par `generate_report`)
- CI Gitea Actions divisée en 4 jobs indépendants : lint, tests, versions, yaml
- Validation YAML des fichiers de configuration dans la CI

---
## [0.1.1] — 2026-08-23

### Added
- Version affichée dans le header du rapport (`Version : x.y.z`)
- Archivage horodaté des rapports contenant des problèmes dans
  `/share/sentinel_report_history/sentinel_report_YYYY-MM-DD_HH-MM-SS.txt`
- Option `keep_history` dans `configuration.yaml` (défaut: `true`) pour
  activer/désactiver l'archivage — les rapports "all clear" ne sont pas archivés

### Fixed
- Import relatif entre custom_components remplacé par import absolu
  (`from custom_components.sentinel_report.const import ...`)
- `hass.async_create_task` appelé depuis un thread executor dans
  `sentinel_report_spook` — corrigé avec `@callback` dans l'event loop
- Exception dans le dispatcher `sentinel_update` — corrigé avec `@callback`
  et `async_dispatcher_connect` après `homeassistant_started`
- Placeholders Spook multi-lignes (listes markdown) aplatis en une seule ligne
- Sévérité Spook `[NONE]` normalisée en `[WARNING]`

---

## [0.1.0] — 2026-08-18

### Added
- Architecture initiale en trois custom_components indépendants :
  `sentinel_report` (orchestrateur), `sentinel_report_sentinel` (collecteur Sentinel),
  `sentinel_report_spook` (collecteur Spook)
- Génération du rapport texte `/share/sentinel_report.txt` au format Watchman
- Déclenchement automatique au démarrage de Home Assistant (`homeassistant_started`)
- Service `sentinel_report.generate` pour un déclenchement manuel
- Collecte en temps réel via le dispatcher `sentinel_update` de Sentinel
- Mise à jour automatique sur `repairs_issue_registry_updated` pour Spook
- Fonctionnement dégradé si Spook n'est pas installé (section omise, pas d'erreur)
- Configuration via `configuration.yaml` : chemin, nom de fichier, filtrage warnings

> Première version fonctionnelle — usage personnel, non encore publiée sur GitHub.
