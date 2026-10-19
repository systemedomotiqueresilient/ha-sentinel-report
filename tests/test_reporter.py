"""Tests unitaires pour sentinel_report.reporter."""
from __future__ import annotations

import sys
import os
from datetime import datetime

# Permet d'importer reporter sans instance HA
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.sentinel_report.reporter import generate_report


# ── Fixtures ────────────────────────────────────────────────────────────────

FIXED_DT = datetime(2026, 1, 1, 12, 0, 0)

SENTINEL_ERROR = {
    "id": "netatmo_error",
    "name": "Netatmo",
    "provider": "integrations",
    "healthy": False,
    "state": "setup_error",
    "severity": "error",
    "reason": "Token expired",
    "since": "2026-01-01 12:00:00",
    "failure_count": 3,
    "domain": "netatmo",
}

SENTINEL_WARNING = {
    "id": "zwave_warning",
    "name": "Z-Wave JS",
    "provider": "integrations",
    "healthy": False,
    "state": "setup_retry",
    "severity": "warning",
    "reason": "",
    "since": "2026-01-01 13:00:00",
    "failure_count": 1,
    "domain": "zwave_js",
}

SPOOK_ISSUE = {
    "issue_id": "entity_no_longer_provided_light.old_lamp",
    "domain": "spook",
    "severity": "warning",
    "label": "[entity_no_longer_provided] — entity_id: light.old_lamp",
    "is_fixable": True,
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def report(sentinel_items, spook_issues, include_warnings, resolved_incidents=None, ha_repairs=None, **kwargs):
    """Appeler generate_report et retourner uniquement le contenu texte."""
    content, _, _ = generate_report(
        sentinel_items, spook_issues, ha_repairs or [],
        resolved_incidents or [],
        include_warnings, generated_at=FIXED_DT, **kwargs
    )
    return content


def has_problems(sentinel_items, spook_issues, include_warnings, resolved_incidents=None, ha_repairs=None, **kwargs):
    """Appeler generate_report et retourner uniquement le flag has_problems."""
    _, flag, _ = generate_report(
        sentinel_items, spook_issues, ha_repairs or [],
        resolved_incidents or [],
        include_warnings, generated_at=FIXED_DT, **kwargs
    )
    return flag


# ── Tests — contenu du rapport ───────────────────────────────────────────────

def test_all_clear_report():
    """Un rapport sans problèmes doit afficher 'All clear'."""
    content = report([], [], include_warnings=True)
    assert "All clear" in content
    assert "SENTINEL PROBLEMS (0)" in content
    assert "SPOOK REPAIRS (0)" in content


def test_sentinel_error_appears():
    """Une erreur Sentinel doit apparaître dans le rapport."""
    content = report([SENTINEL_ERROR], [], include_warnings=True)
    assert "[ERROR]" in content
    assert "Netatmo" in content
    assert "Token expired" in content
    assert "Failures: 3" in content


def test_warning_filtered_when_disabled():
    """Les warnings doivent être absents si include_warnings=False."""
    content = report([SENTINEL_ERROR, SENTINEL_WARNING], [], include_warnings=False)
    assert "Z-Wave JS" not in content
    assert "Netatmo" in content


def test_warning_present_when_enabled():
    """Les warnings doivent apparaître si include_warnings=True."""
    content = report([SENTINEL_ERROR, SENTINEL_WARNING], [], include_warnings=True)
    assert "Z-Wave JS" in content
    assert "[WARNING]" in content


def test_spook_section_present():
    """La section Spook doit apparaître quand des issues sont présentes."""
    content = report([], [SPOOK_ISSUE], include_warnings=True)
    assert "SPOOK REPAIRS (1)" in content
    assert "entity_no_longer_provided" in content


def test_spook_section_absent_when_none():
    """La section Spook doit être absente si spook_issues=None (collecteur non chargé)."""
    content = report([], None, include_warnings=True)
    assert "SPOOK REPAIRS" not in content


def test_footer_summary_counts():
    """Le footer doit résumer correctement le nombre de problèmes."""
    content = report([SENTINEL_ERROR, SENTINEL_WARNING], [SPOOK_ISSUE], include_warnings=True)
    assert "1 sentinel error" in content
    assert "1 sentinel warning" in content
    assert "1 spook issue" in content


def test_provider_grouping():
    """Les items doivent être regroupés par provider."""
    content = report([SENTINEL_ERROR, SENTINEL_WARNING], [], include_warnings=True)
    assert "[INTEGRATIONS]" in content


def test_header_contains_version_and_generated():
    """Le header doit contenir la version et la date de génération."""
    content = report([], [], include_warnings=True)
    assert "HA SENTINEL REPORT" in content
    assert "Generated:" in content
    assert "Version :" in content
    assert "2026-01-01 12:00:00" in content


# ── Tests — flag has_problems ────────────────────────────────────────────────

def test_has_problems_false_when_all_clear():
    """has_problems doit être False quand aucun problème."""
    assert has_problems([], [], include_warnings=True) is False


def test_has_problems_false_when_spook_empty():
    """has_problems doit être False si Spook est présent mais sans issues."""
    assert has_problems([], [], include_warnings=True) is False


def test_has_problems_true_with_sentinel_error():
    """has_problems doit être True si une erreur Sentinel est présente."""
    assert has_problems([SENTINEL_ERROR], [], include_warnings=True) is True


def test_has_problems_true_with_spook_issue():
    """has_problems doit être True si une issue Spook est présente."""
    assert has_problems([], [SPOOK_ISSUE], include_warnings=True) is True


def test_has_problems_true_with_warning_when_enabled():
    """has_problems doit être True si un warning est présent et include_warnings=True."""
    assert has_problems([SENTINEL_WARNING], [], include_warnings=True) is True


def test_has_problems_false_with_warning_when_disabled():
    """has_problems doit être False si seul un warning est présent et include_warnings=False."""
    assert has_problems([SENTINEL_WARNING], [], include_warnings=False) is False


def test_has_problems_none_spook_not_counted():
    """has_problems doit être False si spook_issues=None et sentinel vide."""
    assert has_problems([], None, include_warnings=True) is False


# ── Tests — pluriel dans le footer ──────────────────────────────────────────

def test_footer_plural_errors():
    """Le footer doit utiliser 'errors' au pluriel si > 1."""
    sentinel_items = [SENTINEL_ERROR, {**SENTINEL_ERROR, "id": "error2", "name": "Tuya"}]
    content = report(sentinel_items, [], include_warnings=True)
    assert "2 sentinel errors" in content


def test_footer_singular_error():
    """Le footer doit utiliser 'error' au singulier si = 1."""
    content = report([SENTINEL_ERROR], [], include_warnings=True)
    assert "1 sentinel error" in content
    assert "1 sentinel errors" not in content
