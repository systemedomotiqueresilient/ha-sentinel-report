"""Génération du fichier rapport texte — format proche de Watchman."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

from .const import VERSION

_LOGGER = logging.getLogger(__name__)


def generate_report(
    sentinel_items: list[dict[str, Any]],
    spook_issues: list[dict[str, Any]] | None,
    ha_repairs: list[dict[str, Any]] | None,
    resolved_incidents: list[dict[str, Any]] | None,
    include_warnings: bool,
    generated_at: datetime | None = None,
) -> tuple[str, bool, bool]:
    """Assembler le contenu texte du rapport.

    Retourne un tuple (contenu: str, has_problems: bool, has_resolved: bool).
    - has_problems : True si le rapport contient au moins un problème actif
    - has_resolved : True si le rapport contient des incidents résolus
    """
    if generated_at is None:
        generated_at = datetime.now()  # noqa: DTZ005

    if not include_warnings:
        sentinel_items = [i for i in sentinel_items if i.get("severity") != "warning"]

    now_str = generated_at.strftime("%Y-%m-%d %H:%M:%S")

    total_sentinel_errors   = sum(1 for i in sentinel_items if i.get("severity") == "error")
    total_sentinel_warnings = sum(1 for i in sentinel_items if i.get("severity") == "warning")
    total_spook             = len(spook_issues) if spook_issues is not None else 0
    total_ha_repairs        = len(ha_repairs) if ha_repairs is not None else 0
    grand_total             = len(sentinel_items) + total_spook + total_ha_repairs
    has_problems            = grand_total > 0
    has_resolved            = bool(resolved_incidents)

    lines: list[str] = []

    # ── Header ──────────────────────────────────────────────────────────────
    lines += [
        "==========================================",
        "  HA SENTINEL REPORT",
        f"  Version : {VERSION}",
        f"  Generated: {now_str}",
        "==========================================",
        "",
    ]

    # ── Section Sentinel ────────────────────────────────────────────────────
    lines.append(f"--- SENTINEL PROBLEMS ({len(sentinel_items)}) ---")

    if not sentinel_items:
        lines.append("  ✔ No problems detected.")
    else:
        by_provider: dict[str, list[dict]] = {}
        for item in sentinel_items:
            prov = item.get("provider", "unknown").upper()
            by_provider.setdefault(prov, []).append(item)

        for provider, items in by_provider.items():
            lines.append(f"\n  [{provider}]")
            for item in items:
                severity_tag = "ERROR" if item.get("severity") == "error" else "WARNING"
                name    = item.get("name", "?")
                domain  = item.get("domain", "")
                state   = item.get("state", "?")
                since   = item.get("since", "")

                name_str  = f"{name} ({domain})" if domain else name
                since_str = f" since {since}" if since else ""
                lines.append(f"  [{severity_tag}] {name_str} — {state}{since_str}")

                details = []
                if item.get("reason"):
                    details.append(f"Reason: {item['reason']}")
                if item.get("failure_count"):
                    details.append(f"Failures: {item['failure_count']}")

                if item.get("stability_type") == "restart_failed":
                    cycles   = item.get("stability_cycles", 0)
                    duration = item.get("stability_duration", "")
                    details.append(
                        f"N'a pas redémarré après {cycles} échec{'s' if cycles > 1 else ''} sur {duration}"
                    )

                if details:
                    lines.append(f"           → {' | '.join(details)}")

    lines.append("")

    # ── Section Spook ───────────────────────────────────────────────────────
    if spook_issues is not None:
        lines.append(f"--- SPOOK REPAIRS ({total_spook}) ---")
        if not spook_issues:
            lines.append("  ✔ No Spook issues detected.")
        else:
            for issue in spook_issues:
                sev = issue.get("severity", "warning").upper()
                label = issue.get("label", issue.get("issue_id", "unknown"))
                lines.append(f"  [{sev}] {label}")
        lines.append("")

    # ── Section HA Repairs ───────────────────────────────────────────────────
    if ha_repairs is not None:
        lines.append(f"--- HA REPAIRS ({total_ha_repairs}) ---")
        if not ha_repairs:
            lines.append("  ✔ No HA deprecation issues detected.")
        else:
            for issue in ha_repairs:
                sev = issue.get("severity", "warning").upper()
                label = issue.get("label", issue.get("issue_id", "unknown"))
                line = f"  [{sev}] {label}"
                lines.append(line)
                # Afficher la version de rupture si disponible
                breaks_in = issue.get("breaks_in_ha")
                if breaks_in:
                    lines.append(f"           → ⚠️  Cassant dans HA {breaks_in}")
        lines.append("")

    # ── Section Incidents résolus ────────────────────────────────────────────
    if has_resolved:
        lines.append(f"--- INCIDENTS RÉSOLUS ({len(resolved_incidents)}) ---")
        for inc in resolved_incidents:
            name     = inc.get("name", "?")
            cycles   = inc.get("cycles", 0)
            duration = inc.get("duration", "")
            resolved = inc.get("resolved_at", "")
            first    = inc.get("first_failure", "")
            lines.append(f"  [RESOLVED] {name}")
            lines.append(
                f"             → Stable depuis {resolved} | "
                f"{cycles} cycle{'s' if cycles > 1 else ''} d'instabilité sur {duration}"
            )
            if first:
                lines.append(f"             → Première défaillance : {first}")
        lines.append("")

    # ── Footer ──────────────────────────────────────────────────────────────
    lines.append("==========================================")

    if grand_total == 0 and not has_resolved:
        lines.append("  ✔ All clear — no problems detected.")
    else:
        parts = []
        if total_sentinel_errors:
            parts.append(f"{total_sentinel_errors} sentinel error{'s' if total_sentinel_errors > 1 else ''}")
        if total_sentinel_warnings:
            parts.append(f"{total_sentinel_warnings} sentinel warning{'s' if total_sentinel_warnings > 1 else ''}")
        if total_spook:
            parts.append(f"{total_spook} spook issue{'s' if total_spook > 1 else ''}")
        if total_ha_repairs:
            parts.append(f"{total_ha_repairs} HA repair{'s' if total_ha_repairs > 1 else ''}")
        if has_resolved:
            n = len(resolved_incidents)
            parts.append(f"{n} incident{'s' if n > 1 else ''} résolu{'s' if n > 1 else ''}")
        if parts:
            lines.append("  ✖ " + ", ".join(parts))
        else:
            lines.append("  ✔ All clear — no problems detected.")

    lines.append("==========================================")
    lines.append("")

    return "\n".join(lines), has_problems, has_resolved


def write_report(full_path: str, content: str) -> None:
    """Écrire le rapport latest sur disque."""
    directory = os.path.dirname(full_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    _LOGGER.info("Sentinel Report écrit dans %s", full_path)


def write_history(report_path: str, history_dir: str, content: str, generated_at: datetime) -> None:
    """Écrire une copie horodatée du rapport dans le dossier d'historique."""
    timestamp = generated_at.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"sentinel_report_{timestamp}.txt"
    history_path = os.path.join(report_path, history_dir)
    os.makedirs(history_path, exist_ok=True)
    full_path = os.path.join(history_path, filename)
    with open(full_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    _LOGGER.info("Sentinel Report archivé dans %s", full_path)


def purge_history(
    report_path: str,
    history_dir: str,
    purge_mode: str,
    keep_files: int = 30,
    keep_days: int = 30,
) -> int:
    """Purger les fichiers d'historique selon le mode choisi."""
    if purge_mode == "disabled":
        return 0

    try:
        keep_files = int(float(keep_files)) if keep_files is not None else 30
    except (TypeError, ValueError):
        keep_files = 30
    try:
        keep_days = int(float(keep_days)) if keep_days is not None else 30
    except (TypeError, ValueError):
        keep_days = 30

    history_path = os.path.join(report_path, history_dir)
    if not os.path.isdir(history_path):
        return 0

    files = sorted(
        [f for f in os.listdir(history_path)
         if f.startswith("sentinel_report_") and f.endswith(".txt")],
        reverse=True,
    )

    to_delete: list[str] = []

    if purge_mode == "keep_files":
        to_delete = files[keep_files:]
    elif purge_mode == "keep_days":
        cutoff = datetime.now() - timedelta(days=keep_days)  # noqa: DTZ005
        for filename in files:
            try:
                date_str = filename[len("sentinel_report_"):-len(".txt")]
                file_dt = datetime.strptime(date_str, "%Y-%m-%d_%H-%M-%S")  # noqa: DTZ007
                if file_dt < cutoff:
                    to_delete.append(filename)
            except ValueError:
                continue

    deleted = 0
    for filename in to_delete:
        try:
            os.remove(os.path.join(history_path, filename))
            deleted += 1
        except OSError as exc:
            _LOGGER.warning("Sentinel Report : impossible de supprimer %s : %s", filename, exc)

    if deleted:
        _LOGGER.info(
            "Sentinel Report : purge historique (%s) — %d fichier(s) supprimé(s)",
            purge_mode, deleted,
        )
    return deleted
