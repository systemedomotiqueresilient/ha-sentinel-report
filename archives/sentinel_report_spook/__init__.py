"""Sentinel Report — Collecteur Spook.

Chargé automatiquement par sentinel_report via une config entry programmatique.
Plus besoin de déclaration dans configuration.yaml.

Lit les issues du repair registry de Home Assistant filtrées sur le domaine
"spook" et les dépose dans hass.data[DATA_KEY_SPOOK] pour l'orchestrateur.

Dépend de : spook (frenck/spook)
Ne modifie pas spook — lecture seule via l'API publique HA issue_registry.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

# Import absolu — les custom_components sont des packages Python séparés
from custom_components.sentinel_report.const import DATA_KEY_SPOOK

_LOGGER = logging.getLogger(__name__)

DOMAIN = "sentinel_report_spook"
_SPOOK_DOMAIN = "spook"


def _normalize_severity(severity: Any) -> str:
    """Normaliser la sévérité en 'error' ou 'warning'."""
    if severity is None:
        return "warning"
    raw = severity.value if hasattr(severity, "value") else str(severity)
    raw = raw.lower()
    if raw in ("error", "critical"):
        return "error"
    return "warning"


def _flatten_placeholder(value: str) -> str:
    """Aplatir une valeur de placeholder multi-lignes en une seule ligne.

    Spook génère certains placeholders en liste markdown :
      - `entity_id_1`
      - `entity_id_2`
    Dans Spook 5.1.0, certaines listes incluent des tokens supplémentaires
    comme le domaine de l'appareil (ex: `light.salon`, `mqtt`). On filtre
    les tokens qui ne contiennent pas de '.' car ce sont des domaines HA seuls.
    """
    tokens = re.findall(r"`([^`]+)`", value)
    if tokens:
        # Garder uniquement les tokens qui ressemblent à un entity_id ou chemin
        # (contiennent '.', '/' ou un espace) — filtrer les domaines seuls (mqtt, tuya...)
        meaningful = [t for t in tokens if "." in t or "/" in t or " " in t]
        return ", ".join(meaningful if meaningful else tokens)
    flat = re.sub(r"\s*\n\s*-\s*", ", ", value.strip())
    flat = re.sub(r"^-\s*", "", flat)
    return flat.strip()


def _build_label(key: str, placeholders: dict[str, str]) -> str:
    """Construire un label lisible sur une seule ligne depuis les placeholders."""
    if not placeholders:
        return f"[{key}]"

    preferred_order = [
        "integration",   # dead_entities
        "domain",        # unused_blueprints (automation/script)
        "blueprint",     # unused_blueprints
        "dashboard",     # lovelace repairs
        "automation",    # automation repairs
        "script",        # script repairs
        "token",         # stale_access_tokens
        "owner",         # stale_access_tokens
        "last_active",   # stale_access_tokens
        "entity_id",     # script/automation service references
    ]
    list_keys = {
        "entities",    # lovelace + script + automation entity refs
        "services",    # script/automation service refs
        "integrations",# integration repairs
        "blueprints",  # unused blueprints
        "areas",       # lovelace area refs (v5.1.0)
        "resources",   # lovelace missing resources (v5.1.0)
        "triggers",    # script/automation trigger refs (v5.1.0)
        "conditions",  # script/automation condition refs (v5.1.0)
    }

    parts = [f"[{key}]"]
    for k in preferred_order:
        if k in placeholders:
            parts.append(f"{k}: {placeholders[k]}")
    for k in sorted(placeholders.keys()):
        if k in list_keys:
            parts.append(f"{k}: {_flatten_placeholder(placeholders[k])}")

    return " — ".join(parts)


def _collect_issues(hass: HomeAssistant) -> list[dict]:
    """Lire les issues Spook depuis le repair/issue registry de HA."""
    issues = []
    try:
        from homeassistant.helpers import issue_registry as ir
        registry = ir.async_get(hass)
        for issue in registry.issues.values():
            if issue.domain != _SPOOK_DOMAIN:
                continue
            if issue.dismissed_version is not None:
                continue

            placeholders = dict(issue.translation_placeholders or {})
            key = issue.translation_key or issue.issue_id
            severity = _normalize_severity(issue.severity)
            label = _build_label(key, placeholders)

            issues.append(
                {
                    "issue_id":   issue.issue_id,
                    "domain":     issue.domain,
                    "severity":   severity,
                    "label":      label,
                    "is_fixable": issue.is_fixable,
                }
            )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning(
            "sentinel_report_spook : impossible de lire le issue registry : %s", exc
        )
    return issues


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialiser le collecteur Spook depuis une config entry."""

    async def _refresh(_event: Any = None) -> None:
        """Collecter et déposer les issues dans hass.data."""
        issues = _collect_issues(hass)
        hass.data[DATA_KEY_SPOOK] = issues
        _LOGGER.debug(
            "sentinel_report_spook : %d issue(s) collectée(s)", len(issues)
        )

    # Collecte immédiate dès le setup — sans attendre homeassistant_started
    hass.data[DATA_KEY_SPOOK] = _collect_issues(hass)
    _LOGGER.debug(
        "sentinel_report_spook : collecte initiale — %d issue(s)",
        len(hass.data[DATA_KEY_SPOOK]),
    )

    @callback
    def _on_registry_updated(event: Any) -> None:
        """Callback event loop — non-bloquant."""
        hass.async_create_task(_refresh())

    async def _on_started(_event: Any) -> None:
        """Au démarrage : recollecte + abonnement aux changements du registry."""
        await _refresh()
        hass.bus.async_listen(
            "repairs_issue_registry_updated",
            _on_registry_updated,
        )

    hass.bus.async_listen_once("homeassistant_started", _on_started)

    _LOGGER.info("sentinel_report_spook : collecteur Spook initialisé.")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharger la config entry."""
    hass.data.pop(DATA_KEY_SPOOK, None)
    return True
