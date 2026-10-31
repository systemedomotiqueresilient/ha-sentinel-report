"""Tests : les issues « fantômes » du registre (active=False) sont ignorées.

Au démarrage, Home Assistant recharge depuis son stockage les issues non
persistantes avec active=False, translation_key=None, severity=None et
translation_placeholders=None (voir IssueRegistry.async_load). L'interface
Repairs les masque ; nos collecteurs doivent faire de même.
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from homeassistant.helpers.issue_registry import IssueSeverity

from custom_components.sentinel_report.collectors import ha_repairs, spook


def _issue(domain, issue_id, *, active=True, key=None, placeholders=None,
           severity=None, dismissed=None):
    """Issue avec les attributs lus par les collecteurs."""
    return SimpleNamespace(
        domain=domain,
        issue_id=issue_id,
        active=active,
        dismissed_version=dismissed,
        translation_key=key,
        translation_placeholders=placeholders,
        severity=severity,
        is_fixable=False,
        breaks_in_ha_version=None,
    )


def _ghost(domain, issue_id):
    """Entrée telle que construite par IssueRegistry.async_load (non persistante)."""
    return _issue(domain, issue_id, active=False)


def _registry(*issues):
    return SimpleNamespace(issues={(i.domain, i.issue_id): i for i in issues})


def _collect(module, registry):
    with patch(
        "homeassistant.helpers.issue_registry.async_get", return_value=registry
    ):
        return module._collect_issues(MagicMock())


# ── Spook ────────────────────────────────────────────────────────────────────

def test_spook_ignores_ghost_issues():
    registry = _registry(
        _issue(
            "spook", "unknown_icons_abc", key="unknown_icons",
            placeholders={}, severity=IssueSeverity.WARNING,
        ),
        _ghost("spook", "stale_access_tokens_72b99705256b49f2b396cf543cc2b12e"),
        _ghost("spook", "unknown_area_sensors_wc_c9582008"),
    )
    result = _collect(spook, registry)
    assert [i["issue_id"] for i in result] == ["unknown_icons_abc"]


def test_spook_keeps_active_issue_with_its_placeholders():
    registry = _registry(
        _issue(
            "spook", "script_unknown_service_references_x_f7b5fac0",
            key="script_unknown_service_references",
            placeholders={"script": "Watchman", "services": "- `notify.zoho_mail`"},
            severity=IssueSeverity.WARNING,
        ),
    )
    result = _collect(spook, registry)
    assert len(result) == 1
    assert "script: Watchman" in result[0]["label"]
    assert "notify.zoho_mail" in result[0]["label"]


def test_spook_empty_when_only_ghosts():
    registry = _registry(_ghost("spook", "orphaned_statistics_orphaned_statistics"))
    assert _collect(spook, registry) == []


# ── HA Repairs ───────────────────────────────────────────────────────────────

def test_ha_repairs_ignores_ghost_issues():
    registry = _registry(
        _issue(
            "backup_checkup", "automatic_backup_failed",
            key="automatic_backup_failed",
            placeholders={"attempt": "2026-10-25T09:09:43+00:00"},
            severity=IssueSeverity.ERROR,
        ),
        _ghost("backup_checkup", "latest_backup_incomplete"),
        _ghost("backup_checkup", "runner_not_discovered"),
    )
    result = _collect(ha_repairs, registry)
    assert [i["issue_id"] for i in result] == ["automatic_backup_failed"]
    assert result[0]["severity"] == "error"


def test_ha_repairs_still_excludes_other_collectors_domains():
    registry = _registry(
        _issue("spook", "x", key="x", placeholders={}, severity=IssueSeverity.WARNING),
        _issue("hacs", "y", key="y", placeholders={}, severity=IssueSeverity.WARNING),
        _issue("cloud", "no_subscription", key="no_subscription",
               placeholders={}, severity=IssueSeverity.ERROR),
    )
    result = _collect(ha_repairs, registry)
    assert [i["domain"] for i in result] == ["cloud"]


def test_ha_repairs_skips_dismissed_issues():
    registry = _registry(
        _issue("cloud", "no_subscription", key="no_subscription", placeholders={},
               severity=IssueSeverity.ERROR, dismissed="2026.10.0"),
    )
    assert _collect(ha_repairs, registry) == []
