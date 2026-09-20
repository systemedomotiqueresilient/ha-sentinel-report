"""Config flow minimal pour sentinel_report_sentinel.

Permet la création programmatique d'une config entry par sentinel_report.
Aucun formulaire utilisateur — l'entrée est créée automatiquement.
"""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

DOMAIN = "sentinel_report_sentinel"


class SentinelReportSentinelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pour sentinel_report_sentinel — création automatique uniquement."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Pas de formulaire — entrée créée programmatiquement par sentinel_report."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title="Sentinel Report — Collecteur Sentinel", data={})
