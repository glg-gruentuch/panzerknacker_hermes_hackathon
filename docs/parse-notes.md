# Parse output notes

Observed format of `nvidia/nemotron-3.5-parse` replies on the 100-scan manifest.
The team recorded these notes from the W1.2 pilot and the full extraction run.

## Block format

Each reply holds one block per line in this shape:

```
<x_0.0576><y_0.0445>292 SHIP-BUILDING.<x_0.6514><y_0.0563><class_Page-header>
```

- `<x_..><y_..>` pairs are normalized bounding box corners (0.0 to 1.0).
- `<class_..>` names the page element. Classes seen: `Page-header`,
  `Section-header`, `Title`, `Text`, `List-item`, `Caption`, `Picture`.
- Blocks are separated by blank lines. Reading order follows the page.
- A block can carry a leading corner pair without a class (rare). The
  extractor keeps the text and drops the box in that case.
- Standalone number lines appear without tags (page numbers). The extractor
  drops them.

## Derived records

`artifacts/extract/raw/<filename>.json` keeps each raw reply unchanged.
`artifacts/extract/derived/page-<..>.json` keeps entries with class, text, and
bounding box per block. `artifacts/extract/derived/entries.json` is the
flattened list used by the match stage.

## Segmentation rules (decided 2026-10-18)

1. `Title` and `Section-header` blocks start an entry.
2. `Text`, `List-item`, and `Caption` blocks attach to the entry above them.
3. `Page-header`, `Page-footer`, and `Page-number` blocks stay out of the
   entry text. The running head is kept per page.
4. A page that opens with text and no heading starts a continuation entry
   named after the running head.
5. Markdown artifacts inside headings (`#`, `**`, `_`, trailing `, :`) are
   cleaned.
6. Continuation joining happens only across page boundaries and only for the
   first entry of a page: a running head that matches the previous page, or a
   repeated heading with identical words and numbers.

## Failure modes seen

- Two scans failed: `page-0452-..` (blank binding, no text) and
  `page-2243-..` (engraved plate, no typeset text). The model replied with a
  repetition loop and stopped at `finish_reason: length` at both the 8,744
  and 16,000 token budgets. Both failures stay in `coverage.json`; the
  degenerate replies are kept in `artifacts/extract/failures/`.
- The scans are 600 px wide. Small type produces OCR errors: `F` for `P`
  (`Fractical Building` for `Practical Building`), dropped letters (`Eta` for
  `Etna`), and `f` for `s` in some long-s words. Errors are reported in
  `artifacts/extract/qa/notes.json` and are not corrected in place.

## Retry policy

Transient errors (429, 503) retry up to four times and honor `Retry-After`.
An incomplete reply retries once with a 16,000 token budget. Every other
error is recorded and the run continues.
