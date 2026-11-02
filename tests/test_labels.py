"""Tests des libellés : placeholders inconnus (Spook) et valeurs multi-lignes (HA Repairs)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.sentinel_report.collectors import ha_repairs, spook

# ── Spook : filet de sécurité sur les placeholders inconnus ──────────────────


def test_spook_label_shows_unknown_placeholder():
    """empty_areas : le nom de la pièce (placeholder `area`) doit apparaître."""
    label = spook._build_label("empty_areas", {"area": "Salon"})
    assert label == "[empty_areas] — area: Salon"


def test_spook_two_empty_areas_are_distinguishable():
    first = spook._build_label("empty_areas", {"area": "Salon"})
    second = spook._build_label("empty_areas", {"area": "Garage"})
    assert first != second


def test_spook_known_keys_keep_their_order_and_are_not_duplicated():
    label = spook._build_label(
        "script_unknown_service_references",
        {
            "services": "- `notify.x`\n- `notify.y`",
            "script": "Mon script",
            "entity_id": "script.mon_script",
        },
    )
    assert label == (
        "[script_unknown_service_references] — script: Mon script"
        " — entity_id: script.mon_script — services: notify.x, notify.y"
    )


def test_spook_ignores_links_and_empty_values():
    label = spook._build_label(
        "some_repair",
        {"learn_more_url": "https://example.org", "url": "x", "edit": "y", "extra": ""},
    )
    assert label == "[some_repair]"


def test_spook_unknown_multiline_placeholder_is_flattened_and_capped():
    long_value = "ligne\n" * 100
    label = spook._build_label("some_repair", {"details": long_value})
    assert "\n" not in label
    assert label.startswith("[some_repair] — details: ligne ligne")
    assert label.endswith("…")
    assert len(label) < 260


def test_spook_without_placeholders_keeps_bare_key():
    assert spook._build_label("unknown_icons", {}) == "[unknown_icons]"


# ── HA Repairs : valeurs multi-lignes ────────────────────────────────────────


def test_ha_repairs_yaml_example_on_one_line():
    value = "```yaml\nsensor:\n  - platform: template\n```"
    result = ha_repairs._format_value(value)
    assert "\n" not in result
    assert "```" not in result
    assert result == "sensor: - platform: template"


def test_ha_repairs_plain_value_unchanged():
    assert ha_repairs._format_value("BackUP_HAOS") == "BackUP_HAOS"


def test_ha_repairs_iso_timestamp_still_converted():
    result = ha_repairs._format_value("2026-10-25T09:09:43+00:00")
    assert "T" not in result
    assert len(result) == len("2026-10-25 09:09:43")
