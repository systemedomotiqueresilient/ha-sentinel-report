"""Collecteur Sentinel — module interne de sentinel_report.

Lit les données de ha-sentinel (GuiPoM) via hass.data["sentinel"]
et les dépose dans hass.data[DATA_KEY_SENTINEL].

v0.6.1 : ajout du StabilityWatcher — détecte les cycles d'instabilité
et déclenche automatiquement la génération du rapport après stabilisation.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from ..const import (
    DATA_KEY_RESOLVED,
    DATA_KEY_SENTINEL,
    DATA_KEY_STABILITY,
    STABILITY_MIN_CYCLES,
)

_LOGGER = logging.getLogger(__name__)

_SIGNAL_SENTINEL_UPDATE = "sentinel_update"
_TRANSIENT_STATES = {"not_loaded", "setup_in_progress", "loading"}
_EXCLUDED_DOMAINS = {
    "sentinel_report",
    "sentinel_report_sentinel",
    "sentinel_report_spook",
}


# ── StabilityWatcher ─────────────────────────────────────────────────────────

class StabilityWatcher:
    """Surveille les cycles d'instabilité par item Sentinel.

    Pour chaque item qui alterne entre états sains et non-sains,
    compte les cycles et déclenche la génération du rapport après
    un délai de stabilité sans nouveau changement.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        stability_delay: int,
        generate_callback: Callable,
    ) -> None:
        self._hass = hass
        self._delay = stability_delay
        self._generate_cb = generate_callback
        # {item_id: {"cycles": int, "first_failure": datetime, "last_healthy": bool, "timer": Task}}
        self._watched: dict[str, dict] = {}

    def on_item_update(self, item_id: str, name: str, is_healthy: bool) -> None:
        """Appelé à chaque changement d'état d'un item Sentinel."""
        now = datetime.now()  # noqa: DTZ005

        if item_id not in self._watched:
            if is_healthy:
                return  # Item sain qu'on ne surveille pas encore — ignorer
            # Première détection d'un problème — démarrer la surveillance
            self._watched[item_id] = {
                "name": name,
                "cycles": 0,
                "first_failure": now,
                "last_state_healthy": False,
                "timer": None,
            }
            _LOGGER.debug("StabilityWatcher : début surveillance de '%s'", name)

        entry = self._watched[item_id]
        last_healthy = entry["last_state_healthy"]

        # Détecter un cycle : transition unhealthy → healthy → unhealthy
        if is_healthy and not last_healthy:
            # Récupération temporaire
            entry["last_state_healthy"] = True
            _LOGGER.debug("StabilityWatcher : '%s' semble récupéré (cycle potentiel)", name)
        elif not is_healthy and last_healthy:
            # Rechute → cycle confirmé
            entry["cycles"] += 1
            entry["last_state_healthy"] = False
            _LOGGER.debug(
                "StabilityWatcher : '%s' rechute — cycle %d", name, entry["cycles"]
            )

        # (Re)démarrer le timer de stabilité
        self._reset_timer(item_id)

    def _reset_timer(self, item_id: str) -> None:
        """Annuler le timer existant et en démarrer un nouveau."""
        entry = self._watched.get(item_id)
        if not entry:
            return
        if entry.get("timer") and not entry["timer"].done():
            entry["timer"].cancel()
        entry["timer"] = self._hass.async_create_task(
            self._on_timer_expired(item_id)
        )

    async def _on_timer_expired(self, item_id: str) -> None:
        """Timer expiré — l'item est stable (dans un sens ou dans l'autre)."""
        await asyncio.sleep(self._delay)

        entry = self._watched.pop(item_id, None)
        if not entry:
            return

        cycles = entry["cycles"]
        name = entry["name"]
        first_failure = entry["first_failure"]
        is_healthy_now = entry["last_state_healthy"]
        duration = datetime.now() - first_failure  # noqa: DTZ005
        duration_str = _format_duration(duration.total_seconds())

        # Ignorer si moins de STABILITY_MIN_CYCLES cycles — comportement normal
        if cycles < STABILITY_MIN_CYCLES:
            _LOGGER.debug(
                "StabilityWatcher : '%s' stabilisé avec %d cycle(s) — seuil non atteint",
                name, cycles,
            )
            return

        _LOGGER.info(
            "StabilityWatcher : '%s' stabilisé après %d cycle(s) sur %s — healthy=%s",
            name, cycles, duration_str, is_healthy_now,
        )

        if is_healthy_now:
            # Résolution : l'item est revenu à la normale
            resolved = self._hass.data.setdefault(DATA_KEY_RESOLVED, [])
            resolved.append(
                {
                    "id":            item_id,
                    "name":          name,
                    "cycles":        cycles,
                    "duration":      duration_str,
                    "first_failure": first_failure.strftime("%Y-%m-%d %H:%M:%S"),
                    "resolved_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # noqa: DTZ005
                    "type":          "resolved",
                }
            )
        else:
            # Échec de restart : toujours en erreur après le timer
            stability = self._hass.data.setdefault(DATA_KEY_STABILITY, {})
            stability[item_id] = {
                "name":          name,
                "cycles":        cycles,
                "duration":      duration_str,
                "first_failure": first_failure.strftime("%Y-%m-%d %H:%M:%S"),
                "type":          "restart_failed",
            }

        # Déclencher la génération du rapport
        await self._generate_cb(
            alert_type="on_resolved" if is_healthy_now else "on_restart_fail",
            stability_context={
                "name":     name,
                "cycles":   cycles,
                "duration": duration_str,
                "resolved": is_healthy_now,
            },
        )

    def update_delay(self, new_delay: int) -> None:
        """Mettre à jour le délai de stabilité (après changement d'options)."""
        self._delay = new_delay


