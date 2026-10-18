"""Build the LaTeX archive documents and the static website."""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .config import Settings
from .data import load_manifest
from .pipeline import read_jsonl, write_json

TECTONIC = Path.home() / ".local" / "bin" / "tectonic"
DEFAULT_OUT = Path("deliverables/website")
LINK = re.compile(r'(?:href|src)="([^"]+)"')

TEX_REPLACEMENTS = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def tex_escape(text: str) -> str:
    return "".join(TEX_REPLACEMENTS.get(char, char) for char in text)


def html_escape(text: str) -> str:
    return html.escape(text, quote=True)


def render_page_tex(page: dict[str, Any], checksum: str, volume_id: str) -> str:
    """One LaTeX document per scan. Headings keep the reading order."""
    lines = [
        r"\documentclass{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage{hyperref}",
        r"\begin{document}",
        r"\begin{center}",
        r"{\Large Encyclopaedia Britannica scan \texttt{" + tex_escape(page["filename"]) + r"}}\\[0.5em]",
        tex_escape(page.get("page_header", "") or "(no running head)"),
        r"\end{center}",
    ]
    for entry in page["entries"]:
        heading = entry.get("heading") or "(untitled)"
        command = r"\section*" if entry.get("heading_class") == "Title" else r"\subsection*"
        lines.append(f"{command}{{{tex_escape(heading)}}}")
        body = entry.get("body", "").strip()
        if body:
            lines.append(tex_escape(body))
            lines.append("")
    lines += [
        r"\section*{Source record}",
        r"\begin{itemize}",
        r"\item Page ID: \texttt{" + tex_escape(page["page_id"]) + "}",
        r"\item Scan file: \texttt{" + tex_escape(page["filename"]) + "}",
        r"\item Image SHA-256: \texttt{" + tex_escape(checksum) + "}",
        r"\item Source volume ID: \texttt{" + tex_escape(volume_id) + "}",
        r"\item Extraction: nvidia/nemotron-3.5-parse via the shared organizer endpoint.",
        r"\item Dataset: National Library of Scotland, Encyclopaedia Britannica Illustrated (CC0 1.0).",
        r"\end{itemize}",
        r"\end{document}",
    ]
    return "\n".join(lines) + "\n"


def compile_tex(tex_path: Path, out_dir: Path) -> tuple[bool, str]:
    """Compile one LaTeX document with tectonic. Returns (ok, detail)."""
    tex_path = Path(tex_path).resolve()
    out_dir = Path(out_dir).resolve()
    if not TECTONIC.exists():
        return False, "tectonic not found at ~/.local/bin/tectonic"
    if not tex_path.exists():
        return False, f"LaTeX source missing: {tex_path}"
    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(TECTONIC), "--outdir", str(out_dir), str(tex_path)],
        capture_output=True, text=True, timeout=300, cwd=tex_path.parent,
    )
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-4:]
        return False, " | ".join(tail)
    return True, ""


def make_thumbnail(scan: Path, destination: Path, width: int = 800) -> None:
    """Downscale a scan with ffmpeg. Copy the original when ffmpeg is missing."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("ffmpeg") is None:
        shutil.copy2(scan, destination)
        return
    result = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(scan), "-vf", f"scale={width}:-2",
         "-q:v", "6", str(destination)],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        shutil.copy2(scan, destination)


def _page_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html_escape(title)}</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<nav><a href="index.html">Index</a> <a href="compare.html">Comparisons</a>
<a href="cases.html">Case studies</a> <a href="limits.html">Limits</a></nav>
<main>
{body}
</main>
</body>
</html>
"""


STYLE = """body { font-family: Georgia, serif; margin: 2rem auto; max-width: 60rem; padding: 0 1rem; color: #1b1b1b; }
nav a { margin-right: 1rem; }
img.scan { max-width: 100%; border: 1px solid #999; }
pre { white-space: pre-wrap; font-family: inherit; }
.cite { color: #555; font-size: 0.9rem; }
table { border-collapse: collapse; }
td, th { border: 1px solid #bbb; padding: 0.3rem 0.6rem; }
"""


