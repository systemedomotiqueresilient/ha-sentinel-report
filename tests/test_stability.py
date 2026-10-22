"""Tests unitaires pour le StabilityWatcher et les nouvelles fonctionnalités v0.6.1."""
from __future__ import annotations

import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.sentinel_report.collectors.sentinel import (
    StabilityWatcher,
    _format_duration,
)
from custom_components.sentinel_report.const import (
    DATA_KEY_RESOLVED,
    DATA_KEY_STABILITY,
)
from custom_components.sentinel_report.reporter import generate_report


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_hass() -> MagicMock:
    hass = MagicMock()
    hass.data = {}
    # Créer un event loop dédié pour les tests synchrones
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    hass.async_create_task = lambda coro: loop.create_task(coro)
    return hass


def _make_generate_cb() -> tuple:
    """Retourne un callback mock et la liste des appels reçus."""
    calls = []

    async def cb(alert_type=None, stability_context=None):
        calls.append({"alert_type": alert_type, "stability_context": stability_context})

    return cb, calls


# ── Tests — _format_duration ─────────────────────────────────────────────────

def test_format_duration_seconds():
    assert _format_duration(45) == "45 sec"


def test_format_duration_minutes():
    assert _format_duration(90) == "1 min 30 sec"


def test_format_duration_exact_minutes():
    assert _format_duration(120) == "2 min"


def test_format_duration_hours():
    assert _format_duration(3661) == "1 h 1 min"


def test_format_duration_zero():
    assert _format_duration(0) == "0 sec"


# ── Tests — StabilityWatcher.on_item_update ──────────────────────────────────

def test_watcher_ignores_healthy_item_not_watched():
    hass = _make_hass()
    cb, calls = _make_generate_cb()
    watcher = StabilityWatcher(hass, stability_delay=60, generate_callback=cb)
    watcher.on_item_update("item1", "Z2M", is_healthy=True)
    assert "item1" not in watcher._watched


def test_watcher_starts_watching_on_first_failure():
    hass = _make_hass()
    cb, calls = _make_generate_cb()
    watcher = StabilityWatcher(hass, stability_delay=60, generate_callback=cb)
    watcher.on_item_update("item1", "Z2M", is_healthy=False)
    assert "item1" in watcher._watched
    assert watcher._watched["item1"]["cycles"] == 0
    # Annuler le timer pour éviter le RuntimeWarning
    watcher._watched["item1"]["timer"].cancel()


def test_watcher_counts_cycle_on_rechute():
    hass = _make_hass()
    cb, calls = _make_generate_cb()
    watcher = StabilityWatcher(hass, stability_delay=60, generate_callback=cb)
    watcher.on_item_update("item1", "Z2M", is_healthy=False)
    watcher.on_item_update("item1", "Z2M", is_healthy=True)
    watcher.on_item_update("item1", "Z2M", is_healthy=False)
    assert watcher._watched["item1"]["cycles"] == 1
    watcher._watched["item1"]["timer"].cancel()


def test_watcher_counts_multiple_cycles():
    hass = _make_hass()
    cb, calls = _make_generate_cb()
    watcher = StabilityWatcher(hass, stability_delay=60, generate_callback=cb)
    watcher.on_item_update("item1", "Z2M", is_healthy=False)
    watcher.on_item_update("item1", "Z2M", is_healthy=True)
    watcher.on_item_update("item1", "Z2M", is_healthy=False)
    watcher.on_item_update("item1", "Z2M", is_healthy=True)
    watcher.on_item_update("item1", "Z2M", is_healthy=False)
    assert watcher._watched["item1"]["cycles"] == 2
    watcher._watched["item1"]["timer"].cancel()


def test_watcher_update_delay():
    """update_delay met à jour le délai correctement sans créer de tâches."""
    from unittest.mock import MagicMock
    hass = MagicMock()
    hass.data = {}
    # Ne pas créer de vraies tâches asyncio pour ce test
    hass.async_create_task = MagicMock()
    cb, _ = _make_generate_cb()
    watcher = StabilityWatcher(hass, stability_delay=60, generate_callback=cb)
    watcher.update_delay(120)
    assert watcher._delay == 120


# ── Tests — StabilityWatcher timer (asyncio) ─────────────────────────────────

async def _run_watcher_scenario(
    events: list[tuple[bool, float]],
    stability_delay: float = 0.1,
) -> tuple[dict, list]:
    hass = MagicMock()
    hass.data = {}
    hass.data[DATA_KEY_STABILITY] = {}
    hass.data[DATA_KEY_RESOLVED] = []
    cb, calls = _make_generate_cb()
    watcher = StabilityWatcher(hass, stability_delay=stability_delay, generate_callback=cb)
    # Dans un contexte async, async_create_task crée une vraie tâche
    hass.async_create_task = lambda coro: asyncio.ensure_future(coro)

    for is_healthy, sleep_after in events:
        watcher.on_item_update("item1", "Z2M Bridge", is_healthy=is_healthy)
        if sleep_after > 0:
            await asyncio.sleep(sleep_after)

    await asyncio.sleep(stability_delay + 0.05)
    return hass.data, calls


def test_watcher_below_min_cycles_no_generate():
    async def _run():
        hass_data, calls = await _run_watcher_scenario(
            events=[(False, 0), (True, 0)],
            stability_delay=0.05,
        )
        assert calls == []

    asyncio.run(_run())


