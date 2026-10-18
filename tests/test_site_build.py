"""Site builder renders LaTeX, HTML, and a clean link graph."""
import json
from pathlib import Path

from nemotron_challenge.config import Settings
from nemotron_challenge.site_build import build_site, check_links, render_page_tex, tex_escape

PAGE = {
    "page_id": "britannica:rev:train:13",
    "filename": "page-0013-aaaa.jpg",
    "page_header": "292 SHIP-BUILDING",
    "entries": [
        {"entry_id": "britannica:rev:train:13#0000", "heading": "Practical Building",
         "heading_class": "Section-header", "body": "A & B ~ 50% of the _ship_."},
    ],
}
MANIFEST = {"pages": [{"filename": "page-0013-aaaa.jpg", "page_id": PAGE["page_id"], "volume_id": "77",
                       "image_sha256": "a" * 64}]}


def test_tex_escape_covers_specials():
    assert tex_escape("a & b % c _ d {e} f$") == r"a \& b \% c \_ d \{e\} f\$"


def test_render_page_tex_has_sections_and_record():
    tex = render_page_tex(PAGE, "a" * 64, "77")
    assert r"\subsection*{Practical Building}" in tex
    assert "Image SHA-256" in tex
    assert "a" * 64 in tex
    assert r"\end{document}" in tex


def test_check_links_finds_missing_targets(tmp_path):
    (tmp_path / "a.html").write_text(
        '<a href="b.html">b</a><a href="missing.html">m</a><img src="https://x/y.png">', encoding="utf-8")
    (tmp_path / "b.html").write_text("ok", encoding="utf-8")
    assert check_links(tmp_path) == ["a.html -> missing.html"]


def test_build_site_without_matches(tmp_path, monkeypatch):
    work = tmp_path / "artifacts"
    (work / "extract" / "derived").mkdir(parents=True)
    (work / "extract" / "derived" / "page-0013-aaaa.jpg.json").write_text(json.dumps(PAGE), encoding="utf-8")
    (work / "extract" / "coverage.json").write_text(json.dumps(
        {"pages_total": 1, "pages_ok": 1, "pages_failed": 0, "entries": 1, "joins": 0, "failures": []}), encoding="utf-8")
    monkeypatch.setattr("nemotron_challenge.site_build.load_manifest", lambda: MANIFEST)
    result = build_site(Settings(db_path=tmp_path / "db.lancedb"), work, out_dir=tmp_path / "site", compile_pdfs=False)
    assert result["pages"] == 1
    assert result["broken_links"] == []
    index = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "page-0013-aaaa.jpg" in index
    page_html = (tmp_path / "site" / "page-0013-aaaa.html").read_text(encoding="utf-8")
    assert "Practical Building" in page_html
    assert "a" * 64 in page_html
    compare = (tmp_path / "site" / "compare.html").read_text(encoding="utf-8")
    assert "No comparisons yet" in compare
