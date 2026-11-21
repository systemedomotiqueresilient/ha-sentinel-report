"""Sentinel Report — Config Flow UI."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .admin_phone import (
    CONF_ADMIN_NOTIFY_TARGET,
    is_valid_target,
    normalize_target,
    suggest_admin_target,
)
from .const import (
    COMPANION_ALERT_OPTIONS,
    CONF_COMPANION_ALERTS,
    CONF_ENTRY_TITLE,
    CONF_INCLUDE_HA_REPAIRS,
    CONF_INCLUDE_WARNINGS,
    CONF_KEEP_HISTORY,
    CONF_NOTIFY,
    CONF_NOTIFY_THRESHOLD,
    CONF_PURGE_KEEP_DAYS,
    CONF_PURGE_KEEP_FILES,
    CONF_PURGE_MODE,
    CONF_REPORT_FILE,
    CONF_REPORT_PATH,
    CONF_STABILITY_DELAY,
    CONFIG_MINOR_VERSION,
    DEFAULT_COMPANION_ALERTS,
    DEFAULT_INCLUDE_HA_REPAIRS,
    DEFAULT_INCLUDE_WARNINGS,
    DEFAULT_KEEP_HISTORY,
    DEFAULT_NOTIFY,
    DEFAULT_NOTIFY_THRESHOLD,
    DEFAULT_PURGE_KEEP_DAYS,
    DEFAULT_PURGE_KEEP_FILES,
    DEFAULT_PURGE_MODE,
    DEFAULT_REPORT_FILE,
    DEFAULT_REPORT_PATH,
    DEFAULT_STABILITY_DELAY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

NOTIFY_THRESHOLD_OPTIONS = ["errors_only", "all"]
PURGE_MODE_OPTIONS = ["disabled", "keep_files", "keep_days"]

STABILITY_DELAY_MIN = 60
STABILITY_DELAY_MAX = 3600


def _validate_inputs(
    report_path: str,
    report_file: str,
    stability_delay: int,
) -> str | None:
    """Valider les champs principaux."""
    if not report_path.startswith("/"):
        return "path_not_absolute"
    if not report_file.strip():
        return "filename_empty"
    if "/" in report_file:
        return "filename_has_slash"
    if stability_delay < STABILITY_DELAY_MIN:
        return "stability_delay_too_low"
    if stability_delay > STABILITY_DELAY_MAX:
        return "stability_delay_too_high"
    return None


def _validate_target(value: Any) -> str | None:
    """Valider le téléphone admin : vide accepté, sinon « notify.xxx » (service ou entité)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return None if is_valid_target(value) else "invalid_target"


