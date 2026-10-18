"""Compare matched texts: normalization, frequencies, distinctive terms, plots."""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .config import Settings
from .pipeline import append_jsonl, read_jsonl, write_json

METHOD = (
    "Token frequency and Laplace-smoothed log-odds on matched pairs. "
    "Tokens are lowercase letter runs of two or more characters; stopwords are removed."
)

STOPWORDS = set(
    """
    a about above after again against all am an and any are as at be because been before being below
    between both but by can did do does doing down during each few for from further had has have having
    he her here hers herself him himself his how i if in into is it its itself just me more most my
    myself no nor not now of off on once only or other our ours ourselves out over own same she should
    so some such than that the their theirs them themselves then there these they this those through to
    too under until up very was we were what when where which while who whom why will with you your
    yours yourself yourselves shall may might must one two also upon any every into onto yet thus
    """.split()
)

LIGATURES = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\u00e6": "ae", "\u0153": "oe"}
TOKEN = re.compile(r"[a-z][a-z']*")


def normalize(text: str) -> tuple[list[str], dict[str, int]]:
    """Lowercase, fold long s and ligatures, then keep letter tokens. Log every change."""
    changes: dict[str, int] = {}
    lowered = text.lower()
    changes["long_s"] = lowered.count("\u017f")
    for ligature, replacement in LIGATURES.items():
        count = lowered.count(ligature)
        if count:
            changes[f"ligature_{replacement}"] = count
        lowered = lowered.replace(ligature, replacement)
    lowered = lowered.replace("\u017f", "s")
    tokens = [token.strip("'") for token in TOKEN.findall(lowered)]
    return [token for token in tokens if len(token) >= 2], changes


def top_terms(tokens: list[str], limit: int = 25) -> list[list[Any]]:
    """Most frequent non-stopword tokens as [term, count] rows."""
    counts = Counter(token for token in tokens if token not in STOPWORDS)
    return [[term, count] for term, count in counts.most_common(limit)]


def log_odds(a: Counter, b: Counter, limit: int = 25) -> list[dict[str, Any]]:
    """Terms that separate two counters, ranked by the absolute log-odds value."""
    total_a, total_b = sum(a.values()), sum(b.values())
    scored = []
    for term in set(a) | set(b):
        p_a = (a[term] + 1) / (total_a + 2)
        p_b = (b[term] + 1) / (total_b + 2)
        scored.append({"term": term, "log_odds": round(math.log(p_a / p_b), 4),
                       "count_a": a[term], "count_b": b[term]})
    return sorted(scored, key=lambda row: -abs(row["log_odds"]))[:limit]


def compare_pair(entry: dict[str, Any], match: dict[str, Any], article: dict[str, Any]) -> dict[str, Any]:
    """Build one comparison record with citations to both sources."""
    entry_tokens, entry_changes = normalize(entry["body"])
    article_tokens, article_changes = normalize(article["text"])
    entry_counts = Counter(token for token in entry_tokens if token not in STOPWORDS)
    article_counts = Counter(token for token in article_tokens if token not in STOPWORDS)
    teh = sum(entry_counts.values()) or 1
    tah = sum(article_counts.values()) or 1
    return {
        "entry_id": match["entry_id"],
        "entry_title": match["entry_title"],
        "article_title": match["article_title"],
        "match_confidence": match["match_confidence"],
        "method": METHOD,
        "britannica": {
            "page_id": match["page_id"],
            "scan": match.get("scan", ""),
            "scan_sha256": match.get("scan_sha256", ""),
            "heading_class": entry.get("heading_class", ""),
            "excerpt": entry["body"][:400],
            "tokens": len(entry_tokens),
            "types": len(set(entry_tokens)),
            "type_token_ratio": round(len(set(entry_tokens)) / max(len(entry_tokens), 1), 4),
            "top_terms": top_terms(entry_tokens),
        },
        "wikipedia": {
            "page_id": article["page_id"],
            "revision_id": article["revision_id"],
            "url": article["url"],
            "text_sha256": article["provenance"]["text_sha256"],
            "excerpt": article["text"][:400],
            "tokens": len(article_tokens),
            "types": len(set(article_tokens)),
            "type_token_ratio": round(len(set(article_tokens)) / max(len(article_tokens), 1), 4),
            "top_terms": top_terms(article_tokens),
        },
        "distinctive": {
            "britannica": log_odds(entry_counts, article_counts),
            "wikipedia": log_odds(article_counts, entry_counts),
        },
        "normalization": {"britannica": entry_changes, "wikipedia": article_changes},
        "citations": [
            {"source": "britannica", "page_id": match["page_id"], "scan": match.get("scan", ""),
             "sha256": match.get("scan_sha256", "")},
            {"source": "wikipedia", "page_id": article["page_id"], "revision_id": article["revision_id"],
             "url": article["url"], "sha256": article["provenance"]["text_sha256"]},
        ],
    }


