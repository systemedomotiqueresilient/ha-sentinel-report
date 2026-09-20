"""Tests des filtres du collecteur Sentinel.

Ces tests couvrent la logique de filtrage des états transitoires
et l'exclusion des domaines Sentinel Report lui-même.
Pas de dépendance HA — tests purement unitaires.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.sentinel_report.collectors.sentinel import (
    _EXCLUDED_DOMAINS,
    _TRANSIENT_STATES,
)


# ── Tests — états transitoires ───────────────────────────────────────────────

def test_transient_states_contains_not_loaded():
    assert "not_loaded" in _TRANSIENT_STATES


def test_transient_states_contains_setup_in_progress():
    assert "setup_in_progress" in _TRANSIENT_STATES


def test_transient_states_contains_loading():
    assert "loading" in _TRANSIENT_STATES


def test_transient_states_does_not_contain_unavailable():
    """unavailable est un vrai problème — ne doit pas être filtré."""
    assert "unavailable" not in _TRANSIENT_STATES


def test_transient_states_does_not_contain_setup_error():
    """setup_error est un vrai problème — ne doit pas être filtré."""
    assert "setup_error" not in _TRANSIENT_STATES


# ── Tests — domaines exclus ──────────────────────────────────────────────────

def test_excluded_domains_contains_sentinel_report():
    assert "sentinel_report" in _EXCLUDED_DOMAINS


def test_excluded_domains_contains_sentinel_report_sentinel():
    assert "sentinel_report_sentinel" in _EXCLUDED_DOMAINS


def test_excluded_domains_contains_sentinel_report_spook():
    assert "sentinel_report_spook" in _EXCLUDED_DOMAINS


def test_excluded_domains_does_not_contain_sentinel():
    """sentinel (GuiPoM) ne doit PAS être exclu — c'est une dépendance externe."""
    assert "sentinel" not in _EXCLUDED_DOMAINS


def test_excluded_domains_does_not_contain_spook():
    """spook (frenck) ne doit PAS être exclu."""
    assert "spook" not in _EXCLUDED_DOMAINS
