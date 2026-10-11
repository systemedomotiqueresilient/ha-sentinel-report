"""Sentinel Report — orchestrateur principal.

v0.6.2 : ajout du collecteur HA Repairs (deprecated warnings natifs HA).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .collectors import ha_repairs as collector_ha_repairs
from .collectors import sentinel as collector_sentinel
from .collectors import spook as collector_spook
from .const import (
    ALERT_ON_HA_REPAIR,
    ALERT_ON_PROBLEMS,
    ALERT_ON_REPORT,
    ALERT_ON_RESOLVED,
    ALERT_ON_RESTART_FAIL,
    CONF_COMPANION_ALERTS,
    CONF_COMPANION_DEVICE,
    CONF_INCLUDE_HA_REPAIRS,
    CONF_INCLUDE_WARNINGS,
    CONF_KEEP_HISTORY,
    CONF_NOTIFY,
    CONF_NOTIFY_THRESHOLD,
    CONF_PURGE_KEEP_DAYS,
    CONF_PURGE_KEEP_FILES,
    CONF_PURGE_MODE,
    CONF_REPORT_FILE,
    CONF_REPORT_PATH,
    CONF_STABILITY_DELAY,
    DATA_KEY_HA_REPAIRS,
    DATA_KEY_RESOLVED,
    DATA_KEY_SENTINEL,
    DATA_KEY_SPOOK,
    DATA_KEY_STABILITY,
    DEFAULT_COMPANION_ALERTS,
    DEFAULT_COMPANION_DEVICE,
    DEFAULT_HISTORY_DIR,
    DEFAULT_INCLUDE_HA_REPAIRS,
    DEFAULT_INCLUDE_WARNINGS,
    DEFAULT_KEEP_HISTORY,
    DEFAULT_NOTIFY,
    DEFAULT_NOTIFY_THRESHOLD,
    DEFAULT_PURGE_KEEP_DAYS,
    DEFAULT_PURGE_KEEP_FILES,
    DEFAULT_PURGE_MODE,
    DEFAULT_REPORT_FILE,
    DEFAULT_REPORT_PATH,
    DEFAULT_STABILITY_DELAY,
    DOMAIN,
    VERSION,
)
from .reporter import generate_report, purge_history, write_history, write_report
from .sensor import SIGNAL_REPORT_UPDATED

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_REPORT_PATH, default=DEFAULT_REPORT_PATH): cv.string,
                vol.Optional(CONF_REPORT_FILE, default=DEFAULT_REPORT_FILE): cv.string,
                vol.Optional(CONF_INCLUDE_WARNINGS, default=DEFAULT_INCLUDE_WARNINGS): cv.boolean,
                vol.Optional(CONF_KEEP_HISTORY, default=DEFAULT_KEEP_HISTORY): cv.boolean,
                vol.Optional(CONF_INCLUDE_HA_REPAIRS, default=DEFAULT_INCLUDE_HA_REPAIRS): cv.boolean,
                vol.Optional(CONF_NOTIFY, default=DEFAULT_NOTIFY): cv.boolean,
                vol.Optional(CONF_NOTIFY_THRESHOLD, default=DEFAULT_NOTIFY_THRESHOLD): cv.string,
                vol.Optional(CONF_PURGE_MODE, default=DEFAULT_PURGE_MODE): cv.string,
                vol.Optional(CONF_PURGE_KEEP_FILES, default=DEFAULT_PURGE_KEEP_FILES): cv.positive_int,
                vol.Optional(CONF_PURGE_KEEP_DAYS, default=DEFAULT_PURGE_KEEP_DAYS): cv.positive_int,
                vol.Optional(CONF_STABILITY_DELAY, default=DEFAULT_STABILITY_DELAY): cv.positive_int,
                vol.Optional(CONF_COMPANION_DEVICE, default=DEFAULT_COMPANION_DEVICE): cv.string,
                vol.Optional(CONF_COMPANION_ALERTS, default=DEFAULT_COMPANION_ALERTS): cv.ensure_list,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def _validate_report_path(full_path: str) -> bool:
    directory = os.path.dirname(full_path)
    try:
        os.makedirs(directory, exist_ok=True)
        test_file = os.path.join(directory, ".sentinel_report_write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return True
    except OSError as exc:
        _LOGGER.error("Sentinel Report : dossier '%s' inaccessible : %s", directory, exc)
        return False


def _ensure_allowlist(hass: HomeAssistant, report_path: str) -> None:
    try:
        p = Path(report_path)
        if p not in hass.config.allowlist_external_dirs:
            hass.config.allowlist_external_dirs.add(p)
            _LOGGER.info("Sentinel Report : '%s' ajouté à allowlist_external_dirs", report_path)
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Sentinel Report : allowlist impossible : %s", exc)


def _is_spook_available(hass: HomeAssistant) -> bool:
    if hass.config_entries.async_entries("spook"):
        return True
    if "spook" in hass.data:
        return True
    return "spook" in hass.config.components


def _extract_conf(conf: dict) -> dict:
    """Extraire toutes les options avec typage strict."""
    return {
        "report_path":       str(conf.get(CONF_REPORT_PATH, DEFAULT_REPORT_PATH)),
        "report_file":       str(conf.get(CONF_REPORT_FILE, DEFAULT_REPORT_FILE)),
        "include_warnings":  bool(conf.get(CONF_INCLUDE_WARNINGS, DEFAULT_INCLUDE_WARNINGS)),
        "keep_history":      bool(conf.get(CONF_KEEP_HISTORY, DEFAULT_KEEP_HISTORY)),
        "include_ha_repairs":bool(conf.get(CONF_INCLUDE_HA_REPAIRS, DEFAULT_INCLUDE_HA_REPAIRS)),
        "notify":            bool(conf.get(CONF_NOTIFY, DEFAULT_NOTIFY)),
        "notify_threshold":  str(conf.get(CONF_NOTIFY_THRESHOLD, DEFAULT_NOTIFY_THRESHOLD)),
        "purge_mode":        str(conf.get(CONF_PURGE_MODE, DEFAULT_PURGE_MODE)),
        "purge_keep_files":  int(float(conf.get(CONF_PURGE_KEEP_FILES, DEFAULT_PURGE_KEEP_FILES) or DEFAULT_PURGE_KEEP_FILES)),
        "purge_keep_days":   int(float(conf.get(CONF_PURGE_KEEP_DAYS, DEFAULT_PURGE_KEEP_DAYS) or DEFAULT_PURGE_KEEP_DAYS)),
        "stability_delay":   int(float(conf.get(CONF_STABILITY_DELAY, DEFAULT_STABILITY_DELAY) or DEFAULT_STABILITY_DELAY)),
        "companion_device":  str(conf.get(CONF_COMPANION_DEVICE, DEFAULT_COMPANION_DEVICE)),
        "companion_alerts":  list(conf.get(CONF_COMPANION_ALERTS, DEFAULT_COMPANION_ALERTS) or []),
    }


def _get_defaults_v062() -> dict:
    """Défauts à injecter pour la migration depuis v0.6.1."""
    return {
        CONF_STABILITY_DELAY:   DEFAULT_STABILITY_DELAY,
        CONF_COMPANION_DEVICE:  DEFAULT_COMPANION_DEVICE,
        CONF_COMPANION_ALERTS:  list(DEFAULT_COMPANION_ALERTS),
        CONF_INCLUDE_HA_REPAIRS: DEFAULT_INCLUDE_HA_REPAIRS,
    }


# ── Setup yaml (fallback) ────────────────────────────────────────────────────

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    conf_raw = config.get(DOMAIN)
    if conf_raw is None:
        return True
    if hass.config_entries.async_entries(DOMAIN):
        return True

    opts = _extract_conf({**_get_defaults_v062(), **conf_raw})
    full_path = os.path.join(opts["report_path"], opts["report_file"])
    _ensure_allowlist(hass, opts["report_path"])
    await hass.async_add_executor_job(_validate_report_path, full_path)
    hass.data[DOMAIN] = {**opts, "full_path": full_path}

    hass.async_create_task(
        discovery.async_load_platform(hass, "sensor", DOMAIN, {}, config)
    )

    generate_cb = _make_generate_callback(hass, full_path, opts)
    _register_services(hass, full_path, opts, generate_cb)

    await collector_sentinel.async_setup(hass, opts["stability_delay"], generate_cb)
    if _is_spook_available(hass):
        await collector_spook.async_setup(hass)
    if opts["include_ha_repairs"]:
        await collector_ha_repairs.async_setup(hass)

    @callback
    def _on_started_yaml(_event) -> None:
        async def _delayed():
            await asyncio.sleep(10)
            await generate_cb()
        hass.async_create_task(_delayed())

    hass.bus.async_listen_once("homeassistant_started", _on_started_yaml)
    _LOGGER.info("Sentinel Report %s initialisé (yaml) — rapport : %s", VERSION, full_path)
    return True


# ── Setup config entry ───────────────────────────────────────────────────────

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    conf_raw = {**_get_defaults_v062(), **entry.data, **entry.options}
    opts = _extract_conf(conf_raw)
    full_path = os.path.join(opts["report_path"], opts["report_file"])

    _ensure_allowlist(hass, opts["report_path"])
    await hass.async_add_executor_job(_validate_report_path, full_path)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = {**opts, "full_path": full_path, "entry_id": entry.entry_id}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    generate_cb = _make_generate_callback(hass, full_path, opts)
    _register_services(hass, full_path, opts, generate_cb)

    await collector_sentinel.async_setup(hass, opts["stability_delay"], generate_cb)
    if _is_spook_available(hass):
        await collector_spook.async_setup(hass)
    if opts["include_ha_repairs"]:
        await collector_ha_repairs.async_setup(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    @callback
    def _on_started(_event) -> None:
        async def _delayed():
            await asyncio.sleep(10)
            await generate_cb()
        hass.async_create_task(_delayed())

    hass.bus.async_listen_once("homeassistant_started", _on_started)
    _LOGGER.info("Sentinel Report %s initialisé (config flow) — rapport : %s", VERSION, full_path)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for key in (DOMAIN, DATA_KEY_SENTINEL, DATA_KEY_SPOOK, DATA_KEY_HA_REPAIRS,
                    DATA_KEY_STABILITY, DATA_KEY_RESOLVED):
            hass.data.pop(key, None)
        for service in ("generate", "purge_history"):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _make_generate_callback(hass: HomeAssistant, full_path: str, opts: dict) -> Any:
    async def _generate_cb(alert_type: str | None = None, stability_context: dict | None = None) -> None:
        await _do_generate(hass, full_path, opts, alert_type, stability_context)
    return _generate_cb


def _register_services(hass: HomeAssistant, full_path: str, opts: dict, generate_cb: Any) -> None:
    if not hass.services.has_service(DOMAIN, "generate"):
        async def handle_generate(_call: ServiceCall) -> None:
            await generate_cb()
        hass.services.async_register(DOMAIN, "generate", handle_generate)

    if not hass.services.has_service(DOMAIN, "purge_history"):
        async def handle_purge(_call: ServiceCall) -> None:
            deleted = await hass.async_add_executor_job(
                purge_history, opts["report_path"], DEFAULT_HISTORY_DIR,
                opts["purge_mode"], opts["purge_keep_files"], opts["purge_keep_days"],
            )
            _LOGGER.info("Sentinel Report : purge manuelle — %d fichier(s) supprimé(s)", deleted)
        hass.services.async_register(DOMAIN, "purge_history", handle_purge)


async def _do_generate(
    hass: HomeAssistant,
    full_path: str,
    opts: dict,
    alert_type: str | None = None,
    stability_context: dict | None = None,
) -> None:
    generated_at = datetime.now()  # noqa: DTZ005
    include_warnings = opts["include_warnings"]

    sentinel_items: list = hass.data.get(DATA_KEY_SENTINEL) or []
    spook_issues: list | None = hass.data.get(DATA_KEY_SPOOK)
    ha_repairs: list | None = hass.data.get(DATA_KEY_HA_REPAIRS) if opts["include_ha_repairs"] else None
    spook_available = spook_issues is not None
    resolved_incidents: list = hass.data.pop(DATA_KEY_RESOLVED, [])

    content, has_problems, has_resolved = generate_report(
        sentinel_items, spook_issues, ha_repairs, resolved_incidents,
        include_warnings, generated_at,
    )

    try:
        await hass.async_add_executor_job(write_report, full_path, content)
    except OSError as exc:
        _LOGGER.error("Impossible d'écrire le rapport dans %s : %s", full_path, exc)
        return

    if opts["keep_history"] and (has_problems or has_resolved):
        try:
            await hass.async_add_executor_job(
                write_history, opts["report_path"], DEFAULT_HISTORY_DIR, content, generated_at,
            )
        except OSError as exc:
            _LOGGER.error("Impossible d'archiver le rapport : %s", exc)

    if opts["keep_history"] and opts["purge_mode"] != "disabled":
        try:
            _keep_files = int(float(opts["purge_keep_files"])) if opts["purge_keep_files"] is not None else DEFAULT_PURGE_KEEP_FILES
            _keep_days  = int(float(opts["purge_keep_days"]))  if opts["purge_keep_days"]  is not None else DEFAULT_PURGE_KEEP_DAYS
            await hass.async_add_executor_job(
                purge_history, opts["report_path"], DEFAULT_HISTORY_DIR,
                opts["purge_mode"], _keep_files, _keep_days,
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Sentinel Report : purge ignorée (%s : %s)", type(exc).__name__, exc)

    sentinel_errors   = sum(1 for i in sentinel_items if i.get("severity") == "error")
    sentinel_warnings = sum(1 for i in sentinel_items if i.get("severity") == "warning")
    if not include_warnings:
        sentinel_warnings = 0
    spook_count    = len(spook_issues) if spook_available else 0
    ha_repair_count = len(ha_repairs) if ha_repairs is not None else 0
    total = sentinel_errors + sentinel_warnings + spook_count + ha_repair_count

    async_dispatcher_send(
        hass, SIGNAL_REPORT_UPDATED,
        {
            "total":             total,
            "sentinel_errors":   sentinel_errors,
            "sentinel_warnings": sentinel_warnings,
            "spook_issues":      spook_count,
            "ha_repairs":        ha_repair_count,
            "spook_available":   spook_available,
            "last_generated":    generated_at.strftime("%Y-%m-%d %H:%M:%S"),
            "report_path":       full_path,
        },
    )

    if opts["notify"] and has_problems:
        should_notify = (
            opts["notify_threshold"] == "errors_only" and sentinel_errors > 0
            or opts["notify_threshold"] == "all" and total > 0
        )
        if should_notify:
            parts = []
            if sentinel_errors:
                parts.append(f"{sentinel_errors} erreur{'s' if sentinel_errors > 1 else ''} Sentinel")
            if sentinel_warnings and opts["notify_threshold"] == "all":
                parts.append(f"{sentinel_warnings} warning{'s' if sentinel_warnings > 1 else ''} Sentinel")
            if spook_count and opts["notify_threshold"] == "all":
                parts.append(f"{spook_count} issue{'s' if spook_count > 1 else ''} Spook")
            if ha_repair_count and opts["notify_threshold"] == "all":
                parts.append(f"{ha_repair_count} HA repair{'s' if ha_repair_count > 1 else ''}")

            await hass.services.async_call(
                "persistent_notification", "create",
                {
                    "title": "⚠️ Sentinel Report",
                    "message": (
                        f"Rapport généré le {generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"{', '.join(parts)}\n"
                        f"Rapport complet : {full_path}"
                    ),
                    "notification_id": "sentinel_report_alert",
                },
            )

    companion_device = opts.get("companion_device", "")
    companion_alerts = opts.get("companion_alerts", [])
    if companion_device and companion_alerts:
        await _send_companion_notification(
            hass, companion_device, companion_alerts,
            alert_type, stability_context,
            has_problems, has_resolved, total, ha_repair_count,
            generated_at, full_path,
        )


async def _send_companion_notification(
    hass: HomeAssistant,
    device: str,
    alerts: list[str],
    alert_type: str | None,
    stability_context: dict | None,
    has_problems: bool,
    has_resolved: bool,
    total: int,
    ha_repair_count: int,
    generated_at: datetime,
    full_path: str,
) -> None:
    service = device.replace("notify.", "") if device.startswith("notify.") else device
    should_notify = False
    title = "📊 Sentinel Report"
    message = ""

    if ALERT_ON_REPORT in alerts:
        should_notify = True
        ts = generated_at.strftime("%Y-%m-%d %H:%M:%S")
        message = f"Rapport généré le {ts}."
        if total > 0:
            message += f"\n{total} problème{'s' if total > 1 else ''} détecté{'s' if total > 1 else ''}."

    if ALERT_ON_PROBLEMS in alerts and has_problems and not message:
        should_notify = True
        message = f"{total} problème{'s' if total > 1 else ''} détecté{'s' if total > 1 else ''}."

    if ALERT_ON_RESTART_FAIL in alerts and alert_type == ALERT_ON_RESTART_FAIL and stability_context:
        should_notify = True
        title = "🔴 Sentinel Report — Échec de restart"
        name = stability_context.get("name", "?")
        cycles = stability_context.get("cycles", 0)
        duration = stability_context.get("duration", "")
        message = f"⚠️ {name} n'a pas redémarré après {cycles} échec{'s' if cycles > 1 else ''} sur {duration}."

    if ALERT_ON_RESOLVED in alerts and alert_type == ALERT_ON_RESOLVED and stability_context:
        should_notify = True
        title = "✅ Sentinel Report — Incident résolu"
        name = stability_context.get("name", "?")
        cycles = stability_context.get("cycles", 0)
        duration = stability_context.get("duration", "")
        message = f"✅ {name} revenu à la normale après {cycles} cycle{'s' if cycles > 1 else ''} sur {duration}."

    if ALERT_ON_HA_REPAIR in alerts and ha_repair_count > 0 and not message:
        should_notify = True
        title = "⚠️ Sentinel Report — HA Repairs"
        message = f"{ha_repair_count} deprecated warning{'s' if ha_repair_count > 1 else ''} détecté{'s' if ha_repair_count > 1 else ''}."

    if not should_notify or not message:  # noqa: SIM103
        return

    try:
        await hass.services.async_call(
            "notify", service,
            {
                "title": title,
                "message": message,
                "data": {"push": {"sound": "default"}, "tag": "sentinel_report"},
            },
        )
        _LOGGER.info("Sentinel Report : notification companion envoyée à '%s'", device)
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Sentinel Report : notification companion impossible : %s", exc)