def chart_rows(comparisons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per compared pair. The plot data must count exactly these documents."""
    return [
        {
            "entry_id": row["entry_id"],
            "article_title": row["article_title"],
            "tokens_britannica": row["britannica"]["tokens"],
            "tokens_wikipedia": row["wikipedia"]["tokens"],
            "types_britannica": row["britannica"]["types"],
            "types_wikipedia": row["wikipedia"]["types"],
        }
        for row in comparisons
    ]


def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def plot_pair(row: dict[str, Any], path: Path) -> None:
    """Grouped bars of the ten most frequent terms on each side."""
    plt = _pyplot()
    wiki = dict((term, count) for term, count in row["wikipedia"]["top_terms"][:10])
    brit = dict((term, count) for term, count in row["britannica"]["top_terms"][:10])
    terms = list(dict.fromkeys(list(brit)[:10] + list(wiki)[:10]))[:14]
    positions = range(len(terms))
    figure, axis = plt.subplots(figsize=(9, 4.5))
    axis.bar([p - 0.2 for p in positions], [brit.get(term, 0) for term in terms], width=0.4, label="Britannica 1768")
    axis.bar([p + 0.2 for p in positions], [wiki.get(term, 0) for term in terms], width=0.4, label="Wikipedia")
    axis.set_xticks(list(positions))
    axis.set_xticklabels(terms, rotation=45, ha="right")
    axis.set_ylabel("count")
    axis.set_title(f"{row['entry_title'][:60]} vs {row['article_title'][:60]}")
    axis.legend()
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=120)
    plt.close(figure)


def plot_corpus(rows: list[dict[str, Any]], path: Path) -> None:
    """Total tokens per compared pair across the corpus."""
    plt = _pyplot()
    figure, axis = plt.subplots(figsize=(10, 5))
    labels = [row["entry_id"].split(":")[-1] for row in rows]
    axis.bar([p - 0.2 for p in range(len(rows))], [row["tokens_britannica"] for row in rows], width=0.4, label="Britannica")
    axis.bar([p + 0.2 for p in range(len(rows))], [row["tokens_wikipedia"] for row in rows], width=0.4, label="Wikipedia")
    axis.set_xticks(range(len(rows)))
    axis.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    axis.set_ylabel("tokens")
    axis.set_title(f"Compared documents: {len(rows)}")
    axis.legend()
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=120)
    plt.close(figure)


def corpus_summary(comparisons: list[dict[str, Any]], limit: int = 30) -> dict[str, Any]:
    brit: Counter = Counter()
    wiki: Counter = Counter()
    for row in comparisons:
        brit.update(dict((term, count) for term, count in row["britannica"]["top_terms"]))
        wiki.update(dict((term, count) for term, count in row["wikipedia"]["top_terms"]))
    return {
        "pairs": len(comparisons),
        "top_britannica": [[term, count] for term, count in brit.most_common(limit)],
        "top_wikipedia": [[term, count] for term, count in wiki.most_common(limit)],
    }


def run_compare(settings: Settings, work_dir: Path, *, limit: int | None = None) -> dict[str, Any]:
    """Compare every matched pair. Resume skips pairs already saved."""
    match_dir = work_dir / "match"
    matches = read_jsonl(match_dir / "matches.jsonl")
    if not matches:
        raise ValueError("no matches found; run the match stage first")
    entries = {row["entry_id"]: row for row in json.loads(
        (work_dir / "extract" / "derived" / "entries.json").read_text(encoding="utf-8"))}
    compare_dir = work_dir / "compare"
    comparisons_path = compare_dir / "comparisons.jsonl"
    done = {row["entry_id"] for row in read_jsonl(comparisons_path)}
    if limit is not None:
        matches = matches[:limit]
    failures: list[dict[str, Any]] = []
    for index, match in enumerate(matches, start=1):
        entry_id = match["entry_id"]
        if entry_id in done:
            continue
        print(f"[compare] {index}/{len(matches)} {entry_id}", file=sys.stderr, flush=True)
        try:
            entry = entries[entry_id]
            article = json.loads((match_dir / "articles" / f"{match['article_page_id']}.json").read_text(encoding="utf-8"))
            append_jsonl(comparisons_path, [compare_pair(entry, match, article)])
        except (KeyError, OSError, ValueError) as exc:
            failures.append({"entry_id": entry_id, "error": f"{type(exc).__name__}: {exc}"})
    comparisons = read_jsonl(comparisons_path)
    rows = chart_rows(comparisons)
    plot_failures: list[str] = []
    try:
        plot_corpus(rows, compare_dir / "plots" / "corpus.png")
        for row in comparisons[:12]:
            plot_pair(row, compare_dir / "plots" / f"pair-{row['entry_id'].split(':')[-1]}.png")
    except ImportError as exc:
        plot_failures.append(f"matplotlib unavailable: {exc}")
    summary = corpus_summary(comparisons)
    summary.update({"plots": len(rows[:12]) + 1 if not plot_failures else 0,
                    "plot_failures": plot_failures, "failures": failures})
    write_json(compare_dir / "summary.json", summary)
    return {"stage": "compare", "artifacts": str(compare_dir), "pairs": len(comparisons),
            "chart_rows": len(rows), "failures": failures}
