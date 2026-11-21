"""Tests de l'intégration du module commun admin_phone.py (0.7.3).

Le module est copié À L'IDENTIQUE depuis le dépôt ha-sdr : un test vérifie sa
version et son SHA-256. Les tests couvrent ensuite le capteur « Téléphone admin »,
la migration companion_device -> admin_notify_target, les formulaires et l'envoi
via async_notify_admin. Pas de fixture `hass` : des mocks, comme les autres tests.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.const import EntityCategory

from custom_components.sentinel_report import (
    _extract_conf,
    _send_companion_notification,
    admin_phone,
    async_migrate_entry,
)
from custom_components.sentinel_report.config_flow import (
    SentinelReportConfigFlow,
    SentinelReportOptionsFlow,
    _build_schema,
    _get_current,
    _validate_target,
)
from custom_components.sentinel_report.const import (
    ALERT_ON_REPORT,
    CONF_COMPANION_ALERTS,
    CONF_COMPANION_DEVICE,
    CONF_REPORT_FILE,
    CONF_REPORT_PATH,
    CONF_STABILITY_DELAY,
    CONFIG_MINOR_VERSION,
)
from custom_components.sentinel_report.sensor import AdminPhoneSensor

TARGET = admin_phone.CONF_ADMIN_NOTIFY_TARGET
PHONE = "notify.mobile_app_pixel_9"

# SHA-256 du admin_phone.py 1.2.0 publié dans ha-sdr (commit 77a8992).
REFERENCE_SHA256 = "1d720150ff1c709547018236afcb1c555e630c504be0c34b20fe0b79ed80545b"


def _entry(data=None, options=None, minor_version=1, version=1, entry_id="abc123"):
    return SimpleNamespace(
        entry_id=entry_id,
        version=version,
        minor_version=minor_version,
        data=dict(data or {}),
        options=dict(options or {}),
    )


def _hass_for_update():
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    return hass


# ── Module commun ────────────────────────────────────────────────────────────

def test_module_is_the_reference_copy():
    path = Path(admin_phone.__file__)
    assert admin_phone.MODULE_VERSION == "1.2.0"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == REFERENCE_SHA256


def test_sentinel_report_is_a_sibling_platform():
    assert "sentinel_report" in admin_phone.SIBLING_PLATFORMS


def test_entity_unique_id_convention():
    assert admin_phone.ADMIN_TARGET_SUFFIX == "_admin_notify_target"
    assert TARGET == "admin_notify_target"


# ── Capteur « Téléphone admin » ──────────────────────────────────────────────

def test_sensor_follows_the_convention():
    sensor = AdminPhoneSensor(_entry(data={TARGET: PHONE}, entry_id="e1"))
    assert sensor.unique_id == "e1_admin_notify_target"
    assert sensor.entity_category == EntityCategory.DIAGNOSTIC
    assert sensor.native_value == PHONE
    assert sensor.extra_state_attributes == {"notify_service": PHONE}
    assert sensor.translation_key == "admin_notify_target"


def test_sensor_without_target_is_none_not_a_string():
    for data in ({}, {TARGET: None}, {TARGET: ""}, {TARGET: "unknown"}):
        sensor = AdminPhoneSensor(_entry(data=data))
        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {"notify_service": None}


def test_sensor_accepts_a_notify_entity():
    sensor = AdminPhoneSensor(_entry(data={TARGET: "notify.pixel_9"}))
    assert sensor.native_value == "notify.pixel_9"


def test_sensor_ignores_an_invalid_value():
    sensor = AdminPhoneSensor(_entry(data={TARGET: "light.salon"}))
    assert sensor.native_value is None


# ── Migration 1.1 -> 1.2 ─────────────────────────────────────────────────────

async def test_migration_moves_companion_device_from_data():
    hass = _hass_for_update()
    entry = _entry(data={CONF_COMPANION_DEVICE: PHONE, CONF_REPORT_PATH: "/share"})
    assert await async_migrate_entry(hass, entry) is True
    kwargs = hass.config_entries.async_update_entry.call_args.kwargs
    assert kwargs["data"][TARGET] == PHONE
    assert CONF_COMPANION_DEVICE not in kwargs["data"]
    assert kwargs["data"][CONF_REPORT_PATH] == "/share"
    assert kwargs["minor_version"] == CONFIG_MINOR_VERSION


async def test_migration_options_value_wins_over_data():
    hass = _hass_for_update()
    entry = _entry(
        data={CONF_COMPANION_DEVICE: "notify.mobile_app_old"},
        options={CONF_COMPANION_DEVICE: PHONE, CONF_STABILITY_DELAY: 120},
    )
    await async_migrate_entry(hass, entry)
    kwargs = hass.config_entries.async_update_entry.call_args.kwargs
    assert kwargs["data"][TARGET] == PHONE
    assert CONF_COMPANION_DEVICE not in kwargs["data"]
    assert CONF_COMPANION_DEVICE not in kwargs["options"]
    assert kwargs["options"][CONF_STABILITY_DELAY] == 120


async def test_migration_keeps_other_options_and_alerts():
    hass = _hass_for_update()
    entry = _entry(
        data={CONF_COMPANION_ALERTS: [ALERT_ON_REPORT]},
        options={CONF_COMPANION_DEVICE: PHONE, CONF_COMPANION_ALERTS: ["on_problems"]},
    )
    await async_migrate_entry(hass, entry)
    kwargs = hass.config_entries.async_update_entry.call_args.kwargs
    assert kwargs["data"][CONF_COMPANION_ALERTS] == [ALERT_ON_REPORT]
    assert kwargs["options"][CONF_COMPANION_ALERTS] == ["on_problems"]


async def test_migration_without_phone_sets_none():
    hass = _hass_for_update()
    await async_migrate_entry(hass, _entry(data={CONF_COMPANION_DEVICE: ""}))
    assert hass.config_entries.async_update_entry.call_args.kwargs["data"][TARGET] is None
    hass = _hass_for_update()
    await async_migrate_entry(hass, _entry())
    assert hass.config_entries.async_update_entry.call_args.kwargs["data"][TARGET] is None


async def test_migration_is_skipped_when_already_current():
    hass = _hass_for_update()
    entry = _entry(data={TARGET: PHONE}, minor_version=CONFIG_MINOR_VERSION)
    assert await async_migrate_entry(hass, entry) is True
    hass.config_entries.async_update_entry.assert_not_called()


async def test_migration_refuses_a_newer_major_version():
    hass = _hass_for_update()
    assert await async_migrate_entry(hass, _entry(version=2)) is False
    hass.config_entries.async_update_entry.assert_not_called()


def test_config_flow_declares_minor_version():
    assert SentinelReportConfigFlow.MINOR_VERSION == CONFIG_MINOR_VERSION == 2


# ── Lecture de la configuration ──────────────────────────────────────────────

def test_extract_conf_reads_the_new_key():
    assert _extract_conf({TARGET: PHONE})["admin_notify_target"] == PHONE


def test_extract_conf_accepts_a_notify_entity():
    assert _extract_conf({TARGET: "notify.pixel_9"})["admin_notify_target"] == "notify.pixel_9"


def test_extract_conf_falls_back_on_the_yaml_companion_device():
    assert _extract_conf({CONF_COMPANION_DEVICE: PHONE})["admin_notify_target"] == PHONE


def test_extract_conf_new_key_wins_over_legacy():
    conf = {TARGET: PHONE, CONF_COMPANION_DEVICE: "notify.mobile_app_old"}
    assert _extract_conf(conf)["admin_notify_target"] == PHONE


def test_extract_conf_undefined_is_none():
    for conf in ({}, {TARGET: None}, {TARGET: ""}, {CONF_COMPANION_DEVICE: ""}):
        assert _extract_conf(conf)["admin_notify_target"] is None


def test_get_current_merges_data_and_options():
    entry = _entry(data={TARGET: PHONE}, options={CONF_STABILITY_DELAY: 90})
    current = _get_current(entry)
    assert current[TARGET] == PHONE
    assert current[CONF_STABILITY_DELAY] == 90


# ── Formulaires ──────────────────────────────────────────────────────────────

def test_validate_target():
    assert _validate_target(None) is None
    assert _validate_target("") is None
    assert _validate_target("   ") is None
    assert _validate_target(PHONE) is None
    assert _validate_target("notify.pixel_9") is None
    assert _validate_target("light.salon") == "invalid_target"
    assert _validate_target("unknown") == "invalid_target"
    assert _validate_target("notify.") == "invalid_target"


def _schema_key(schema, name):
    return next(k for k in schema.schema if str(k) == name)


def test_schema_has_the_optional_admin_field_without_hass():
    schema = _build_schema(None, {})
    key = _schema_key(schema, TARGET)
    assert key.description is None
    assert str(CONF_COMPANION_DEVICE) not in {str(k) for k in schema.schema}


def test_schema_prefills_the_current_value():
    schema = _build_schema(None, {TARGET: PHONE})
    assert _schema_key(schema, TARGET).description == {"suggested_value": PHONE}


def test_schema_prefills_from_a_sibling_integration():
    hass = MagicMock()
    with patch(
        "custom_components.sentinel_report.config_flow.suggest_admin_target",
        return_value=(PHONE, [PHONE, "notify.pixel_9"]),
    ) as suggest:
        schema = _build_schema(hass, {})
    suggest.assert_called_once_with(hass, None)
    assert _schema_key(schema, TARGET).description == {"suggested_value": PHONE}


def _options_flow(entry):
    flow = SentinelReportOptionsFlow()
    flow.hass = MagicMock()
    flow.hass.config_entries.async_update_entry = MagicMock()
    flow.hass.config.allowlist_external_dirs = set()
    return flow, patch.object(
        SentinelReportOptionsFlow, "config_entry", new_callable=PropertyMock, return_value=entry
    )


def _user_input(**extra):
    base = {CONF_REPORT_PATH: "/share", CONF_REPORT_FILE: "sentinel_report.txt",
            CONF_STABILITY_DELAY: 60}
    base.update(extra)
    return base


async def test_options_flow_writes_the_target_into_entry_data():
    entry = _entry(data={TARGET: None}, minor_version=2)
    flow, config_entry = _options_flow(entry)
    with config_entry, patch.object(flow, "async_create_entry", side_effect=lambda **kw: kw):
        result = await flow.async_step_init(_user_input(**{TARGET: PHONE}))
    update = flow.hass.config_entries.async_update_entry.call_args
    assert update.kwargs["data"][TARGET] == PHONE
    assert TARGET not in result["data"]
    assert result["data"][CONF_REPORT_PATH] == "/share"


async def test_options_flow_clearing_the_field_sets_none():
    entry = _entry(data={TARGET: PHONE}, minor_version=2)
    flow, config_entry = _options_flow(entry)
    with config_entry, patch.object(flow, "async_create_entry", side_effect=lambda **kw: kw):
        await flow.async_step_init(_user_input())
    update = flow.hass.config_entries.async_update_entry.call_args
    assert update.kwargs["data"][TARGET] is None


async def test_options_flow_unchanged_target_does_not_touch_entry_data():
    entry = _entry(data={TARGET: PHONE}, minor_version=2)
    flow, config_entry = _options_flow(entry)
    with config_entry, patch.object(flow, "async_create_entry", side_effect=lambda **kw: kw):
        await flow.async_step_init(_user_input(**{TARGET: PHONE}))
    flow.hass.config_entries.async_update_entry.assert_not_called()


async def test_options_flow_rejects_an_invalid_target():
    entry = _entry(data={TARGET: PHONE}, minor_version=2)
    flow, config_entry = _options_flow(entry)
    flow.async_show_form = MagicMock(side_effect=lambda **kw: kw)
    with config_entry:
        result = await flow.async_step_init(_user_input(**{TARGET: "light.salon"}))
    assert result["errors"] == {TARGET: "invalid_target"}
    flow.hass.config_entries.async_update_entry.assert_not_called()


async def test_config_flow_stores_the_target_in_data():
    flow = SentinelReportConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config.allowlist_external_dirs = set()
    flow._async_current_entries = MagicMock(return_value=[])
    with patch.object(flow, "async_create_entry", side_effect=lambda **kw: kw):
        result = await flow.async_step_user(_user_input(**{TARGET: " " + PHONE + " "}))
    assert result["data"][TARGET] == PHONE


async def test_config_flow_without_phone_stores_none():
    flow = SentinelReportConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config.allowlist_external_dirs = set()
    flow._async_current_entries = MagicMock(return_value=[])
    with patch.object(flow, "async_create_entry", side_effect=lambda **kw: kw):
        result = await flow.async_step_user(_user_input())
    assert result["data"][TARGET] is None


# ── Envoi par async_notify_admin ─────────────────────────────────────────────

_NOW = None


def _send(hass, target, alerts, alert_type=None, ctx=None, problems=0):
    from datetime import datetime
    return _send_companion_notification(
        hass, target, alerts, alert_type, ctx,
        problems > 0, False, problems, 0,
        datetime(2026, 11, 21, 12, 0, 0), "/share/sentinel_report.txt",
    )


async def test_send_uses_async_notify_admin_with_the_push_data():
    hass = MagicMock()
    with patch(
        "custom_components.sentinel_report.async_notify_admin", new=AsyncMock(return_value=True)
    ) as notify:
        await _send(hass, PHONE, [ALERT_ON_REPORT], problems=2)
    args = notify.call_args
    assert args.args[0] is hass
    assert args.args[1] == PHONE
    assert args.args[2] == "📊 Sentinel Report"
    assert "2 problèmes détectés" in args.args[3]
    assert args.kwargs["data"] == {"push": {"sound": "default"}, "tag": "sentinel_report"}


async def test_send_restart_fail_message():
    hass = MagicMock()
    ctx = {"name": "Zigbee2MQTT", "cycles": 3, "duration": "4 min"}
    with patch(
        "custom_components.sentinel_report.async_notify_admin", new=AsyncMock(return_value=True)
    ) as notify:
        await _send(hass, PHONE, ["on_restart_fail"], "on_restart_fail", ctx)
    assert notify.call_args.args[2] == "🔴 Sentinel Report — Échec de restart"
    assert "Zigbee2MQTT" in notify.call_args.args[3]


async def test_send_nothing_when_no_alert_matches():
    hass = MagicMock()
    with patch(
        "custom_components.sentinel_report.async_notify_admin", new=AsyncMock()
    ) as notify:
        await _send(hass, PHONE, ["on_problems"], problems=0)
    notify.assert_not_called()


async def test_send_to_a_notify_service_calls_the_service_with_data():
    hass = MagicMock()
    hass.states.get.return_value = None
    hass.services.has_service.return_value = True
    hass.services.async_call = AsyncMock()
    await _send(hass, PHONE, [ALERT_ON_REPORT])
    domain, service, payload = hass.services.async_call.call_args.args
    assert (domain, service) == ("notify", "mobile_app_pixel_9")
    assert payload["data"]["tag"] == "sentinel_report"
    assert payload["title"] == "📊 Sentinel Report"


async def test_send_to_a_notify_entity_uses_send_message_without_data():
    hass = MagicMock()
    hass.states.get.return_value = object()
    hass.services.has_service.return_value = True
    hass.services.async_call = AsyncMock()
    await _send(hass, "notify.pixel_9", [ALERT_ON_REPORT])
    domain, service, payload = hass.services.async_call.call_args.args
    assert (domain, service) == ("notify", "send_message")
    assert payload["entity_id"] == "notify.pixel_9"
    assert "data" not in payload


async def test_send_never_raises_when_the_target_is_unknown():
    hass = MagicMock()
    hass.states.get.return_value = None
    hass.services.has_service.return_value = False
    hass.services.async_call = AsyncMock()
    await _send(hass, PHONE, [ALERT_ON_REPORT])
    hass.services.async_call.assert_not_called()


@pytest.mark.parametrize("target", [None, ""])
async def test_no_target_means_no_notification(target):
    from custom_components.sentinel_report import _do_generate

    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.data = {}
    opts = {
        "include_warnings": True, "keep_history": False, "include_ha_repairs": False,
        "notify": False, "notify_threshold": "errors_only", "purge_mode": "disabled",
        "purge_keep_files": 30, "purge_keep_days": 30,
        "admin_notify_target": target, "companion_alerts": [ALERT_ON_REPORT],
    }
    with patch("custom_components.sentinel_report._send_companion_notification",
               new=AsyncMock()) as send, \
         patch("custom_components.sentinel_report.async_dispatcher_send"):
        await _do_generate(hass, "/tmp/sentinel_report_test.txt", opts)
    send.assert_not_called()
