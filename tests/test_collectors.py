"""Tests des collecteurs sentinel_report (modules internes v0.6.0).

Les collecteurs sont maintenant dans sentinel_report/collectors/.
"""
from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.sentinel_report.collectors.sentinel import (
    _collect_items,
    _TRANSIENT_STATES,
    _EXCLUDED_DOMAINS,
)
from custom_components.sentinel_report.collectors.spook import (
    _normalize_severity,
    _flatten_placeholder,
    _build_label,
    _collect_issues,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_sentinel_item(
    id="item1",
    name="Test Device",
    provider="devices",
    healthy=False,
    state="unavailable",
    severity="error",
    reason="",
    since=None,
    failure_count=1,
    domain="tuya",
):
    item = MagicMock()
    item.id = id
    item.name = name
    item.provider = provider
    item.healthy = healthy
    item.state = state
    item.severity = severity
    item.reason = reason
    item.since = since or datetime(2026, 1, 1, 12, 0, 0)
    item.failure_count = failure_count
    item.extra = {"domain": domain}
    return item


def _make_hass(items=None, sentinel_present=True):
    hass = MagicMock()
    coordinator = MagicMock()
    coordinator.get_all_items.return_value = items or []
    if sentinel_present:
        hass.data = {"sentinel": {"entry1": coordinator}}
    else:
        hass.data = {}
    return hass


# ── Tests — _collect_items ───────────────────────────────────────────────────

def test_collect_items_returns_empty_when_sentinel_absent():
    hass = _make_hass(sentinel_present=False)
    assert _collect_items(hass) == []


def test_collect_items_skips_healthy_items():
    item = _make_sentinel_item(healthy=True)
    assert _collect_items(_make_hass(items=[item])) == []


def test_collect_items_skips_transient_states():
    for state in _TRANSIENT_STATES:
        item = _make_sentinel_item(healthy=False, state=state)
        assert _collect_items(_make_hass(items=[item])) == [], f"État '{state}' aurait dû être filtré"


def test_collect_items_skips_excluded_domains():
    for domain in _EXCLUDED_DOMAINS:
        item = _make_sentinel_item(healthy=False, state="unavailable", domain=domain)
        assert _collect_items(_make_hass(items=[item])) == [], f"Domaine '{domain}' aurait dû être exclu"


def test_collect_items_includes_real_errors():
    item = _make_sentinel_item(healthy=False, state="unavailable", domain="tuya")
    result = _collect_items(_make_hass(items=[item]))
    assert len(result) == 1
    assert result[0]["name"] == "Test Device"
    assert result[0]["state"] == "unavailable"
    assert result[0]["domain"] == "tuya"


def test_collect_items_formats_since_correctly():
    since = datetime(2026, 8, 29, 10, 0, 0)
    item = _make_sentinel_item(since=since)
    result = _collect_items(_make_hass(items=[item]))
    assert result[0]["since"] == "2026-08-29 10:00:00"


def test_collect_items_multiple_items():
    items = [
        _make_sentinel_item(id="1", name="Device A", domain="mqtt"),
        _make_sentinel_item(id="2", name="Device B", domain="tuya"),
        _make_sentinel_item(id="3", name="Device C", healthy=True),
        _make_sentinel_item(id="4", name="Device D", state="not_loaded"),
    ]
    result = _collect_items(_make_hass(items=items))
    assert len(result) == 2
    assert {r["name"] for r in result} == {"Device A", "Device B"}


# ── Tests — _normalize_severity ──────────────────────────────────────────────

def test_normalize_severity_error():
    sev = MagicMock()
    sev.value = "error"
    assert _normalize_severity(sev) == "error"


def test_normalize_severity_critical_becomes_error():
    sev = MagicMock()
    sev.value = "critical"
    assert _normalize_severity(sev) == "error"


def test_normalize_severity_warning():
    sev = MagicMock()
    sev.value = "warning"
    assert _normalize_severity(sev) == "warning"


def test_normalize_severity_none_becomes_warning():
    assert _normalize_severity(None) == "warning"


def test_normalize_severity_unknown_becomes_warning():
    sev = MagicMock()
    sev.value = "other"
    assert _normalize_severity(sev) == "warning"


# ── Tests — _flatten_placeholder ─────────────────────────────────────────────

def test_flatten_placeholder_backtick_list():
    value = "- `entity_id_1`\n- `entity_id_2`\n- `entity_id_3`"
    assert _flatten_placeholder(value) == "entity_id_1, entity_id_2, entity_id_3"


def test_flatten_placeholder_single_backtick():
    assert _flatten_placeholder("`light.salon`") == "light.salon"


def test_flatten_placeholder_filters_bare_domains():
    """Spook 5.1.0 : domaines seuls (mqtt, tuya) filtrés — seuls les entity_id gardés."""
    value = "- `binary_sensor.my_sensor`\n- `mqtt`\n- `sensor.temp`\n- `mqtt`"
    result = _flatten_placeholder(value)
    assert "binary_sensor.my_sensor" in result
    assert "sensor.temp" in result
    assert "mqtt" not in result


def test_flatten_placeholder_plain_text():
    value = "- item_a\n- item_b"
    assert "\n" not in _flatten_placeholder(value)


def test_flatten_placeholder_already_flat():
    assert _flatten_placeholder("homeassistant.remove_entity") == "homeassistant.remove_entity"


# ── Tests — _build_label ─────────────────────────────────────────────────────

def test_build_label_no_placeholders():
    assert _build_label("my_key", {}) == "[my_key]"


def test_build_label_with_dashboard():
    result = _build_label("lovelace_unknown_entity_references", {"dashboard": "Maison"})
    assert "[lovelace_unknown_entity_references]" in result
    assert "dashboard: Maison" in result


def test_build_label_with_entities_list():
    result = _build_label(
        "lovelace_unknown_entity_references",
        {"dashboard": "Maison", "entities": "- `light.lamp`\n- `sensor.temp`"},
    )
    assert "light.lamp, sensor.temp" in result
    assert "\n" not in result


def test_build_label_preferred_order():
    result = _build_label(
        "script_unknown_service_references",
        {"script": "Mon Script", "services": "- `homeassistant.remove_entity`", "entity_id": "script.mon_script"},
    )
    parts = result.split(" — ")
    script_idx = next(i for i, p in enumerate(parts) if "script:" in p)
    services_idx = next(i for i, p in enumerate(parts) if "services:" in p)
    assert script_idx < services_idx


def test_build_label_edit_key_excluded():
    result = _build_label(
        "lovelace_unknown_entity_references",
        {"dashboard": "Maison", "edit": "/dashboard-maison/1?edit=1"},
    )
    assert "edit:" not in result


def test_build_label_dead_entities():
    result = _build_label(
        "dead_entities",
        {"integration": "Tuya", "entities": "- `light.salon`\n- `switch.bureau`"},
    )
    assert "integration: Tuya" in result
    assert "light.salon, switch.bureau" in result
    assert "\n" not in result


def test_build_label_stale_access_tokens():
    result = _build_label(
        "stale_access_tokens",
        {"token": "Mon script", "owner": "Mathieu", "last_active": "2025-01-01"},
    )
    assert "token: Mon script" in result
    assert "owner: Mathieu" in result
    assert "last_active: 2025-01-01" in result


def test_build_label_unused_blueprints():
    result = _build_label(
        "unused_blueprints",
        {"domain": "automation", "blueprint": "Notify Leaving Zone"},
    )
    assert "domain: automation" in result
    assert "blueprint: Notify Leaving Zone" in result


def test_build_label_automation_unknown_trigger_references():
    result = _build_label(
        "automation_unknown_trigger_references",
        {"automation": "Mon Auto", "triggers": "- `old.trigger`", "edit": "/config/auto/edit/abc"},
    )
    assert "automation: Mon Auto" in result
    assert "old.trigger" in result
    assert "edit:" not in result


def test_build_label_automation_unknown_condition_references():
    result = _build_label(
        "automation_unknown_condition_references",
        {"automation": "Mon Auto", "conditions": "- `old.condition`", "edit": "/config/auto/edit/abc"},
    )
    assert "automation: Mon Auto" in result
    assert "old.condition" in result
    assert "edit:" not in result


def test_build_label_lovelace_missing_resources():
    result = _build_label(
        "lovelace_missing_resources",
        {"resources": "- `/local/card.js`\n- `/hacsfiles/old-card.js`"},
    )
    assert "/local/card.js" in result
    assert "/hacsfiles/old-card.js" in result
    assert "\n" not in result


def test_build_label_lovelace_unknown_area_references():
    result = _build_label(
        "lovelace_unknown_area_references",
        {"dashboard": "Maison", "areas": "- `kitchen`\n- `old_room`", "edit": "/dashboard/0?edit=1"},
    )
    assert "dashboard: Maison" in result
    assert "kitchen, old_room" in result
    assert "edit:" not in result


# ── Tests — _collect_issues ──────────────────────────────────────────────────

def test_collect_issues_filters_non_spook():
    hass = MagicMock()

    issue_spook = MagicMock()
    issue_spook.domain = "spook"
    issue_spook.dismissed_version = None
    issue_spook.translation_key = "some_key"
    issue_spook.issue_id = "some_key_detail"
    issue_spook.translation_placeholders = {}
    issue_spook.severity = MagicMock(value="warning")
    issue_spook.is_fixable = True

    issue_other = MagicMock()
    issue_other.domain = "homeassistant"
    issue_other.dismissed_version = None

    registry = MagicMock()
    registry.issues = {"a": issue_spook, "b": issue_other}

    with patch("custom_components.sentinel_report.collectors.spook.ir.async_get", return_value=registry):
        result = _collect_issues(hass)

    assert len(result) == 1
    assert result[0]["domain"] == "spook"


def test_collect_issues_skips_dismissed():
    hass = MagicMock()
    issue = MagicMock()
    issue.domain = "spook"
    issue.dismissed_version = "2024.1.0"

    registry = MagicMock()
    registry.issues = {"a": issue}

    with patch("custom_components.sentinel_report.collectors.spook.ir.async_get", return_value=registry):
        result = _collect_issues(hass)

    assert result == []
