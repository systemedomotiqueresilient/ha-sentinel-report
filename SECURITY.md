# Politique de sécurité

## Versions supportées

| Version | Supportée          |
|---------|--------------------|
| 0.6.x   | :white_check_mark: |
| < 0.6.0 | :x:                |

## Signaler une vulnérabilité

**Ne pas ouvrir une Issue publique pour un problème de sécurité.**

Sentinel Report s'exécute localement sur ton instance Home Assistant et n'expose
aucun service réseau. Les risques sont limités mais réels (lecture de `hass.data`,
écriture dans `/share/`).

Pour signaler une vulnérabilité :

1. Utiliser les [Security Advisories](https://github.com/systemedomotiqueresilient/ha-sentinel-report/security/advisories/new)
   de GitHub (onglet Security → Report a vulnerability)
2. Décrire le vecteur d'attaque et l'impact potentiel
3. Laisser un délai raisonnable (14 jours) avant toute divulgation publique

Une réponse sera apportée dans les 72 heures.