def _format_duration(seconds: float) -> str:
    """Formater une durée en secondes en chaîne lisible."""
    total = int(seconds)
    if total < 60:
        return f"{total} sec"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes} min {secs} sec" if secs else f"{minutes} min"
    hours, mins = divmod(minutes, 60)
    return f"{hours} h {mins} min"


# ── Collecte et setup ─────────────────────────────────────────────────────────

def _collect_items(hass: HomeAssistant) -> list[dict]:
    """Extraire les items unhealthy depuis les coordinators Sentinel."""
    sentinel_data = hass.data.get("sentinel")
    if not sentinel_data:
        _LOGGER.debug("collecteur sentinel : hass.data['sentinel'] introuvable")
        return []

    items = []
    for coordinator in sentinel_data.values():
        if not hasattr(coordinator, "get_all_items"):
            continue
        for item in coordinator.get_all_items():
            if item.healthy:
                continue
            if item.state in _TRANSIENT_STATES:
                continue

            domain = ""
            if hasattr(item, "extra") and item.extra:
                domain = item.extra.get("domain", "") or item.extra.get("source", "").lower()
            if domain in _EXCLUDED_DOMAINS:
                continue

            since_str = ""
            if item.since:
                try:
                    since_str = item.since.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:  # noqa: BLE001
                    since_str = str(item.since)

            # Enrichir avec les données de stabilité si disponibles
            stability_meta = hass.data.get(DATA_KEY_STABILITY, {}).get(item.id)
            extra_info = {}
            if stability_meta:
                extra_info = {
                    "stability_cycles":   stability_meta["cycles"],
                    "stability_duration": stability_meta["duration"],
                    "stability_type":     stability_meta["type"],
                }

            items.append(
                {
                    "id":            item.id,
                    "name":          item.name,
                    "provider":      item.provider,
                    "healthy":       item.healthy,
                    "state":         item.state,
                    "severity":      item.severity,
                    "reason":        item.reason or "",
                    "since":         since_str,
                    "failure_count": item.failure_count,
                    "domain":        domain,
                    **extra_info,
                }
            )
    return items


async def async_setup(
    hass: HomeAssistant,
    stability_delay: int,
    generate_callback: Callable,
) -> None:
    """Initialiser le collecteur Sentinel avec le StabilityWatcher.

    generate_callback : coroutine appelée après expiration du timer de stabilité.
    """
    watcher = StabilityWatcher(hass, stability_delay, generate_callback)
    hass.data[DATA_KEY_STABILITY] = {}
    hass.data[DATA_KEY_RESOLVED] = []

    async def _refresh(updated_item: Any = None) -> None:
        """Collecter les items et notifier le watcher si un item a changé."""
        # Notifier le watcher avant de collecter (pour que les méta soient à jour)
        if updated_item is not None:
            try:
                item_id = updated_item.id
                name = updated_item.name
                is_healthy = updated_item.healthy
                watcher.on_item_update(item_id, name, is_healthy)
            except AttributeError:
                pass  # updated_item peut être None ou ne pas avoir ces attributs

        hass.data[DATA_KEY_SENTINEL] = _collect_items(hass)
        _LOGGER.debug(
            "collecteur sentinel : %d item(s) unhealthy", len(hass.data[DATA_KEY_SENTINEL])
        )

    # Collecte immédiate
    hass.data[DATA_KEY_SENTINEL] = _collect_items(hass)

    @callback
    def _on_sentinel_update(item: Any) -> None:
        hass.async_create_task(_refresh(item))

    async def _on_started(_event: Any) -> None:
        await _refresh()
        async_dispatcher_connect(hass, _SIGNAL_SENTINEL_UPDATE, _on_sentinel_update)
        _LOGGER.debug("collecteur sentinel : abonné au dispatcher '%s'", _SIGNAL_SENTINEL_UPDATE)

    hass.bus.async_listen_once("homeassistant_started", _on_started)
    _LOGGER.info("collecteur sentinel : initialisé (stability_delay=%ds).", stability_delay)
