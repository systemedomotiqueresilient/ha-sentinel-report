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

## v0.7.0 — Contrat public Sentinel ✅

- [x] Collecteur Sentinel alimenté par l'événement public `sentinel_item_changed`
- [x] État initial via le service public `sentinel.check`
- [x] Repli "au mieux" sur `hass.data["sentinel"]` si `fire_events` est désactivé
- [x] Horodatages `since` convertis en heure locale
- [x] Désabonnement propre au rechargement de l'intégration

## v0.7.1 — Issues fantômes ✅

- [x] Les collecteurs Spook et HA Repairs ignorent les issues inactives (`active=False`)
  rechargées du stockage de HA au démarrage

## v0.7.2 — Rapport de démarrage & libellés ✅

- [x] Rapport complet 180 s après `homeassistant_started`, en plus du rapport rapide à 10 s
- [x] Libellé "⏳ en cours d'initialisation" au lieu de "✔ No issues" juste après le boot
- [x] Libellés Spook : tous les placeholders non vides sont affichés (ex: `empty_areas`)
- [x] HA Repairs : valeurs multi-lignes (exemples YAML) ramenées sur une ligne

## v0.7.3 — Installation & finitions (prochaine version)

- [ ] README : section Installation "HA friendly" (bouton My Home Assistant, étapes HACS
  dépliées, installation manuelle), dans le style de Sentinel
- [ ] Workflows : `actions/checkout` en version supérieure (avertissement Node.js)
- [ ] Manifest : clé `categories` (après vérification des valeurs autorisées)

## v1.0.0 — Publication HACS

- [x] Icon et brand assets (`brand/icon.png`, `icon@2x.png`)
- [x] CI hassfest + HACS au vert, release `v0.7.1` installée via HACS (dépôt personnalisé)
- [ ] Soumission au dépôt HACS default
- [ ] Documentation complète dans `/docs`
- [ ] Tests d'intégration sur HA OS, Supervised, Container

## vX.X — Personnalisation avancée (non planifiée)

- [ ] Template Jinja2 personnalisable pour le format du rapport
  *(à évaluer selon les retours de la communauté)*
- [ ] Plugin HACS pour des collecteurs tiers
