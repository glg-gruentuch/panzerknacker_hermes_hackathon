"""The six challenge stages. Each stage returns a JSON result."""
from pathlib import Path
from typing import Any

from .config import Settings

STAGES = ("extract", "match", "compare", "claims", "agent", "site", "evaluate", "export")

# Stages with a working implementation. The CLI and doctor report this set.
IMPLEMENTED: set[str] = set(STAGES)


def extract(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Extract scans with Parse 3.5 and segment entries. See docs/milestones.md#extract."""
    from .extract import run_extract

    return run_extract(settings, work_dir)


def match(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Find and verify Wikipedia article matches. See docs/milestones.md#match."""
    from .match import run_match

    return run_match(settings, work_dir)


def compare(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Frequency and distinctive-term comparison. See docs/milestones.md#compare."""
    from .compare import run_compare

    return run_compare(settings, work_dir)


def claims(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Align claims between matched texts with Super VL. See docs/milestones.md#claims."""
    from .claims import run_claims

    return run_claims(settings, work_dir)


def agent(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Run the scripted Hermes cases and record evidence. See docs/milestones.md#agent."""
    from .agent_runner import run_agent_cases

    return run_agent_cases(settings, work_dir)


def site(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Build the LaTeX documents and the static website. See docs/milestones.md#site."""
    from .site_build import build_site

    return build_site(settings, work_dir)


def evaluate(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Assemble the evaluation report. See docs/milestones.md#evaluate."""
    from .evaluate import run_evaluate

    return run_evaluate(settings, work_dir)


def export(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Write the static app data for the React UI. See handoff 2, item B10."""
    from .site_export import run_export

    return run_export(settings, work_dir)
