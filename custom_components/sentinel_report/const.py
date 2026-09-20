"""Constants partagées pour Sentinel Report."""
from __future__ import annotations

DOMAIN = "sentinel_report"
VERSION = "0.6.2"

# Clés hass.data
DATA_KEY_SENTINEL = "sentinel_report_sentinel_data"
DATA_KEY_SPOOK = "sentinel_report_spook_data"
DATA_KEY_HA_REPAIRS = "sentinel_report_ha_repairs_data"
DATA_KEY_STABILITY = "sentinel_report_stability_data"
DATA_KEY_RESOLVED = "sentinel_report_resolved_data"

# Chemins par défaut
DEFAULT_REPORT_PATH = "/share"
DEFAULT_REPORT_FILE = "sentinel_report.txt"
DEFAULT_HISTORY_DIR = "sentinel_report_history"

# Options config flow — rapport
CONF_REPORT_PATH = "report_path"
CONF_REPORT_FILE = "report_file"
CONF_INCLUDE_WARNINGS = "include_warnings"
CONF_KEEP_HISTORY = "keep_history"
CONF_INCLUDE_HA_REPAIRS = "include_ha_repairs"

# Options config flow — notifications HA persistantes
CONF_NOTIFY = "notify"
CONF_NOTIFY_THRESHOLD = "notify_threshold"  # "errors_only" | "all"

# Options config flow — purge historique
CONF_PURGE_MODE = "purge_mode"           # "disabled" | "keep_files" | "keep_days"
CONF_PURGE_KEEP_FILES = "purge_keep_files"
CONF_PURGE_KEEP_DAYS = "purge_keep_days"

# Options config flow — stabilité et temps réel
CONF_STABILITY_DELAY = "stability_delay"  # secondes (60 → 3600)

# Options config flow — companion app
CONF_COMPANION_DEVICE = "companion_device"   # entité notify.mobile_app_* ou ""
CONF_COMPANION_ALERTS = "companion_alerts"   # liste de types d'alertes

# Valeurs par défaut
DEFAULT_INCLUDE_WARNINGS = True
DEFAULT_KEEP_HISTORY = True
DEFAULT_INCLUDE_HA_REPAIRS = True
DEFAULT_NOTIFY = False
DEFAULT_NOTIFY_THRESHOLD = "errors_only"
DEFAULT_PURGE_MODE = "keep_files"
DEFAULT_PURGE_KEEP_FILES = 30
DEFAULT_PURGE_KEEP_DAYS = 30
DEFAULT_STABILITY_DELAY = 60
DEFAULT_COMPANION_DEVICE = ""
DEFAULT_COMPANION_ALERTS: list[str] = []

# Types d'alertes companion app
ALERT_ON_REPORT = "on_report"
ALERT_ON_PROBLEMS = "on_problems"
ALERT_ON_RESTART_FAIL = "on_restart_fail"
ALERT_ON_RESOLVED = "on_resolved"
ALERT_ON_HA_REPAIR = "on_ha_repair"

COMPANION_ALERT_OPTIONS = [
    ALERT_ON_REPORT,
    ALERT_ON_PROBLEMS,
    ALERT_ON_RESTART_FAIL,
    ALERT_ON_RESOLVED,
    ALERT_ON_HA_REPAIR,
]

# Domaines HA Core exclus des HA Repairs
# - spook    : géré par son propre collecteur
# - hacs     : restart_required une par composant — bruit
# - hassio   : issues Supervisor sans traduction utile — bruit
# - automation, script, lovelace, blueprint : déjà couverts par Spook
HA_REPAIRS_EXCLUDED_DOMAINS = {
    "spook",
    "hacs",
    "hassio",
    "automation",
    "script",
    "lovelace",
    "blueprint",
}

# Seuil minimum de cycles pour déclencher la logique d'instabilité
STABILITY_MIN_CYCLES = 2

# Titre de l'entrée config flow
CONF_ENTRY_TITLE = "Sentinel Report"
