"""Collecteur HA Repairs — module interne de sentinel_report.

Lit toutes les issues du repair registry de Home Assistant (deprecated warnings,
configurations obsolètes, migrations en attente) en excluant le domaine "spook"
(géré par son propre collecteur) et les issues ignorées par l'utilisateur.

Permet de détecter proactivement les problèmes qui casseront une future
mise à jour de Home Assistant.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback

from ..const import DATA_KEY_HA_REPAIRS, HA_REPAIRS_EXCLUDED_DOMAINS

_LOGGER = logging.getLogger(__name__)

# Severités HA → label normalisé
_SEVERITY_MAP = {
    "error":    "error",
    "critical": "error",
    "warning":  "warning",
    "warn":     "warning",
}


def _normalize_severity(severity: Any) -> str:
    """Normaliser la sévérité HA en 'error' ou 'warning'."""
    if severity is None:
        return "warning"
    raw = severity.value if hasattr(severity, "value") else str(severity)
    return _SEVERITY_MAP.get(raw.lower(), "warning")


def _build_label(issue: Any) -> str:
    """Construire un label lisible pour une issue HA Repair."""
    domain = issue.domain or "homeassistant"
    key = issue.translation_key or issue.issue_id or "unknown"
    placeholders = dict(issue.translation_placeholders or {})

    # Construire une description lisible à partir des placeholders
    # Les issues HA Core ont souvent : integration, platform, config_key, url
    parts = [f"[{domain}/{key}]"]

    # Placeholders utiles dans l'ordre de priorité
    priority_keys = ["integration", "platform", "config_key", "name", "entity_id", "service", "error", "deprecated_behavior", "new_behavior", "domain", "integration_title"]
    for k in priority_keys:
        if k in placeholders:
            parts.append(f"{k}: {placeholders[k]}")

    # Ajouter les clés restantes pertinentes
    # Exclure : URLs internes, ids techniques, clés déjà traitées
    skip_keys = set(priority_keys) | {"url", "learn_more_url", "issue_id", "edit"}
    for k, v in placeholders.items():
        if k not in skip_keys and v and len(str(v)) < 100:
            parts.append(f"{k}: {v}")

    return " — ".join(parts)


def _collect_issues(hass: HomeAssistant) -> list[dict]:
    """Lire les HA Repairs depuis l'issue registry."""
    issues = []
    try:
        from homeassistant.helpers import issue_registry as ir
        registry = ir.async_get(hass)

        for issue in registry.issues.values():
            # Exclure les domaines gérés par d'autres collecteurs
            if issue.domain in HA_REPAIRS_EXCLUDED_DOMAINS:
                continue
            # Exclure les issues ignorées par l'utilisateur
            if issue.dismissed_version is not None:
                continue

            severity = _normalize_severity(issue.severity)
            label = _build_label(issue)

            issues.append(
                {
                    "issue_id":       issue.issue_id,
                    "domain":         issue.domain,
                    "severity":       severity,
                    "label":          label,
                    "is_fixable":     issue.is_fixable,
                    "breaks_in_ha":   getattr(issue, "breaks_in_ha_version", None),
                    "learn_more_url": (issue.translation_placeholders or {}).get(
                        "learn_more_url", ""
                    ) if issue.translation_placeholders else "",
                }
            )
            _LOGGER.debug(
                "collecteur ha_repairs : issue — %s/%s | sévérité: %s | breaks_in: %s",
                issue.domain,
                issue.issue_id,
                severity,
                getattr(issue, "breaks_in_ha_version", "?"),
            )

    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning(
            "collecteur ha_repairs : impossible de lire le issue registry : %s", exc
        )

    # Trier : errors en premier, puis par domaine
    issues.sort(key=lambda x: (0 if x["severity"] == "error" else 1, x["domain"]))
    return issues


async def async_setup(hass: HomeAssistant) -> None:
    """Initialiser le collecteur HA Repairs.

    Toujours disponible — ne dépend d'aucune intégration tierce.
    Collecte différée au homeassistant_started pour que le registry soit complet.
    """
    # Initialiser à liste vide pour signaler que le collecteur est actif
    hass.data[DATA_KEY_HA_REPAIRS] = []
    _LOGGER.debug("collecteur ha_repairs : initialisé, collecte différée.")

    async def _refresh(_event: Any = None) -> None:
        hass.data[DATA_KEY_HA_REPAIRS] = _collect_issues(hass)
        _LOGGER.debug(
            "collecteur ha_repairs : %d issue(s) collectée(s)",
            len(hass.data[DATA_KEY_HA_REPAIRS]),
        )

    @callback
    def _on_registry_updated(event: Any) -> None:
        hass.async_create_task(_refresh())

    async def _on_started(_event: Any) -> None:
        await _refresh()
        hass.bus.async_listen("repairs_issue_registry_updated", _on_registry_updated)

    hass.bus.async_listen_once("homeassistant_started", _on_started)
    _LOGGER.info("collecteur ha_repairs : initialisé.")