def test_watcher_restart_fail_triggers_generate():
    async def _run():
        hass_data, calls = await _run_watcher_scenario(
            events=[
                (False, 0.01),
                (True,  0.01),
                (False, 0.01),
                (True,  0.01),
                (False, 0.0),
            ],
            stability_delay=0.05,
        )
        assert len(calls) == 1
        assert calls[0]["alert_type"] == "on_restart_fail"
        ctx = calls[0]["stability_context"]
        assert ctx["cycles"] == 2
        assert ctx["resolved"] is False

    asyncio.run(_run())


def test_watcher_resolved_triggers_generate():
    async def _run():
        hass_data, calls = await _run_watcher_scenario(
            events=[
                (False, 0.01),
                (True,  0.01),
                (False, 0.01),
                (True,  0.01),
                (False, 0.01),
                (True,  0.0),
            ],
            stability_delay=0.05,
        )
        assert len(calls) == 1
        assert calls[0]["alert_type"] == "on_resolved"
        ctx = calls[0]["stability_context"]
        assert ctx["cycles"] == 2
        assert ctx["resolved"] is True

    asyncio.run(_run())


# ── Tests — generate_report avec ha_repairs + resolved_incidents ──────────────

FIXED_DT = datetime(2026, 9, 1, 10, 0, 0)


def _report(sentinel_items, spook_issues, resolved_incidents,
            include_warnings, ha_repairs=None):
    """Helper — passe ha_repairs=[] par défaut."""
    content, _, _ = generate_report(
        sentinel_items, spook_issues, ha_repairs or [],
        resolved_incidents, include_warnings,
        generated_at=FIXED_DT,
    )
    return content


def _flags(sentinel_items, spook_issues, resolved_incidents,
           include_warnings, ha_repairs=None):
    _, has_problems, has_resolved = generate_report(
        sentinel_items, spook_issues, ha_repairs or [],
        resolved_incidents, include_warnings,
        generated_at=FIXED_DT,
    )
    return has_problems, has_resolved


def test_report_no_resolved_section_when_empty():
    content = _report([], [], [], include_warnings=True)
    assert "INCIDENTS RÉSOLUS" not in content


def test_report_resolved_section_present():
    resolved = [{
        "id": "item1",
        "name": "Z2M Bridge",
        "cycles": 2,
        "duration": "3 min 12 sec",
        "first_failure": "2026-09-01 09:55:00",
        "resolved_at": "2026-09-01 09:58:12",
        "type": "resolved",
    }]
    content = _report([], [], resolved, include_warnings=True)
    assert "INCIDENTS RÉSOLUS (1)" in content
    assert "Z2M Bridge" in content
    assert "2 cycle" in content
    assert "3 min 12 sec" in content
    assert "09:55:00" in content


def test_report_has_resolved_flag():
    resolved = [{"id": "x", "name": "Z2M", "cycles": 2,
                 "duration": "1 min", "first_failure": "", "resolved_at": "", "type": "resolved"}]
    hp, hr = _flags([], [], resolved, include_warnings=True)
    assert hr is True
    assert hp is False


def test_report_stability_enrichment_in_problems():
    sentinel_items = [{
        "id": "item1",
        "name": "Z2M Bridge",
        "provider": "devices",
        "domain": "mqtt",
        "state": "unavailable",
        "severity": "error",
        "reason": "",
        "since": "2026-09-01 09:55:00",
        "failure_count": 4,
        "stability_type": "restart_failed",
        "stability_cycles": 2,
        "stability_duration": "3 min 12 sec",
    }]
    content = _report(sentinel_items, [], [], include_warnings=True)
    assert "N'a pas redémarré" in content
    assert "2 échec" in content
    assert "3 min 12 sec" in content


def test_report_footer_includes_resolved():
    resolved = [{"id": "x", "name": "Z2M", "cycles": 2,
                 "duration": "1 min", "first_failure": "", "resolved_at": "", "type": "resolved"}]
    content = _report([], [], resolved, include_warnings=True)
    assert "résolu" in content.lower()


# ── Tests — validation config flow ───────────────────────────────────────────

def test_validate_stability_delay_too_low():
    from custom_components.sentinel_report.config_flow import _validate_inputs
    assert _validate_inputs("/share", "report.txt", 45) == "stability_delay_too_low"


def test_validate_stability_delay_too_high():
    from custom_components.sentinel_report.config_flow import _validate_inputs
    assert _validate_inputs("/share", "report.txt", 7200) == "stability_delay_too_high"


def test_validate_stability_delay_valid():
    from custom_components.sentinel_report.config_flow import _validate_inputs
    assert _validate_inputs("/share", "report.txt", 60) is None
    assert _validate_inputs("/share", "report.txt", 300) is None
    assert _validate_inputs("/share", "report.txt", 3600) is None


def test_validate_stability_delay_boundary_low():
    from custom_components.sentinel_report.config_flow import _validate_inputs
    assert _validate_inputs("/share", "report.txt", 60) is None


def test_validate_stability_delay_boundary_high():
    from custom_components.sentinel_report.config_flow import _validate_inputs
    assert _validate_inputs("/share", "report.txt", 3600) is None