def build_site(
    settings: Settings,
    work_dir: Path,
    *,
    out_dir: Path = DEFAULT_OUT,
    scan_dir: Path = Path("data/raw/britannica"),
    compile_pdfs: bool = True,
) -> dict[str, Any]:
    """Render LaTeX sources, compile them, and assemble the static site."""
    manifest = load_manifest()
    pages_by_scan = {page["filename"]: page for page in manifest["pages"]}
    derived_dir = work_dir / "extract" / "derived"
    coverage = {}
    coverage_path = work_dir / "extract" / "coverage.json"
    if coverage_path.exists():
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    entries_flat = read_jsonl(work_dir / "match" / "matches.jsonl")
    comparisons = read_jsonl(work_dir / "compare" / "comparisons.jsonl")
    tex_dir = work_dir / "site" / "tex"
    files_dir = out_dir / "files"
    assets = out_dir / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "style.css").write_text(STYLE, encoding="utf-8")

    compile_failures: list[dict[str, str]] = []
    compiled = 0
    page_links: list[tuple[str, str, int]] = []
    match_by_entry = {row["entry_id"]: row for row in entries_flat}
    compare_by_entry = {row["entry_id"]: row for row in comparisons}
    for page_file in sorted(derived_dir.glob("page-*.jpg.json")):
        page = json.loads(page_file.read_text(encoding="utf-8"))
        meta = pages_by_scan.get(page["filename"], {})
        checksum = meta.get("image_sha256", "")
        volume_id = meta.get("volume_id", "")
        if compile_pdfs:
            tex_path = tex_dir / f"{page['filename']}.tex"
            tex_path.parent.mkdir(parents=True, exist_ok=True)
            tex_path.write_text(render_page_tex(page, checksum, volume_id), encoding="utf-8")
            ok, detail = compile_tex(tex_path, files_dir)
            if ok:
                compiled += 1
            else:
                compile_failures.append({"file": page["filename"], "error": detail})
        scan = scan_dir / page["filename"]
        if scan.exists():
            make_thumbnail(scan, assets / "scans" / page["filename"])
        body = [f"<h1>{html_escape(page['filename'])}</h1>"]
        if scan.exists():
            body.append(f'<p><img class="scan" src="assets/scans/{html_escape(page["filename"])}" alt="Scan of {html_escape(page["filename"])}"></p>')
        body.append(f"<p class=\"cite\">Page ID: {html_escape(page['page_id'])}<br>Running head: {html_escape(page.get('page_header',''))}"
                    f"<br>Image SHA-256: {html_escape(checksum)}</p>")
        if compile_pdfs and (files_dir / f"{page['filename']}.pdf").exists():
            body.append(f'<p><a href="files/{html_escape(page["filename"])}.pdf">Compiled LaTeX document (PDF)</a></p>')
        for entry in page["entries"]:
            body.append(f"<h2>{html_escape(entry.get('heading') or '(untitled)')} <span class=\"cite\">[{html_escape(entry.get('heading_class') or '?')}]</span></h2>")
            body.append(f"<pre>{html_escape(entry.get('body',''))}</pre>")
            match = match_by_entry.get(entry["entry_id"])
            if match:
                comparison = compare_by_entry.get(entry["entry_id"])
                link = f' &middot; <a href="compare.html#{html_escape(entry["entry_id"])}">comparison</a>' if comparison else ""
                body.append(f'<p class="cite">Matched article: {html_escape(match["article_title"])} '
                            f'(<a href="{html_escape(match["article_url"])}">Wikipedia</a>, revision {html_escape(match["article_revision_id"])}, '
                            f're-rank score {match["match_confidence"]}){link}</p>')
        name = page["filename"].removesuffix(".jpg")
        (out_dir / f"{name}.html").write_text(_page_shell(page["filename"], "\n".join(body)), encoding="utf-8")
        page_links.append((name, page["filename"], len(page["entries"])))

    index_body = [
        "<h1>Encyclopaedia Britannica 1768-1860 against Wikipedia</h1>",
        "<p>This archive presents 100 historical Britannica scans with the text extracted by Nemotron Parse 3.5 and compiled LaTeX documents.</p>",
        f"<p>Scans processed: {coverage.get('pages_ok', 'pending')} of {coverage.get('pages_total', 'pending')}. "
        f"Entries: {coverage.get('entries', 'pending')}. Failed scans: {coverage.get('pages_failed', 'pending')}.</p>",
        f"<p>Matched entries: {len(entries_flat) if entries_flat else 'pending'}. Compared pairs: {len(comparisons) if comparisons else 'pending'}.</p>",
        "<h2>Scans</h2>",
        "<ul>",
    ]
    for name, filename, entry_count in page_links:
        index_body.append(f'<li><a href="{html_escape(name)}.html">{html_escape(filename)}</a> ({entry_count} entries)</li>')
    index_body.append("</ul>")
    (out_dir / "index.html").write_text(_page_shell("Index", "\n".join(index_body)), encoding="utf-8")

    compare_body = ["<h1>Comparisons</h1>"]
    if comparisons:
        plots_src = work_dir / "compare" / "plots"
        if plots_src.exists():
            for plot in sorted(plots_src.glob("*.png")):
                shutil.copy2(plot, assets / plot.name)
                compare_body.append(f'<p><img src="assets/{html_escape(plot.name)}" alt="{html_escape(plot.name)}" style="max-width:100%"></p>')
        compare_body.append("<table><tr><th>Entry</th><th>Article</th><th>Britannica tokens</th><th>Wikipedia tokens</th></tr>")
        for row in comparisons:
            compare_body.append(
                f'<tr id="{html_escape(row["entry_id"])}"><td>{html_escape(row["entry_title"])}</td>'
                f'<td>{html_escape(row["article_title"])}</td><td>{row["britannica"]["tokens"]}</td>'
                f'<td>{row["wikipedia"]["tokens"]}</td></tr>')
        compare_body.append("</table>")
    else:
        compare_body.append("<p>No comparisons yet. Match coverage is pending the retrieval service.</p>")
    (out_dir / "compare.html").write_text(_page_shell("Comparisons", "\n".join(compare_body)), encoding="utf-8")

    cases_dir = Path("docs/cases")
    cases_body = ["<h1>Case studies</h1>"]
    cases = sorted(cases_dir.glob("*.md")) if cases_dir.exists() else []
    if cases:
        cases_body.append("<ul>" + "".join(f"<li>{html_escape(case.stem)}</li>" for case in cases) + "</ul>")
    else:
        cases_body.append("<p>Case studies are recorded from Hermes agent runs in docs/cases.</p>")
    (out_dir / "cases.html").write_text(_page_shell("Case studies", "\n".join(cases_body)), encoding="utf-8")

    limits_body = ["<h1>Limits</h1>",
                   "<p>Extraction covers the fixed 100-scan manifest. Match thresholds are calibrated on samples; "
                   "unmatched entries are reported, not forced. Wikipedia text is CC BY-SA 4.0 and quoted for comparison. "
                   "See docs/method.md for the full method and known limits.</p>"]
    (out_dir / "limits.html").write_text(_page_shell("Limits", "\n".join(limits_body)), encoding="utf-8")

    broken = check_links(out_dir)
    result = {
        "stage": "site",
        "out_dir": str(out_dir),
        "pages": len(page_links),
        "pdfs_compiled": compiled,
        "compile_failures": compile_failures,
        "broken_links": broken,
        "compare_pairs": len(comparisons),
    }
    write_json(work_dir / "site" / "build.json", result)
    return result


def check_links(site_dir: Path) -> list[str]:
    """Return relative links in the site that point at missing files."""
    broken: list[str] = []
    for html_file in sorted(site_dir.glob("*.html")):
        text = html_file.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            plain = re.split(r"[#?]", target, maxsplit=1)[0]
            if not plain:
                continue
            if not (site_dir / plain).exists():
                broken.append(f"{html_file.name} -> {target}")
    return broken
