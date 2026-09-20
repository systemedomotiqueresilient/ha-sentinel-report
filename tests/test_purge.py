"""Tests unitaires pour la purge de l'historique (reporter.purge_history)."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.sentinel_report.reporter import purge_history, write_history


# ── Helpers ──────────────────────────────────────────────────────────────────

def _create_history_files(history_path: str, dates: list[datetime]) -> list[str]:
    """Créer des fichiers d'historique factices pour les dates données."""
    os.makedirs(history_path, exist_ok=True)
    files = []
    for dt in dates:
        ts = dt.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"sentinel_report_{ts}.txt"
        path = os.path.join(history_path, filename)
        with open(path, "w") as f:
            f.write(f"rapport du {ts}")
        files.append(filename)
    return files


def _list_history_files(history_path: str) -> list[str]:
    """Lister les fichiers d'historique présents."""
    if not os.path.isdir(history_path):
        return []
    return sorted(
        f for f in os.listdir(history_path)
        if f.startswith("sentinel_report_") and f.endswith(".txt")
    )


# ── Tests — mode disabled ─────────────────────────────────────────────────────

def test_purge_disabled_does_nothing():
    """Mode 'disabled' : aucun fichier supprimé."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_dir = "history"
        history_path = os.path.join(tmpdir, history_dir)
        _create_history_files(history_path, [
            datetime.now() - timedelta(days=i) for i in range(5)
        ])
        deleted = purge_history(tmpdir, history_dir, "disabled")
        assert deleted == 0
        assert len(_list_history_files(history_path)) == 5


def test_purge_disabled_with_empty_dir():
    """Mode 'disabled' sur dossier vide : retourne 0."""
    with tempfile.TemporaryDirectory() as tmpdir:
        deleted = purge_history(tmpdir, "history", "disabled")
        assert deleted == 0


# ── Tests — mode keep_files ───────────────────────────────────────────────────

def test_purge_keep_files_keeps_n_most_recent():
    """keep_files=3 sur 5 fichiers : supprime les 2 plus anciens."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_dir = "history"
        history_path = os.path.join(tmpdir, history_dir)
        now = datetime(2026, 8, 1, 12, 0, 0)
        dates = [now - timedelta(hours=i) for i in range(5)]
        _create_history_files(history_path, dates)

        deleted = purge_history(tmpdir, history_dir, "keep_files", keep_files=3)
        assert deleted == 2
        remaining = _list_history_files(history_path)
        assert len(remaining) == 3


def test_purge_keep_files_no_deletion_when_below_limit():
    """keep_files=10 sur 5 fichiers : aucune suppression."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_dir = "history"
        history_path = os.path.join(tmpdir, history_dir)
        now = datetime(2026, 8, 1, 12, 0, 0)
        dates = [now - timedelta(hours=i) for i in range(5)]
        _create_history_files(history_path, dates)

        deleted = purge_history(tmpdir, history_dir, "keep_files", keep_files=10)
        assert deleted == 0
        assert len(_list_history_files(history_path)) == 5


def test_purge_keep_files_exact_limit():
    """keep_files=5 sur 5 fichiers : aucune suppression."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_dir = "history"
        history_path = os.path.join(tmpdir, history_dir)
        now = datetime(2026, 8, 1, 12, 0, 0)
        dates = [now - timedelta(hours=i) for i in range(5)]
        _create_history_files(history_path, dates)

        deleted = purge_history(tmpdir, history_dir, "keep_files", keep_files=5)
        assert deleted == 0


def test_purge_keep_files_keeps_most_recent_not_oldest():
    """keep_files=2 : les 2 fichiers restants sont les plus récents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_dir = "history"
        history_path = os.path.join(tmpdir, history_dir)
        now = datetime(2026, 8, 1, 12, 0, 0)
        dates = [now - timedelta(hours=i) for i in range(4)]
        _create_history_files(history_path, dates)

        purge_history(tmpdir, history_dir, "keep_files", keep_files=2)
        remaining = _list_history_files(history_path)
        assert len(remaining) == 2
        # Les fichiers restants doivent être les plus récents (tri décroissant)
        assert "2026-08-01_12-00-00" in remaining[1]
        assert "2026-08-01_11-00-00" in remaining[0]


def test_purge_keep_files_empty_history():
    """keep_files sur dossier inexistant : retourne 0 sans erreur."""
    with tempfile.TemporaryDirectory() as tmpdir:
        deleted = purge_history(tmpdir, "nonexistent", "keep_files", keep_files=5)
        assert deleted == 0


# ── Tests — mode keep_days ────────────────────────────────────────────────────

def test_purge_keep_days_removes_old_files():
    """keep_days=7 : supprime les fichiers plus anciens que 7 jours."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_dir = "history"
        history_path = os.path.join(tmpdir, history_dir)
        now = datetime.now()
        # 3 fichiers récents (< 7 jours) + 3 anciens (> 7 jours)
        recent = [now - timedelta(days=i) for i in range(3)]
        old = [now - timedelta(days=10 + i) for i in range(3)]
        _create_history_files(history_path, recent + old)

        deleted = purge_history(tmpdir, history_dir, "keep_days", keep_days=7)
        assert deleted == 3
        assert len(_list_history_files(history_path)) == 3


def test_purge_keep_days_keeps_recent_files():
    """keep_days=30 : aucun fichier supprimé si tous récents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_dir = "history"
        history_path = os.path.join(tmpdir, history_dir)
        now = datetime.now()
        _create_history_files(history_path, [now - timedelta(days=i) for i in range(5)])

        deleted = purge_history(tmpdir, history_dir, "keep_days", keep_days=30)
        assert deleted == 0
        assert len(_list_history_files(history_path)) == 5


def test_purge_keep_days_empty_history():
    """keep_days sur dossier inexistant : retourne 0 sans erreur."""
    with tempfile.TemporaryDirectory() as tmpdir:
        deleted = purge_history(tmpdir, "nonexistent", "keep_days", keep_days=30)
        assert deleted == 0


def test_purge_ignores_unexpected_filenames():
    """Les fichiers au nom inattendu ne doivent pas provoquer d'erreur."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_dir = "history"
        history_path = os.path.join(tmpdir, history_dir)
        os.makedirs(history_path)
        # Fichier au nom inattendu
        with open(os.path.join(history_path, "sentinel_report_invalid.txt"), "w") as f:
            f.write("bad")
        # Fichier valide récent
        now = datetime.now()
        _create_history_files(history_path, [now])

        # Ne doit pas lever d'exception
        deleted = purge_history(tmpdir, history_dir, "keep_days", keep_days=1)
        assert deleted == 0  # Le fichier valide est récent, l'invalide est ignoré


# ── Tests — write_history + purge intégrés ───────────────────────────────────

def test_write_and_purge_integration():
    """Écrire 5 rapports puis purger à 3 : 2 supprimés."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_dir = "history"
        history_path = os.path.join(tmpdir, history_dir)
        now = datetime(2026, 8, 1, 12, 0, 0)

        for i in range(5):
            dt = now - timedelta(hours=i)
            write_history(tmpdir, history_dir, f"rapport {i}", dt)

        assert len(_list_history_files(history_path)) == 5

        deleted = purge_history(tmpdir, history_dir, "keep_files", keep_files=3)
        assert deleted == 2
        assert len(_list_history_files(history_path)) == 3
