"""Tests du config flow sentinel_report.

Vérifie la validation des champs et les constantes.
_build_schema utilise maintenant (hass, current) — les tests passent hass=None.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.sentinel_report.config_flow import (
    _validate_inputs,
    NOTIFY_THRESHOLD_OPTIONS,
    PURGE_MODE_OPTIONS,
)
from custom_components.sentinel_report.const import (
    CONF_REPORT_PATH,
    CONF_REPORT_FILE,
    CONF_INCLUDE_WARNINGS,
    CONF_KEEP_HISTORY,
    CONF_NOTIFY,
    CONF_NOTIFY_THRESHOLD,
    CONF_PURGE_MODE,
    CONF_STABILITY_DELAY,
    DEFAULT_REPORT_PATH,
    DEFAULT_REPORT_FILE,
    DEFAULT_INCLUDE_WARNINGS,
    DEFAULT_KEEP_HISTORY,
    DEFAULT_NOTIFY,
    DEFAULT_NOTIFY_THRESHOLD,
    DEFAULT_PURGE_MODE,
    DEFAULT_STABILITY_DELAY,
)


# ── Tests — _validate_inputs ─────────────────────────────────────────────────

def test_validate_inputs_valid():
    assert _validate_inputs("/share", "sentinel_report.txt", 60) is None


def test_validate_inputs_not_absolute():
    assert _validate_inputs("share", "sentinel_report.txt", 60) == "path_not_absolute"


def test_validate_inputs_empty_filename():
    assert _validate_inputs("/share", "", 60) == "filename_empty"
    assert _validate_inputs("/share", "   ", 60) == "filename_empty"


def test_validate_inputs_filename_with_slash():
    assert _validate_inputs("/share", "sub/report.txt", 60) == "filename_has_slash"


def test_validate_inputs_custom_path():
    assert _validate_inputs("/config/reports", "my_report.txt", 60) is None


def test_validate_inputs_stability_delay_too_low():
    assert _validate_inputs("/share", "report.txt", 45) == "stability_delay_too_low"


def test_validate_inputs_stability_delay_too_high():
    assert _validate_inputs("/share", "report.txt", 7200) == "stability_delay_too_high"


def test_validate_inputs_stability_delay_valid():
    assert _validate_inputs("/share", "report.txt", 60) is None
    assert _validate_inputs("/share", "report.txt", 3600) is None


# ── Tests — NOTIFY_THRESHOLD_OPTIONS ─────────────────────────────────────────

def test_notify_threshold_options_contains_errors_only():
    assert "errors_only" in NOTIFY_THRESHOLD_OPTIONS


def test_notify_threshold_options_contains_all():
    assert "all" in NOTIFY_THRESHOLD_OPTIONS


def test_notify_threshold_options_has_two_values():
    assert len(NOTIFY_THRESHOLD_OPTIONS) == 2


# ── Tests — PURGE_MODE_OPTIONS ────────────────────────────────────────────────

def test_purge_mode_options_contains_disabled():
    assert "disabled" in PURGE_MODE_OPTIONS


def test_purge_mode_options_contains_keep_files():
    assert "keep_files" in PURGE_MODE_OPTIONS


def test_purge_mode_options_contains_keep_days():
    assert "keep_days" in PURGE_MODE_OPTIONS


# ── Tests — constantes cohérentes ────────────────────────────────────────────

def test_default_report_path_is_absolute():
    assert DEFAULT_REPORT_PATH.startswith("/")


def test_default_report_file_has_extension():
    assert DEFAULT_REPORT_FILE.endswith(".txt")


def test_default_notify_is_false():
    assert DEFAULT_NOTIFY is False


def test_default_notify_threshold_is_errors_only():
    assert DEFAULT_NOTIFY_THRESHOLD == "errors_only"


def test_default_stability_delay_is_60():
    assert DEFAULT_STABILITY_DELAY == 60


def test_default_purge_mode_is_keep_files():
    assert DEFAULT_PURGE_MODE == "keep_files"
