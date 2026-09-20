# Guide de contribution

Merci de ton intérêt pour Sentinel Report !

## Prérequis

- Home Assistant en cours de fonctionnement avec Sentinel installé
- Python 3.12+
- Git

## Environnement de développement

1. Forker le dépôt sur GitHub et cloner ton fork localement
2. Copier le dossier `custom_components/sentinel_report/` dans
   `/config/custom_components/` de Home Assistant
3. Redémarrer Home Assistant et vérifier les logs (`sentinel_report`)

## Règles de contribution

- **Ne pas modifier** le code de GuiPoM/ha-sentinel — Sentinel Report est
  conçu pour lire ses données en lecture seule
- Respecter l'architecture collecteurs internes (`collectors/sentinel.py`,
  `collectors/spook.py`, `collectors/ha_repairs.py`)
- Tout nouveau collecteur doit être un module dans `collectors/` avec son
  propre `async_setup(hass)` et sa clé `DATA_KEY_*` dans `const.py`
- Les changements de l'API interne de Sentinel (constantes, clés `hass.data`)
  doivent être documentés dans `CHANGELOG.md`
- Toujours mettre à jour `const.py` ET `VERSION` ensemble

## Soumettre une Pull Request

1. Créer une branche depuis `main` : `git checkout -b feat/ma-fonctionnalite`
2. Coder et tester sur une instance HA réelle
3. Mettre à jour `CHANGELOG.md` dans la section `[Unreleased]`
4. Ouvrir une Pull Request via
   https://github.com/systemedomotiqueresilient/ha-sentinel-report/compare

## Signaler un bug

Utiliser le template **Bug Report** dans les Issues en joignant
les logs HA filtrés sur `sentinel_report`.

## Proposer une fonctionnalité

Utiliser le template **Feature Request** dans les Issues.
