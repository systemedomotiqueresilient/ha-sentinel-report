"""Sentinel Report — Sensor HA.

Expose un sensor `sensor.sentinel_report_problems` avec le nombre total
de problèmes détectés (Sentinel + Spook) et les détails en attributs.
Mis à jour à chaque génération du rapport via un dispatcher interne.
Compatible config flow (async_setup_entry) et yaml legacy (async_setup_platform).
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)

# Signal interne pour notifier le sensor après chaque génération
SIGNAL_REPORT_UPDATED = f"{DOMAIN}_report_updated"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configurer le sensor via config entry (config flow UI)."""
    async_add_entities([SentinelReportSensor()], update_before_add=False)
    _LOGGER.debug("sentinel_report : sensor ajouté (config entry)")


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Configurer le sensor via discovery (yaml legacy)."""
    async_add_entities([SentinelReportSensor()], update_before_add=False)
    _LOGGER.debug("sentinel_report : sensor ajouté (yaml legacy)")


class SentinelReportSensor(SensorEntity):
    """Sensor exposant le nombre total de problèmes Sentinel + Spook."""

    _attr_name = "Sentinel Report Problems"
    _attr_unique_id = "sentinel_report_problems"
    _attr_icon = "mdi:shield-alert"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "problems"
    _attr_should_poll = False

    def __init__(self) -> None:
        """Initialiser le sensor."""
        self._total: int = 0
        self._sentinel_errors: int = 0
        self._sentinel_warnings: int = 0
        self._spook_issues: int = 0
        self._last_generated: str = "never"
        self._report_path: str = ""
        self._spook_available: bool = False

    @property
    def native_value(self) -> int:
        """Nombre total de problèmes."""
        return self._total

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributs détaillés exposés dans HA."""
        attrs: dict[str, Any] = {
            "sentinel_errors":   self._sentinel_errors,
            "sentinel_warnings": self._sentinel_warnings,
            "last_generated":    self._last_generated,
            "report_path":       self._report_path,
            "version":           VERSION,
        }
        if self._spook_available:
            attrs["spook_issues"] = self._spook_issues
        return attrs

    async def async_added_to_hass(self) -> None:
        """S'abonner au signal de mise à jour du rapport."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_REPORT_UPDATED,
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self, data: dict[str, Any]) -> None:
        """Mettre à jour le sensor avec les nouvelles données du rapport."""
        self._total             = data.get("total", 0)
        self._sentinel_errors   = data.get("sentinel_errors", 0)
        self._sentinel_warnings = data.get("sentinel_warnings", 0)
        self._spook_issues      = data.get("spook_issues", 0)
        self._last_generated    = data.get("last_generated", "unknown")
        self._report_path       = data.get("report_path", "")
        self._spook_available   = data.get("spook_available", False)
        self.async_write_ha_state()
        _LOGGER.debug(
            "sentinel_report sensor mis à jour : %d problème(s) total", self._total
        )
