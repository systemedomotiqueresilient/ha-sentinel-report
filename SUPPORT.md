# Support

## Où chercher de l'aide ?

1. **README** — vérifier la section Installation et Configuration
2. **Logs Home Assistant** — filtrer sur `sentinel_report` dans
   `Paramètres → Système → Journaux`
3. **Issues GitHub** — chercher si le problème est déjà connu avant d'en ouvrir un

## Ouvrir une Issue

Utiliser le template **Bug Report** et joindre :

- La version de Sentinel Report (fichier `VERSION`)
- La version de Home Assistant
- La version de Sentinel (GuiPoM) et de Spook si utilisé
- Les logs HA filtrés sur `sentinel_report`, `sentinel_report_sentinel`,
  `sentinel_report_spook`
- Le contenu de ton `configuration.yaml` (sans informations sensibles)

## Ce projet ne supporte pas

- Les instances HA Core ou Container (non testé — contributions bienvenues)
- Les versions de HA antérieures à 2024.1
- Les modifications du code de GuiPoM/ha-sentinel
