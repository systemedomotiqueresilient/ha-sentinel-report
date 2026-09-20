# Roadmap

## v0.1.0 — MVP ✅

- [x] Architecture trois composants : orchestrateur + collecteur Sentinel + collecteur Spook
- [x] Génération du rapport texte dans `/share/sentinel_report.txt`
- [x] Déclenchement au démarrage (`homeassistant_started`)
- [x] Service `sentinel_report.generate`
- [x] Mise à jour en temps réel via dispatcher Sentinel
- [x] Fonctionnement dégradé sans Spook

## v0.1.1 — Corrections & polish ✅

- [x] Version affichée dans le header du rapport
- [x] Archivage horodaté des rapports avec problèmes (`sentinel_report_history/`)
- [x] Option `keep_history` pour activer/désactiver l'archivage
- [x] Fix import relatif entre custom_components
- [x] Fix async_create_task depuis mauvais thread
- [x] Placeholders Spook aplatis sur une seule ligne
- [x] Sévérité Spook normalisée

## v0.2.0 — Qualité & robustesse ✅

- [x] Tests unitaires sur `reporter.py`
- [x] CI Gitea Actions : lint, YAML, cohérence versions, pytest, coverage
- [x] Validation du chemin de rapport au démarrage
- [x] Sensor HA `sensor.sentinel_report_problems`
- [x] Mise à jour du sensor via dispatcher

## v0.3.0 — Expérience utilisateur ✅

- [x] Config flow UI
- [x] Options flow
- [x] Enregistrement automatique dans `allowlist_external_dirs`
- [x] Notification HA persistante optionnelle
- [x] Support double mode : config flow + `configuration.yaml` (fallback)
- [x] Traductions fr/en

## v0.3.1 — Architecture & corrections ✅

- [x] Collecteurs chargés via `dependencies` / `after_dependencies`
- [x] Config flow minimal sur les collecteurs
- [x] Filtrage des états transitoires (`not_loaded`, `setup_in_progress`)
- [x] Sentinel Report exclu de ses propres rapports
- [x] Fix thread safety
- [x] Collecte immédiate dans `async_setup_entry`

## v0.4.0 — Tests d'intégration & CI ✅

- [x] Tests sur le config flow, les collecteurs, les filtres
- [x] CI : coverage (60% minimum), cohérence traductions
- [x] `pytest-asyncio`, `pytest-cov`

## v0.5.0 — Gestion de l'historique ✅

- [x] Purge automatique : N fichiers ou X jours
- [x] Service `sentinel_report.purge_history`
- [x] Configuration dans le config flow
- [x] Traductions FR complètes des selectors
- [x] Compatibilité Spook 5.1.0

## v0.6.0 — UX intégration HA ✅

- [x] Vignette unique dans Paramètres → Appareils et services
- [x] Collecteurs intégrés dans `sentinel_report/collectors/`
- [x] Détection automatique de Spook via `hass.config.components`
- [x] `manifest.json` simplifié : `dependencies: ["sentinel"]`, `after_dependencies: ["spook"]`
- [x] Suppression des anciens `sentinel_report_sentinel` et `sentinel_report_spook`

## v0.6.1 — Temps réel & notifications avancées ✅

- [x] **StabilityWatcher** : détection des cycles de plantage/restart
- [x] Délai de stabilité configurable (60 → 3600s) avec validation bloquante
- [x] Génération automatique du rapport à l'expiration du timer
- [x] Section `INCIDENTS RÉSOLUS` dans le rapport (uniquement à la résolution)
- [x] Enrichissement `SENTINEL PROBLEMS` : "N'a pas redémarré après X échec(s)"
- [x] Notifications companion app : menu déroulant `notify.mobile_app_*`
- [x] Types d'alertes configurables : rapport / problèmes / restart fail / résolution
- [x] Tests unitaires StabilityWatcher + nouveaux cas reporter

## v0.6.2 — HA Repairs natifs ✅

- [x] Collecteur `collectors/ha_repairs.py` : lit les deprecated warnings natifs HA
- [x] Section `--- HA REPAIRS ---` dans le rapport avec version de rupture
- [x] Option `include_ha_repairs` dans le config flow (activée par défaut)
- [x] Alerte companion app `on_ha_repair`

## v1.0.0 — Publication HACS

- [ ] Icon et brand assets (logo Sentinel Report)
- [ ] Soumission au dépôt HACS default
- [ ] Documentation complète dans `/docs`
- [ ] Tests d'intégration sur HA OS, Supervised, Container

## vX.X — Personnalisation avancée (non planifiée)

- [ ] Template Jinja2 personnalisable pour le format du rapport
  *(à évaluer selon les retours de la communauté)*
- [ ] Plugin HACS pour des collecteurs tiers
