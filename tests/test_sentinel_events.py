"""Tests du collecteur Sentinel v0.7.0 — mode événements et repli hass.data."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import ANY, AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from homeassistant.core import CoreState
from homeassistant.util import dt as dt_util

from custom_components.sentinel_report.collectors import sentinel as collector
from custom_components.sentinel_report.const import (
    DATA_KEY_SENTINEL,
    DATA_KEY_STABILITY,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _stub_task(coro):
    """Remplace hass.async_create_task : ferme la coroutine, renvoie un faux Task."""
    coro.close()
    return MagicMock()


def _make_hass(
    *,
    running: bool = True,
    configured: bool = True,
    fire_events: bool = True,
    has_service: bool = True,
):
    """Construire un faux hass. Retourne (hass, unsub, holder).

    holder["handler"] reçoit le handler enregistré sur sentinel_item_changed.
    """
    hass = MagicMock()
    hass.data = {}
    hass.state = CoreState.running if running else CoreState.starting

    entry = MagicMock()
    entry.data = {"fire_events": fire_events}
    entry.options = {}
    hass.config_entries.async_entries.return_value = [entry] if configured else []
    hass.services.has_service.return_value = has_service
    hass.services.async_call = AsyncMock()
    hass.async_create_task = MagicMock(side_effect=_stub_task)

    unsub = MagicMock()
    holder: dict = {}

    def _listen(event_type, handler):
        holder["event_type"] = event_type
        holder["handler"] = handler
        return unsub

    hass.bus.async_listen = MagicMock(side_effect=_listen)
    hass.bus.async_listen_once = MagicMock()
    return hass, unsub, holder


def _event(data: dict) -> MagicMock:
    return MagicMock(data=data)


def _payload(item_id: str = "int_tuya", healthy: bool = False, state: str = "setup_error", **extra):
    data = {
        "item_id": item_id,
        "provider": "integrations",
        "name": "Tuya",
        "domain": "tuya",
        "source": "Tuya",
        "item_type": "integration",
        "healthy": healthy,
        "state": state,
        "severity": "error",
        "reason": None,
        "failure_count": 1,
        "since": "2026-10-25T09:26:00+00:00",
    }
    data.update(extra)
    return data


def _legacy_item(item_id: str = "dev_1", name: str = "Ampoule", domain: str = "hue"):
    item = MagicMock()
    item.id = item_id
    item.name = name
    item.provider = "devices"
    item.healthy = False
    item.state = "unavailable"
    item.severity = "error"
    item.reason = ""
    item.since = datetime(2026, 10, 25, 9, 26, 0)
    item.failure_count = 1
    item.extra = {"domain": domain}
    return item


def _set_legacy_snapshot(hass, items: list) -> None:
    coordinator = MagicMock()
    coordinator.get_all_items.return_value = items
    hass.data["sentinel"] = {"entry1": coordinator}


# ── _format_since ────────────────────────────────────────────────────────────

def test_format_since_naive_datetime_is_kept_as_local():
    dt_util.set_default_time_zone(timezone(timedelta(hours=2)))
    try:
        assert collector._format_since(datetime(2026, 10, 25, 9, 26, 0)) == "2026-10-25 09:26:00"
    finally:
        dt_util.set_default_time_zone(dt_util.UTC)


def test_format_since_converts_utc_to_local():
    dt_util.set_default_time_zone(timezone(timedelta(hours=2)))
    try:
        assert collector._format_since("2026-10-25T09:26:00+00:00") == "2026-10-25 11:26:00"
        aware = datetime(2026, 10, 25, 9, 26, 0, tzinfo=timezone.utc)
        assert collector._format_since(aware) == "2026-10-25 11:26:00"
    finally:
        dt_util.set_default_time_zone(dt_util.UTC)


def test_format_since_empty_and_invalid():
    assert collector._format_since(None) == ""
    assert collector._format_since("") == ""
    assert collector._format_since("pas une date") == "pas une date"


# ── _item_from_event ─────────────────────────────────────────────────────────

def test_item_from_event_maps_all_fields():
    item = collector._item_from_event(_payload(reason="Token expiré", failure_count=3))
    assert item["id"] == "int_tuya"
    assert item["name"] == "Tuya"
    assert item["provider"] == "integrations"
    assert item["domain"] == "tuya"
    assert item["state"] == "setup_error"
    assert item["severity"] == "error"
    assert item["reason"] == "Token expiré"
    assert item["failure_count"] == 3
    assert item["healthy"] is False
    assert item["since"] == "2026-10-25 09:26:00"


def test_item_from_event_none_reason_becomes_empty_string():
    assert collector._item_from_event(_payload(reason=None))["reason"] == ""


# ── _events_unavailable_reason ───────────────────────────────────────────────

def test_reason_none_when_everything_is_available():
    hass, _, _ = _make_hass()
    assert collector._events_unavailable_reason(hass) is None


def test_reason_when_sentinel_not_configured():
    hass, _, _ = _make_hass(configured=False)
    assert collector._events_unavailable_reason(hass) == "Sentinel n'est pas configuré"


def test_reason_when_fire_events_disabled():
    hass, _, _ = _make_hass(fire_events=False)
    assert "fire_events" in collector._events_unavailable_reason(hass)


def test_reason_when_check_service_missing():
    hass, _, _ = _make_hass(has_service=False)
    assert "sentinel.check" in collector._events_unavailable_reason(hass)


# ── Mode événements ──────────────────────────────────────────────────────────

async def test_events_mode_subscribes_and_calls_check():
    hass, _, holder = _make_hass()
    await collector.async_setup(hass, 60, AsyncMock())

    assert holder["event_type"] == "sentinel_item_changed"
    hass.services.async_call.assert_awaited_once_with(
        "sentinel", "check", {}, blocking=True
    )
    assert hass.data[DATA_KEY_SENTINEL] == []


async def test_events_mode_adds_then_removes_item():
    hass, _, holder = _make_hass()
    await collector.async_setup(hass, 60, AsyncMock())

    holder["handler"](_event(_payload()))
    items = hass.data[DATA_KEY_SENTINEL]
    assert [i["id"] for i in items] == ["int_tuya"]

    holder["handler"](_event(_payload(healthy=True, state="loaded")))
    assert hass.data[DATA_KEY_SENTINEL] == []


async def test_events_mode_ignores_transient_state_and_removes_item():
    hass, _, holder = _make_hass()
    await collector.async_setup(hass, 60, AsyncMock())

    holder["handler"](_event(_payload()))
    assert len(hass.data[DATA_KEY_SENTINEL]) == 1

    holder["handler"](_event(_payload(state="not_loaded")))
    assert hass.data[DATA_KEY_SENTINEL] == []


async def test_events_mode_ignores_excluded_domains():
    hass, _, holder = _make_hass()
    await collector.async_setup(hass, 60, AsyncMock())

    holder["handler"](_event(_payload(item_id="self", domain="sentinel_report")))
    assert hass.data[DATA_KEY_SENTINEL] == []


async def test_events_mode_ignores_event_without_item_id():
    hass, _, holder = _make_hass()
    await collector.async_setup(hass, 60, AsyncMock())

    holder["handler"](_event({"healthy": False}))
    assert hass.data[DATA_KEY_SENTINEL] == []


async def test_events_mode_merges_stability_metadata():
    hass, _, holder = _make_hass()
    await collector.async_setup(hass, 60, AsyncMock())
    hass.data[DATA_KEY_STABILITY]["int_tuya"] = {
        "cycles": 2,
        "duration": "3 min",
        "type": "restart_failed",
    }

    holder["handler"](_event(_payload()))
    item = hass.data[DATA_KEY_SENTINEL][0]
    assert item["stability_type"] == "restart_failed"
    assert item["stability_cycles"] == 2
    assert item["stability_duration"] == "3 min"


async def test_events_mode_healthy_event_clears_stability_metadata():
    hass, _, holder = _make_hass()
    await collector.async_setup(hass, 60, AsyncMock())
    hass.data[DATA_KEY_STABILITY]["int_tuya"] = {
        "cycles": 2,
        "duration": "3 min",
        "type": "restart_failed",
    }

    holder["handler"](_event(_payload(healthy=True, state="loaded")))
    assert "int_tuya" not in hass.data[DATA_KEY_STABILITY]


async def test_events_mode_feeds_watcher_when_running():
    hass, _, holder = _make_hass(running=True)
    await collector.async_setup(hass, 60, AsyncMock())

    holder["handler"](_event(_payload()))
    # Un échec démarre la surveillance : un timer de stabilité est créé.
    assert hass.async_create_task.call_count == 1


async def test_events_mode_snapshot_events_do_not_feed_watcher():
    hass, _, holder = _make_hass(running=True)

    async def fake_check(domain, service, data, blocking=False):
        # Sentinel ré-émet un événement par item en défaut pendant sentinel.check
        holder["handler"](_event(_payload()))

    hass.services.async_call = AsyncMock(side_effect=fake_check)
    await collector.async_setup(hass, 60, AsyncMock())

    assert [i["id"] for i in hass.data[DATA_KEY_SENTINEL]] == ["int_tuya"]
    assert hass.async_create_task.call_count == 0


async def test_events_mode_watcher_waits_for_homeassistant_started():
    hass, _, holder = _make_hass(running=False)
    await collector.async_setup(hass, 60, AsyncMock())

    # Avant le démarrage complet : l'état est mis à jour, pas le watcher.
    holder["handler"](_event(_payload()))
    assert len(hass.data[DATA_KEY_SENTINEL]) == 1
    assert hass.async_create_task.call_count == 0

    event_type, on_started = hass.bus.async_listen_once.call_args[0]
    assert event_type == "homeassistant_started"
    await on_started(None)
    assert hass.services.async_call.await_count == 2  # setup + started

    holder["handler"](_event(_payload(item_id="int_hue", name="Hue")))
    assert hass.async_create_task.call_count == 1


async def test_events_mode_check_failure_falls_back_to_snapshot():
    hass, _, _ = _make_hass()
    _set_legacy_snapshot(hass, [_legacy_item()])
    hass.services.async_call = AsyncMock(side_effect=RuntimeError("boom"))

    await collector.async_setup(hass, 60, AsyncMock())
    assert [i["id"] for i in hass.data[DATA_KEY_SENTINEL]] == ["dev_1"]


async def test_unsubscribe_removes_listener_and_cancels_timers():
    hass, unsub, holder = _make_hass()
    unsubscribe = await collector.async_setup(hass, 60, AsyncMock())

    holder["handler"](_event(_payload()))
    unsubscribe()
    unsub.assert_called_once()


# ── Repli hass.data ──────────────────────────────────────────────────────────

async def test_fallback_when_fire_events_disabled():
    hass, _, holder = _make_hass(fire_events=False)
    _set_legacy_snapshot(hass, [_legacy_item()])
    dispatcher_unsub = MagicMock()

    with patch.object(
        collector, "async_dispatcher_connect", return_value=dispatcher_unsub
    ) as connect:
        unsubscribe = await collector.async_setup(hass, 60, AsyncMock())

    assert "handler" not in holder  # pas d'écoute de sentinel_item_changed
    hass.services.async_call.assert_not_awaited()
    connect.assert_called_once_with(hass, "sentinel_update", ANY)
    assert [i["id"] for i in hass.data[DATA_KEY_SENTINEL]] == ["dev_1"]

    unsubscribe()
    dispatcher_unsub.assert_called_once()


async def test_fallback_when_check_service_missing():
    hass, _, holder = _make_hass(has_service=False)
    _set_legacy_snapshot(hass, [_legacy_item()])

    with patch.object(collector, "async_dispatcher_connect", return_value=MagicMock()):
        await collector.async_setup(hass, 60, AsyncMock())

    assert "handler" not in holder
    assert [i["id"] for i in hass.data[DATA_KEY_SENTINEL]] == ["dev_1"]


async def test_fallback_dispatcher_update_refreshes_snapshot():
    hass, _, _ = _make_hass(fire_events=False)
    _set_legacy_snapshot(hass, [])
    captured: dict = {}

    def _connect(_hass, _signal, target):
        captured["target"] = target
        return MagicMock()

    with patch.object(collector, "async_dispatcher_connect", side_effect=_connect):
        await collector.async_setup(hass, 60, AsyncMock())

    assert hass.data[DATA_KEY_SENTINEL] == []
    _set_legacy_snapshot(hass, [_legacy_item()])
    captured["target"](_legacy_item())
    assert [i["id"] for i in hass.data[DATA_KEY_SENTINEL]] == ["dev_1"]
    assert hass.async_create_task.call_count == 1  # le watcher a reçu l'échec


# ── StabilityWatcher ─────────────────────────────────────────────────────────

async def test_watcher_republishes_before_generating_on_restart_failed():
    hass = MagicMock()
    hass.data = {}
    order: list[str] = []

    async def generate(alert_type=None, stability_context=None):
        order.append(f"generate:{alert_type}")

    watcher = collector.StabilityWatcher(
        hass,
        stability_delay=0,
        generate_callback=generate,
        on_stability_change=lambda: order.append("publish"),
    )
    watcher._watched["x"] = {
        "name": "Z2M",
        "cycles": 2,
        "first_failure": datetime.now(),
        "last_state_healthy": False,
        "timer": None,
    }

    await watcher._on_timer_expired("x")

    assert order == ["publish", "generate:on_restart_fail"]
    assert hass.data[DATA_KEY_STABILITY]["x"]["type"] == "restart_failed"


async def test_watcher_does_not_republish_on_resolved():
    hass = MagicMock()
    hass.data = {}
    published: list[str] = []

    watcher = collector.StabilityWatcher(
        hass,
        stability_delay=0,
        generate_callback=AsyncMock(),
        on_stability_change=lambda: published.append("publish"),
    )
    watcher._watched["x"] = {
        "name": "Z2M",
        "cycles": 2,
        "first_failure": datetime.now(),
        "last_state_healthy": True,
        "timer": None,
    }

    await watcher._on_timer_expired("x")
    assert published == []


def test_watcher_cancel_all_cancels_running_timers():
    hass = MagicMock()
    hass.data = {}
    watcher = collector.StabilityWatcher(hass, 60, AsyncMock())
    running = MagicMock()
    running.done.return_value = False
    finished = MagicMock()
    finished.done.return_value = True
    watcher._watched = {
        "a": {"timer": running},
        "b": {"timer": finished},
        "c": {"timer": None},
    }

    watcher.cancel_all()

    running.cancel.assert_called_once()
    finished.cancel.assert_not_called()
    assert watcher._watched == {}