def _build_schema(
    hass: HomeAssistant | None,
    current: dict,
) -> vol.Schema:
    """Construire le schéma avec les selectors HA natifs."""

    # Téléphone admin : valeur courante prioritaire, sinon celle déjà choisie dans une
    # intégration sœur (une seule valeur), sinon la liste des services/entités mobiles.
    current_target = current.get(CONF_ADMIN_NOTIFY_TARGET)
    if hass is not None:
        admin_default, admin_choices = suggest_admin_target(hass, current_target)
    else:
        admin_default, admin_choices = normalize_target(current_target), []
    admin_key = (
        vol.Optional(CONF_ADMIN_NOTIFY_TARGET, description={"suggested_value": admin_default})
        if admin_default
        else vol.Optional(CONF_ADMIN_NOTIFY_TARGET)
    )

    companion_alerts = current.get(CONF_COMPANION_ALERTS, list(DEFAULT_COMPANION_ALERTS))
    if not isinstance(companion_alerts, list):
        companion_alerts = []
    companion_alerts = [a for a in companion_alerts if a in COMPANION_ALERT_OPTIONS]

    return vol.Schema(
        {
            vol.Required(
                CONF_REPORT_PATH,
                default=current.get(CONF_REPORT_PATH, DEFAULT_REPORT_PATH),
            ): selector.selector({"text": {}}),

            vol.Required(
                CONF_REPORT_FILE,
                default=current.get(CONF_REPORT_FILE, DEFAULT_REPORT_FILE),
            ): selector.selector({"text": {}}),

            vol.Required(
                CONF_INCLUDE_WARNINGS,
                default=current.get(CONF_INCLUDE_WARNINGS, DEFAULT_INCLUDE_WARNINGS),
            ): selector.selector({"boolean": {}}),

            vol.Required(
                CONF_KEEP_HISTORY,
                default=current.get(CONF_KEEP_HISTORY, DEFAULT_KEEP_HISTORY),
            ): selector.selector({"boolean": {}}),

            vol.Required(
                CONF_INCLUDE_HA_REPAIRS,
                default=current.get(CONF_INCLUDE_HA_REPAIRS, DEFAULT_INCLUDE_HA_REPAIRS),
            ): selector.selector({"boolean": {}}),

            vol.Required(
                CONF_NOTIFY,
                default=current.get(CONF_NOTIFY, DEFAULT_NOTIFY),
            ): selector.selector({"boolean": {}}),

            vol.Required(
                CONF_NOTIFY_THRESHOLD,
                default=current.get(CONF_NOTIFY_THRESHOLD, DEFAULT_NOTIFY_THRESHOLD),
            ): selector.selector({
                "select": {
                    "options": NOTIFY_THRESHOLD_OPTIONS,
                    "translation_key": "notify_threshold",
                }
            }),

            vol.Required(
                CONF_PURGE_MODE,
                default=current.get(CONF_PURGE_MODE, DEFAULT_PURGE_MODE),
            ): selector.selector({
                "select": {
                    "options": PURGE_MODE_OPTIONS,
                    "translation_key": "purge_mode",
                }
            }),

            vol.Required(
                CONF_PURGE_KEEP_FILES,
                default=current.get(CONF_PURGE_KEEP_FILES, DEFAULT_PURGE_KEEP_FILES),
            ): selector.selector({
                "number": {"min": 1, "max": 365, "mode": "box"}
            }),

            vol.Required(
                CONF_PURGE_KEEP_DAYS,
                default=current.get(CONF_PURGE_KEEP_DAYS, DEFAULT_PURGE_KEEP_DAYS),
            ): selector.selector({
                "number": {"min": 1, "max": 365, "mode": "box"}
            }),

            vol.Required(
                CONF_STABILITY_DELAY,
                default=current.get(CONF_STABILITY_DELAY, DEFAULT_STABILITY_DELAY),
            ): selector.selector({
                "number": {
                    "min": STABILITY_DELAY_MIN,
                    "max": STABILITY_DELAY_MAX,
                    "mode": "box",
                    "unit_of_measurement": "s",
                }
            }),

            admin_key: selector.selector({
                "select": {
                    "options": admin_choices,
                    "custom_value": True,
                    "mode": "dropdown",
                }
            }),

            vol.Optional(
                CONF_COMPANION_ALERTS,
                default=companion_alerts,
            ): selector.selector({
                "select": {
                    "multiple": True,
                    "options": COMPANION_ALERT_OPTIONS,
                    "translation_key": "companion_alerts",
                }
            }),
        }
    )


def _get_current(entry: config_entries.ConfigEntry) -> dict:
    """Fusionner data + options avec les défauts v0.6.1."""
    defaults = {
        CONF_STABILITY_DELAY:     DEFAULT_STABILITY_DELAY,
        CONF_ADMIN_NOTIFY_TARGET: None,
        CONF_COMPANION_ALERTS:    list(DEFAULT_COMPANION_ALERTS),
    }
    return {**defaults, **entry.data, **entry.options}


class SentinelReportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pour Sentinel Report."""

    VERSION = 1
    MINOR_VERSION = CONFIG_MINOR_VERSION

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        current: dict = {
            CONF_REPORT_PATH:      DEFAULT_REPORT_PATH,
            CONF_REPORT_FILE:      DEFAULT_REPORT_FILE,
            CONF_INCLUDE_WARNINGS: DEFAULT_INCLUDE_WARNINGS,
            CONF_KEEP_HISTORY:     DEFAULT_KEEP_HISTORY,
            CONF_NOTIFY:           DEFAULT_NOTIFY,
            CONF_NOTIFY_THRESHOLD: DEFAULT_NOTIFY_THRESHOLD,
            CONF_PURGE_MODE:       DEFAULT_PURGE_MODE,
            CONF_PURGE_KEEP_FILES: DEFAULT_PURGE_KEEP_FILES,
            CONF_PURGE_KEEP_DAYS:  DEFAULT_PURGE_KEEP_DAYS,
            CONF_STABILITY_DELAY:  DEFAULT_STABILITY_DELAY,
            CONF_ADMIN_NOTIFY_TARGET: None,
            CONF_COMPANION_ALERTS: list(DEFAULT_COMPANION_ALERTS),
        }

        if user_input is not None:
            error = _validate_inputs(
                user_input.get(CONF_REPORT_PATH, ""),
                user_input.get(CONF_REPORT_FILE, ""),
                user_input.get(CONF_STABILITY_DELAY, DEFAULT_STABILITY_DELAY),
            )
            target_error = _validate_target(user_input.get(CONF_ADMIN_NOTIFY_TARGET))
            if error:
                errors["base"] = error
            elif target_error:
                errors[CONF_ADMIN_NOTIFY_TARGET] = target_error
            else:
                await self._async_allowlist_path(user_input[CONF_REPORT_PATH])
                data = {
                    **user_input,
                    CONF_ADMIN_NOTIFY_TARGET: normalize_target(
                        user_input.get(CONF_ADMIN_NOTIFY_TARGET)
                    ),
                }
                return self.async_create_entry(title=CONF_ENTRY_TITLE, data=data)
            current = {**current, **user_input}

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(hass=self.hass, current=current),
            errors=errors,
        )

    async def _async_allowlist_path(self, path: str) -> None:
        try:
            p = Path(path)
            if p not in self.hass.config.allowlist_external_dirs:
                self.hass.config.allowlist_external_dirs.add(p)
                _LOGGER.info("Sentinel Report : '%s' ajouté à allowlist_external_dirs", path)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "Sentinel Report : impossible d'ajouter '%s' à allowlist_external_dirs : %s",
                path, exc,
            )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SentinelReportOptionsFlow:
        return SentinelReportOptionsFlow()


class SentinelReportOptionsFlow(config_entries.OptionsFlow):
    """Options flow — modifier la configuration après installation."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        current = _get_current(self.config_entry)

        if user_input is not None:
            error = _validate_inputs(
                user_input.get(CONF_REPORT_PATH, ""),
                user_input.get(CONF_REPORT_FILE, ""),
                user_input.get(CONF_STABILITY_DELAY, DEFAULT_STABILITY_DELAY),
            )
            target_error = _validate_target(user_input.get(CONF_ADMIN_NOTIFY_TARGET))
            if error:
                errors["base"] = error
            elif target_error:
                errors[CONF_ADMIN_NOTIFY_TARGET] = target_error
            else:
                if user_input.get(CONF_REPORT_PATH) != current.get(CONF_REPORT_PATH):
                    await self._async_allowlist_path(user_input[CONF_REPORT_PATH])
                # Le téléphone admin vit dans entry.data (convention commune SDR), les
                # autres réglages dans entry.options. Champ vidé = non défini (None).
                options = dict(user_input)
                target = normalize_target(options.pop(CONF_ADMIN_NOTIFY_TARGET, None))
                if target != normalize_target(self.config_entry.data.get(CONF_ADMIN_NOTIFY_TARGET)):
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data={**self.config_entry.data, CONF_ADMIN_NOTIFY_TARGET: target},
                    )
                return self.async_create_entry(title="", data=options)
            current = {**current, **user_input}

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(hass=self.hass, current=current),
            errors=errors,
        )

    async def _async_allowlist_path(self, path: str) -> None:
        try:
            p = Path(path)
            if p not in self.hass.config.allowlist_external_dirs:
                self.hass.config.allowlist_external_dirs.add(p)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "Sentinel Report : impossible d'ajouter '%s' à allowlist_external_dirs : %s",
                path, exc,
            )
