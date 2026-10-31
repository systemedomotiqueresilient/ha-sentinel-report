"""Collecteur Sentinel — module interne de sentinel_report.

v0.7.0 : source principale = événement public ``sentinel_item_changed``
(contrat recommandé par l'auteur de Sentinel). L'état initial est obtenu via
le service public ``sentinel.check``, qui ré-émet un événement pour chaque
élément en défaut.

Repli « au mieux » : si les événements sont désactivés dans Sentinel (option
``fire_events``) ou si le service est introuvable, on relit
``hass.data["sentinel"]`` et le signal ``sentinel_update``. Ce sont des
détails d'implémentation de Sentinel, sans garantie de stabilité.

Les données sont déposées dans hass.data[DATA_KEY_SENTINEL] (liste de dict).
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util

from ..const import (
    DATA_KEY_RESOLVED,
    DATA_KEY_SENTINEL,
    DATA_KEY_STABILITY,
    STABILITY_MIN_CYCLES,
)

_LOGGER = logging.getLogger(__name__)

# Contrat public de Sentinel (https://github.com/GuiPoM/ha-sentinel)
_SENTINEL_DOMAIN = "sentinel"
_EVENT_ITEM_CHANGED = "sentinel_item_changed"
_SERVICE_CHECK = "check"
_CONF_FIRE_EVENTS = "fire_events"

# Détail d'implémentation de Sentinel — utilisé uniquement pour le repli
_SIGNAL_SENTINEL_UPDATE = "sentinel_update"

_REASON_NOT_CONFIGURED = "Sentinel n'est pas configuré"

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
        on_stability_change: Callable[[], None] | None = None,
    ) -> None:
        self._hass = hass
        self._delay = stability_delay
        self._generate_cb = generate_callback
        # Appelé quand les métadonnées de stabilité changent, pour que la
        # liste d'items publiée soit enrichie avant la génération du rapport.
        self._on_stability_change = on_stability_change
        # {item_id: {"cycles": int, "first_failure": datetime, "last_healthy": bool, "timer": Task}}
        self._watched: dict[str, dict] = {}

    def on_item_update(self, item_id: str, name: str, is_healthy: bool) -> None:
        """Appelé à chaque changement d'état d'un item Sentinel."""
        now = datetime.now()

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
        duration = datetime.now() - first_failure
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
                    "resolved_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
            # Republier la liste pour que l'item porte ces métadonnées
            # au moment où le rapport est généré.
            if self._on_stability_change is not None:
                self._on_stability_change()

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

    def cancel_all(self) -> None:
        """Annuler tous les timers en cours (déchargement de l'intégration)."""
        for entry in self._watched.values():
            timer = entry.get("timer")
            if timer is not None and not timer.done():
                timer.cancel()
        self._watched.clear()


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


# ── Conversion des données ───────────────────────────────────────────────────

def _format_since(value: Any) -> str:
    """Formater un horodatage Sentinel en heure locale (AAAA-MM-JJ HH:MM:SS).

    Accepte un datetime ou une chaîne ISO 8601. Un horodatage sans fuseau est
    considéré comme déjà local (comportement de dt_util.as_local).
    """
    if not value:
        return ""
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return str(value)
    return dt_util.as_local(parsed).strftime("%Y-%m-%d %H:%M:%S")


def _stability_extra(hass: HomeAssistant, item_id: str) -> dict[str, Any]:
    """Métadonnées de stabilité à ajouter à un item, si elles existent."""
    meta = hass.data.get(DATA_KEY_STABILITY, {}).get(item_id)
    if not meta:
        return {}
    return {
        "stability_cycles":   meta["cycles"],
        "stability_duration": meta["duration"],
        "stability_type":     meta["type"],
    }


def _item_from_event(data: Mapping[str, Any]) -> dict[str, Any]:
    """Convertir le payload de sentinel_item_changed en item de rapport."""
    return {
        "id":            data.get("item_id", ""),
        "name":          data.get("name", "?"),
        "provider":      data.get("provider", "unknown"),
        "healthy":       bool(data.get("healthy", False)),
        "state":         data.get("state", "?"),
        "severity":      data.get("severity", "warning"),
        "reason":        data.get("reason") or "",
        "since":         _format_since(data.get("since")),
        "failure_count": data.get("failure_count", 0),
        "domain":        data.get("domain", ""),
    }


# ── Repli : lecture de hass.data["sentinel"] (API non officielle) ────────────

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

            items.append(
                {
                    "id":            item.id,
                    "name":          item.name,
                    "provider":      item.provider,
                    "healthy":       item.healthy,
                    "state":         item.state,
                    "severity":      item.severity,
                    "reason":        item.reason or "",
                    "since":         _format_since(item.since),
                    "failure_count": item.failure_count,
                    "domain":        domain,
                    **_stability_extra(hass, item.id),
                }
            )
    return items


# ── Choix du mode ────────────────────────────────────────────────────────────

def _events_unavailable_reason(hass: HomeAssistant) -> str | None:
    """Raison pour laquelle le mode événements est inutilisable, ou None."""
    entries = hass.config_entries.async_entries(_SENTINEL_DOMAIN)
    if not entries:
        return _REASON_NOT_CONFIGURED
    for entry in entries:
        options = {**entry.data, **entry.options}
        if not options.get(_CONF_FIRE_EVENTS, True):
            return "l'option « fire_events » est désactivée dans Sentinel"
    if not hass.services.has_service(_SENTINEL_DOMAIN, _SERVICE_CHECK):
        return "le service sentinel.check est introuvable"
    return None


# ── Setup ────────────────────────────────────────────────────────────────────

async def async_setup(
    hass: HomeAssistant,
    stability_delay: int,
    generate_callback: Callable,
) -> Callable[[], None]:
    """Initialiser le collecteur Sentinel avec le StabilityWatcher.

    generate_callback : coroutine appelée après expiration du timer de stabilité.

    Retourne une fonction de désabonnement, à enregistrer avec
    ``entry.async_on_unload`` pour éviter les écouteurs en double lors d'un
    rechargement de l'intégration.
    """
    hass.data[DATA_KEY_STABILITY] = {}
    hass.data[DATA_KEY_RESOLVED] = []
    hass.data[DATA_KEY_SENTINEL] = []

    reason = _events_unavailable_reason(hass)
    use_events = reason is None
    items: dict[str, dict[str, Any]] = {}
    # watch : le StabilityWatcher n'est alimenté qu'une fois HA démarré, pour
    # ne pas compter les oscillations normales du démarrage comme des cycles.
    # snapshot : True pendant sentinel.check — ces événements sont un état
    # initial, pas un changement réel.
    flags = {"watch": hass.state == CoreState.running, "snapshot": False}
    unsubs: list[Callable[[], None]] = []

    @callback
    def _publish() -> None:
        if use_events:
            hass.data[DATA_KEY_SENTINEL] = [
                {**item, **_stability_extra(hass, item["id"])} for item in items.values()
            ]
        else:
            hass.data[DATA_KEY_SENTINEL] = _collect_items(hass)

    watcher = StabilityWatcher(
        hass, stability_delay, generate_callback, on_stability_change=_publish
    )

    @callback
    def _on_item_changed(event: Event) -> None:
        """Événement public sentinel_item_changed."""
        data = event.data
        item_id = data.get("item_id")
        if not item_id:
            return
        domain = data.get("domain", "")
        excluded = domain in _EXCLUDED_DOMAINS
        healthy = bool(data.get("healthy", False))

        if flags["watch"] and not flags["snapshot"] and not excluded:
            watcher.on_item_update(item_id, data.get("name", item_id), healthy)

        if healthy:
            # Incident terminé : les anciennes métadonnées ne s'appliquent plus.
            hass.data.get(DATA_KEY_STABILITY, {}).pop(item_id, None)

        if healthy or excluded or data.get("state") in _TRANSIENT_STATES:
            items.pop(item_id, None)
        else:
            items[item_id] = _item_from_event(data)
        _publish()

    @callback
    def _on_sentinel_update(item: Any) -> None:
        """Signal sentinel_update (repli, API non officielle)."""
        item_id = getattr(item, "id", None)
        if flags["watch"] and item_id is not None:
            watcher.on_item_update(
                item_id,
                getattr(item, "name", item_id),
                bool(getattr(item, "healthy", False)),
            )
        _publish()

    async def _snapshot() -> None:
        """Demander à Sentinel de ré-émettre un événement par item en défaut."""
        flags["snapshot"] = True
        try:
            await hass.services.async_call(
                _SENTINEL_DOMAIN, _SERVICE_CHECK, {}, blocking=True
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "collecteur sentinel : sentinel.check a échoué (%s) — "
                "instantané de repli via hass.data",
                exc,
            )
            for item in _collect_items(hass):
                items.setdefault(item["id"], item)
        finally:
            flags["snapshot"] = False
        _publish()

    if use_events:
        unsubs.append(hass.bus.async_listen(_EVENT_ITEM_CHANGED, _on_item_changed))
        await _snapshot()
    else:
        if reason == _REASON_NOT_CONFIGURED:
            _LOGGER.debug("collecteur sentinel : %s — aucune donnée Sentinel.", reason)
        else:
            _LOGGER.warning(
                "collecteur sentinel : %s — repli sur hass.data['sentinel'] "
                "(API non officielle de Sentinel, sans garantie de stabilité).",
                reason,
            )
        unsubs.append(
            async_dispatcher_connect(hass, _SIGNAL_SENTINEL_UPDATE, _on_sentinel_update)
        )
        _publish()

    if hass.state != CoreState.running:

        async def _on_started(_event: Event) -> None:
            flags["watch"] = True
            if use_events:
                await _snapshot()
            else:
                _publish()

        hass.bus.async_listen_once("homeassistant_started", _on_started)

    @callback
    def _unsubscribe() -> None:
        for unsub in unsubs:
            unsub()
        unsubs.clear()
        watcher.cancel_all()

    _LOGGER.info(
        "collecteur sentinel : initialisé (mode %s, stability_delay=%ds).",
        "événements" if use_events else "repli hass.data",
        stability_delay,
    )
    return _unsubscribe
