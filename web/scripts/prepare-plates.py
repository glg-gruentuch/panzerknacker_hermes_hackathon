"""Prepare the engraved plates shown behind the landing page.

Reads the pinned Britannica parquet (fetch it with `uv run nemotron-challenge data fetch`),
turns the yellowed paper white so only the ink remains, crops the page margins,
and writes web/public/plates/<slug>.jpg plus web/src/config/plates.json.

Run from the repository root:
    uv run --with pillow python web/scripts/prepare-plates.py
"""

import glob
import hashlib
import io
import json
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image, ImageOps

REVISION = "309f765b1ecc83e0a7f7762e44b4a927a7555443"

# slug, source row, title on the plate, optional crop as fractions (left, top, right, bottom)
PLATES = [
    ("anatomy", 1274, "Anatomy", None),
    ("helminthology", 651, "Helminthology", None),
    ("geyser", 1369, "Hver, or boiling fountain", (0.0, 0.0, 1.0, 0.55)),
    ("electricity", 1446, "Electricity", (0.0, 0.17, 1.0, 1.0)),
    ("astronomy", 2176, "Astronomy", None),
]

ROOT = Path(__file__).resolve().parents[2]
OUT_IMG = ROOT / "web" / "public" / "plates"
OUT_JSON = ROOT / "web" / "src" / "config" / "plates.json"


def ink_only(img: Image.Image) -> Image.Image:
    """Grey scale, then stretch so the paper reads as white and the ink stays dark."""
    grey = ImageOps.grayscale(img)
    hist = grey.histogram()
    total = sum(hist)

    def percentile(p: float) -> int:
        seen = 0
        for value, count in enumerate(hist):
            seen += count
            if seen >= total * p:
                return value
        return 255

    paper = percentile(0.60)  # most of a plate is paper
    ink = percentile(0.01)
    span = max(1, paper - 8 - ink)
    lut = [max(0, min(255, round((v - ink) / span * 255))) for v in range(256)]
    return grey.point(lut)


def crop_margins(img: Image.Image) -> Image.Image:
    """Trim the page edge and gutter shadow: keep the box that holds the ink."""
    mask = img.point(lambda v: 255 if v < 150 else 0)
    w, h = img.size
    # Ignore a thin border where the scan shows the book edge.
    inner = mask.crop((int(w * 0.04), int(h * 0.03), int(w * 0.96), int(h * 0.97)))
    box = inner.getbbox()
    if not box:
        return img
    pad = 10
    left, top, right, bottom = box
    return img.crop(
        (
            max(0, left + int(w * 0.04) - pad),
            max(0, top + int(h * 0.03) - pad),
            min(w, right + int(w * 0.04) + pad),
            min(h, bottom + int(h * 0.03) + pad),
        )
    )


def main() -> None:
    source = glob.glob(str(ROOT / "data" / "cache" / "**" / "*.parquet"), recursive=True)
    if not source:
        raise SystemExit("Parquet not found. Run `uv run nemotron-challenge data fetch` first.")
    table = pq.read_table(source[0], columns=["image", "id", "meta"])
    OUT_IMG.mkdir(parents=True, exist_ok=True)
    records = []
    for slug, row, title, crop in PLATES:
        raw = table.column("image")[row].as_py()["bytes"]
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        if crop:
            w, h = img.size
            img = img.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
        out = crop_margins(ink_only(img))
        path = OUT_IMG / f"{slug}.jpg"
        out.save(path, quality=84, optimize=True, progressive=True)
        records.append(
            {
                "slug": slug,
                "title": title,
                "src": f"/plates/{slug}.jpg",
                "width": out.width,
                "height": out.height,
                "pageId": f"britannica:{REVISION}:train:{row}",
                "row": row,
                "volumeId": table.column("id")[row].as_py(),
                "meta": table.column("meta")[row].as_py(),
                "sourceSha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        print(f"{path.relative_to(ROOT)}  {out.width}x{out.height}  {path.stat().st_size // 1024} KiB")
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
    print(OUT_JSON.relative_to(ROOT))


if __name__ == "__main__":
    main()
