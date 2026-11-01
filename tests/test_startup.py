"""Tests des rapports de démarrage : régénération différée et libellés "initialisation"."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import custom_components.sentinel_report as integration
from custom_components.sentinel_report.const import (
    DATA_KEY_STARTED,
    STARTUP_REPORT_DELAY,
    STARTUP_SETTLE_DELAY,
)
from custom_components.sentinel_report.reporter import generate_report

MODULE = "custom_components.sentinel_report"
FIXED_DT = datetime(2026, 1, 1, 12, 0, 0)  # noqa: DTZ001

SPOOK_ISSUE = {
    "issue_id": "automation_unknown_trigger_references_x",
    "severity": "warning",
    "label": "[automation_unknown_trigger_references] — automation: Test",
}


# ── Reporter : libellés de démarrage ─────────────────────────────────────────

def _report(spook, ha_repairs, *, initializing: bool, sentinel=None) -> str:
    content, _, _ = generate_report(
        sentinel or [], spook, ha_repairs, [], True, FIXED_DT, initializing,
    )
    return content


def test_default_report_unchanged_when_not_initializing():
    content = _report([], [], initializing=False)
    assert "✔ No Spook issues detected." in content
    assert "✔ No HA deprecation issues detected." in content
    assert "✔ All clear" in content
    assert "⏳" not in content


def test_initializing_empty_sections_are_not_reported_as_clear():
    content = _report([], [], initializing=True)
    assert "Spook en cours d'initialisation" in content
    assert "HA Repairs en cours d'initialisation" in content
    assert "✔ No Spook issues detected." not in content
    assert "✔ No HA deprecation issues detected." not in content
    assert "✔ All clear" not in content
    assert "Démarrage en cours — résultat non définitif." in content


def test_initializing_adds_header_note():
    content = _report([], [], initializing=True)
    header, _, _ = content.partition("--- SENTINEL PROBLEMS")
    assert "Démarrage récent de Home Assistant" in header


def test_initializing_keeps_real_issues_and_error_footer():
    content = _report([SPOOK_ISSUE], [], initializing=True)
    assert SPOOK_ISSUE["label"] in content
    assert "Spook en cours d'initialisation" not in content
    assert "✖ 1 spook issue" in content
    assert "Démarrage en cours — résultat non définitif." not in content


def test_initializing_without_spook_has_no_spook_section():
    content = _report(None, [], initializing=True)
    assert "SPOOK REPAIRS" not in content
    assert "HA Repairs en cours d'initialisation" in content


def test_initializing_does_not_change_has_problems():
    _, has_problems, _ = generate_report([], [], [], [], True, FIXED_DT, True)
    assert has_problems is False


# ── Planification des rapports de démarrage ──────────────────────────────────

def _make_hass():
    hass = MagicMock()
    hass.data = {}
    unsub = MagicMock()
    holder: dict = {}

    def _listen(event_type, handler):
        holder["event_type"] = event_type
        holder["handler"] = handler
        return unsub

    hass.bus.async_listen_once = MagicMock(side_effect=_listen)
    return hass, unsub, holder


def test_nothing_is_scheduled_before_homeassistant_started():
    hass, _, holder = _make_hass()
    with patch(f"{MODULE}.async_call_later") as call_later:
        integration._schedule_startup_reports(hass, AsyncMock())
    assert holder["event_type"] == "homeassistant_started"
    call_later.assert_not_called()


def test_two_reports_scheduled_after_homeassistant_started():
    hass, _, holder = _make_hass()
    with patch(f"{MODULE}.async_call_later", side_effect=[MagicMock(), MagicMock()]) as call_later:
        integration._schedule_startup_reports(hass, AsyncMock())
        holder["handler"](MagicMock())
    delays = [call.args[1] for call in call_later.call_args_list]
    assert delays == [STARTUP_REPORT_DELAY, STARTUP_SETTLE_DELAY]
    assert DATA_KEY_STARTED in hass.data


def test_scheduled_action_calls_generate_callback():
    hass, _, holder = _make_hass()
    generate_cb = AsyncMock()
    with patch(f"{MODULE}.async_call_later", side_effect=[MagicMock(), MagicMock()]) as call_later:
        integration._schedule_startup_reports(hass, generate_cb)
        holder["handler"](MagicMock())
    action = call_later.call_args_list[0].args[2]
    asyncio.run(action(None))
    generate_cb.assert_awaited_once_with()


def test_cancel_before_start_removes_the_listener():
    hass, unsub, _ = _make_hass()
    with patch(f"{MODULE}.async_call_later") as call_later:
        cancel = integration._schedule_startup_reports(hass, AsyncMock())
        cancel()
    unsub.assert_called_once_with()
    call_later.assert_not_called()


def test_cancel_after_start_cancels_both_timers_only():
    hass, unsub, holder = _make_hass()
    timers = [MagicMock(), MagicMock()]
    with patch(f"{MODULE}.async_call_later", side_effect=timers):
        cancel = integration._schedule_startup_reports(hass, AsyncMock())
        holder["handler"](MagicMock())
        cancel()
    for timer in timers:
        timer.assert_called_once_with()
    unsub.assert_not_called()


# ── Fenêtre d'initialisation ─────────────────────────────────────────────────

def test_initializing_while_homeassistant_is_not_running():
    hass = MagicMock()
    hass.data = {}
    hass.is_running = False
    assert integration._is_initializing(hass) is True


def test_not_initializing_after_reload_on_a_running_instance():
    hass = MagicMock()
    hass.data = {}
    hass.is_running = True
    assert integration._is_initializing(hass) is False


def test_initializing_window_after_start():
    hass = MagicMock()
    hass.is_running = True
    hass.data = {DATA_KEY_STARTED: 1000.0}
    with patch(f"{MODULE}.time.monotonic", return_value=1000.0 + STARTUP_SETTLE_DELAY - 1):
        assert integration._is_initializing(hass) is True
    with patch(f"{MODULE}.time.monotonic", return_value=1000.0 + STARTUP_SETTLE_DELAY + 1):
        assert integration._is_initializing(hass) is False
