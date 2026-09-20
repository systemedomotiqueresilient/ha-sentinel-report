"""Sentinel Report — Collecteur Sentinel.

Chargé automatiquement par sentinel_report via une config entry programmatique.
Plus besoin de déclaration dans configuration.yaml.

Lit les données du coordinator de GuiPoM/ha-sentinel via hass.data["sentinel"]
et les dépose dans hass.data[DATA_KEY_SENTINEL] pour que l'orchestrateur
sentinel_report puisse les consommer.

Dépend de : sentinel (GuiPoM/ha-sentinel)
Ne modifie pas sentinel — lecture seule.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

# Import absolu — les custom_components sont des packages Python séparés
from custom_components.sentinel_report.const import DATA_KEY_SENTINEL

_LOGGER = logging.getLogger(__name__)

DOMAIN = "sentinel_report_sentinel"

# Signal dispatcher émis par ha-sentinel (GuiPoM) à chaque changement
_SIGNAL_SENTINEL_UPDATE = "sentinel_update"

# États transitoires au démarrage — pas des vrais problèmes
_TRANSIENT_STATES = {"not_loaded", "setup_in_progress", "loading"}

# Domaines à exclure du rapport — Sentinel Report lui-même
_EXCLUDED_DOMAINS = {
    "sentinel_report",
    "sentinel_report_sentinel",
    "sentinel_report_spook",
}


def _collect_items(hass: HomeAssistant) -> list[dict]:
    """Extraire les items unhealthy depuis les coordinators Sentinel."""
    sentinel_data = hass.data.get("sentinel")
    if not sentinel_data:
        _LOGGER.debug(
            "sentinel_report_sentinel : hass.data['sentinel'] introuvable "
            "(Sentinel pas encore chargé ou aucun item)"
        )
        return []

    items = []
    for coordinator in sentinel_data.values():
        if not hasattr(coordinator, "get_all_items"):
            continue
        for item in coordinator.get_all_items():
            if item.healthy:
                continue

            # Ignorer les états transitoires du démarrage
            if item.state in _TRANSIENT_STATES:
                continue

            # Ignorer Sentinel Report lui-même
            domain = ""
            if hasattr(item, "extra") and item.extra:
                domain = item.extra.get("domain", "") or item.extra.get("source", "").lower()

            if domain in _EXCLUDED_DOMAINS:
                continue

            since_str = ""
            if item.since:
                try:
                    since_str = item.since.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    since_str = str(item.since)

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
                }
            )
    return items


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialiser le collecteur Sentinel depuis une config entry."""

    async def _refresh(_item: Any = None) -> None:
        """Collecter et déposer les items dans hass.data."""
        items = _collect_items(hass)
        hass.data[DATA_KEY_SENTINEL] = items
        _LOGGER.debug(
            "sentinel_report_sentinel : %d item(s) unhealthy collecté(s)", len(items)
        )

    # Collecte immédiate dès le setup
    hass.data[DATA_KEY_SENTINEL] = _collect_items(hass)
    _LOGGER.debug(
        "sentinel_report_sentinel : collecte initiale — %d item(s)",
        len(hass.data[DATA_KEY_SENTINEL]),
    )

    @callback
    def _on_sentinel_update(item: Any) -> None:
        """Callback dispatcher Sentinel — non-bloquant."""
        hass.async_create_task(_refresh(item))

    async def _on_started(_event: Any) -> None:
        """Au démarrage : recollecte + abonnement au dispatcher temps réel."""
        await _refresh()
        async_dispatcher_connect(hass, _SIGNAL_SENTINEL_UPDATE, _on_sentinel_update)
        _LOGGER.debug(
            "sentinel_report_sentinel : abonné au dispatcher '%s'",
            _SIGNAL_SENTINEL_UPDATE,
        )

    hass.bus.async_listen_once("homeassistant_started", _on_started)

    _LOGGER.info("sentinel_report_sentinel : collecteur Sentinel initialisé.")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharger la config entry."""
    hass.data.pop(DATA_KEY_SENTINEL, None)
    return True
