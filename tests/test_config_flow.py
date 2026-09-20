"""Tests du config flow sentinel_report.

Vérifie la validation des champs, la création d'entrée,
et le flow d'options — sans instance HA réelle.
"""
from __future__ import annotations

import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.sentinel_report.config_flow import (
    _validate_path,
    _build_schema,
    NOTIFY_THRESHOLD_OPTIONS,
)
from custom_components.sentinel_report.const import (
    CONF_REPORT_PATH,
    CONF_REPORT_FILE,
    CONF_INCLUDE_WARNINGS,
    CONF_KEEP_HISTORY,
    CONF_NOTIFY,
    CONF_NOTIFY_THRESHOLD,
    DEFAULT_REPORT_PATH,
    DEFAULT_REPORT_FILE,
    DEFAULT_INCLUDE_WARNINGS,
    DEFAULT_KEEP_HISTORY,
    DEFAULT_NOTIFY,
    DEFAULT_NOTIFY_THRESHOLD,
)


# ── Tests — _validate_path ───────────────────────────────────────────────────

def test_validate_path_valid():
    """Un chemin absolu et un nom de fichier valides ne retournent pas d'erreur."""
    assert _validate_path("/share", "sentinel_report.txt") is None


def test_validate_path_not_absolute():
    """Un chemin relatif doit retourner une erreur."""
    assert _validate_path("share", "sentinel_report.txt") == "path_not_absolute"


def test_validate_path_empty_filename():
    """Un nom de fichier vide doit retourner une erreur."""
    assert _validate_path("/share", "") == "filename_empty"
    assert _validate_path("/share", "   ") == "filename_empty"


def test_validate_path_filename_with_slash():
    """Un nom de fichier contenant un slash doit retourner une erreur."""
    assert _validate_path("/share", "sub/report.txt") == "filename_has_slash"


def test_validate_path_custom_path():
    """Tout chemin absolu valide doit être accepté."""
    assert _validate_path("/config/reports", "my_report.txt") is None


# ── Tests — NOTIFY_THRESHOLD_OPTIONS ────────────────────────────────────────

def test_notify_threshold_options_contains_errors_only():
    assert "errors_only" in NOTIFY_THRESHOLD_OPTIONS


def test_notify_threshold_options_contains_all():
    assert "all" in NOTIFY_THRESHOLD_OPTIONS


def test_notify_threshold_options_has_two_values():
    assert len(NOTIFY_THRESHOLD_OPTIONS) == 2


# ── Tests — _build_schema ────────────────────────────────────────────────────

def test_build_schema_default_values():
    """Le schéma avec valeurs par défaut doit être valide."""
    schema = _build_schema()
    # Vérifier que le schéma accepte des valeurs valides
    result = schema({
        CONF_REPORT_PATH: DEFAULT_REPORT_PATH,
        CONF_REPORT_FILE: DEFAULT_REPORT_FILE,
        CONF_INCLUDE_WARNINGS: DEFAULT_INCLUDE_WARNINGS,
        CONF_KEEP_HISTORY: DEFAULT_KEEP_HISTORY,
        CONF_NOTIFY: DEFAULT_NOTIFY,
        CONF_NOTIFY_THRESHOLD: DEFAULT_NOTIFY_THRESHOLD,
    })
    assert result[CONF_REPORT_PATH] == DEFAULT_REPORT_PATH
    assert result[CONF_REPORT_FILE] == DEFAULT_REPORT_FILE


def test_build_schema_custom_values():
    """Le schéma doit accepter des valeurs personnalisées."""
    schema = _build_schema(
        report_path="/config",
        report_file="mon_rapport.txt",
        include_warnings=False,
        keep_history=False,
        notify=True,
        notify_threshold="all",
    )
    result = schema({
        CONF_REPORT_PATH: "/config",
        CONF_REPORT_FILE: "mon_rapport.txt",
        CONF_INCLUDE_WARNINGS: False,
        CONF_KEEP_HISTORY: False,
        CONF_NOTIFY: True,
        CONF_NOTIFY_THRESHOLD: "all",
    })
    assert result[CONF_REPORT_PATH] == "/config"
    assert result[CONF_NOTIFY] is True
    assert result[CONF_NOTIFY_THRESHOLD] == "all"


def test_build_schema_invalid_threshold():
    """Une valeur de seuil invalide doit être rejetée par le schéma."""
    import voluptuous as vol
    schema = _build_schema()
    try:
        schema({
            CONF_REPORT_PATH: "/share",
            CONF_REPORT_FILE: "report.txt",
            CONF_INCLUDE_WARNINGS: True,
            CONF_KEEP_HISTORY: True,
            CONF_NOTIFY: False,
            CONF_NOTIFY_THRESHOLD: "invalid_value",
        })
        assert False, "Aurait dû lever une exception voluptuous"
    except vol.Invalid:
        pass


# ── Tests — constantes cohérentes ────────────────────────────────────────────

def test_default_report_path_is_absolute():
    """Le chemin par défaut doit être absolu."""
    assert DEFAULT_REPORT_PATH.startswith("/")


def test_default_report_file_has_extension():
    """Le fichier par défaut doit avoir une extension .txt."""
    assert DEFAULT_REPORT_FILE.endswith(".txt")


def test_default_notify_is_false():
    """Les notifications sont désactivées par défaut."""
    assert DEFAULT_NOTIFY is False


def test_default_notify_threshold_is_errors_only():
    """Le seuil par défaut est 'errors_only'."""
    assert DEFAULT_NOTIFY_THRESHOLD == "errors_only"
