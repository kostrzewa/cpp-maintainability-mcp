#!/usr/bin/env python3
"""Fetch open-access copies of the references cited in Code Red (arXiv:2203.04374).

Politeness policy:
  * at least 5 seconds between every network attempt;
  * exponential backoff on 429/5xx (5s, 15s, 45s);
  * honour Retry-After;
  * one request at a time (no parallelism);
  * only open-access / repository copies are downloaded.

Outputs (all under references/):
  * NNN_<first author>_<title>_<year>.pdf
  * references.bib
  * manifest.json
  * README.md
  * fetch.log
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
REFDIR = ROOT / "references"
SEED = REFDIR / "seed.json"
MANIFEST = REFDIR / "manifest.json"
BIB = REFDIR / "references.bib"
README = REFDIR / "README.md"
LOG = REFDIR / "fetch.log"

DELAY = 5.0
UA = "maintainability-refs/0.1 (research; contact: bartek@example.org)"
SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": UA,
        "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
    }
)

MAIN_PAPER = {
    "index": 0,
    "source": "manual",
    "authors": ["Adam Tornhill", "Markus Borg"],
    "year": 2022,
    "title": (
        "Code Red: The Business Impact of Code Quality - A Quantitative Study "
        "of 39 Proprietary Production Codebases"
    ),
    "venue": "International Conference on Technical Debt (TechDebt 2022)",
    "doi": "10.48550/arXiv.2203.04374",
    "type": "conference-paper",
    "oa_urls": ["https://arxiv.org/pdf/2203.04374"],
    "url": None,
    "raw": (
        "Adam Tornhill and Markus Borg. 2022. Code Red: The Business Impact of "
        "Code Quality - A Quantitative Study of 39 Proprietary Production "
        "Codebases. In Proc. of the International Conference on Technical Debt."
    ),
}


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def slugify(text: str, maxlen: int | None = None) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    for src, dst in (("ß", "ss"), ("ø", "o"), ("æ", "ae"), ("ł", "l"), ("đ", "d")):
        text = text.replace(src, dst)
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    if not text:
        return "untitled"
    if maxlen and len(text) > maxlen:
        text = text[:maxlen]
        if " " in text:
            text = text.rsplit(" ", 1)[0]
    return text.replace(" ", "_")


def first_author_slug(authors: list[str]) -> str:
    return slugify(authors[0]) if authors else "unknown"


def make_filename(entry: dict) -> str:
    author = first_author_slug(entry.get("authors") or [])
    title = slugify(entry.get("title") or "untitled", maxlen=80)
    year = entry.get("year") or "nd"
    return f"{entry['index']:03d}_{author}_{title}_{year}.pdf"


def bibtype(entry: dict) -> str:
    t = (entry.get("type") or "").lower()
    title = (entry.get("title") or "").lower()
    book_markers = (
        "facts and fallacies",
        "software estimation",
        "case study research",
        "your code as a crime scene",
        "software design x-rays",
        "beyond legacy code",
        "accelerate:",
        "causal inference",
        "anova for the behavioral",
    )
    if t == "book" or any(m in title for m in book_markers):
        return "book"
    if t in ("conference-paper", "proceedings-article"):
        return "inproceedings"
    if t in ("article", "review"):
        return "article"
    if t == "report":
        return "techreport"
    if t in ("web", "preprint"):
        return "misc"
    return "misc"


def bibkey(entry: dict) -> str:
    authors = entry.get("authors") or []
    surname = slugify(authors[0].split()[-1]) if authors else "anon"
    year = entry.get("year") or "nd"
    word = slugify(entry.get("title") or "", maxlen=40).split("_")[0] or "ref"
    return f"{surname}{year}{word}".replace("_", "")


def candidate_urls(entry: dict) -> list[str]:
    urls: list[str] = []
    for url in entry.get("oa_urls") or []:
        if url and url not in urls:
            urls.append(url)
    url = entry.get("url")
    if url and url not in urls:
        urls.append(url)

    def priority(url: str) -> tuple[int, int]:
        low = url.lower()
        secure = 0 if low.startswith("https://") else 1
        if "arxiv.org" in low:
            return (0, secure)
        if any(
            d in low
            for d in (
                "chalmers.se",
                "dash.harvard.edu",
                "constellation.uqac.ca",
                "duo.uio.no",
                "unsworks",
                "uhra.herts.ac.uk",
                "hdl.handle.net",
            )
        ):
            return (1, secure)
        if "stamppdf" in low:
            return (2, secure)
        return (3, secure)

    return sorted(dict.fromkeys(urls), key=priority)


def is_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            if fh.read(5) != b"%PDF-":
                return False
        proc = subprocess.run(
            ["pdfinfo", str(path)], capture_output=True, text=True, timeout=30
        )
        if proc.returncode != 0:
            return False
        match = re.search(r"^Pages:\s+(\d+)", proc.stdout, re.M)
        return bool(match and int(match.group(1)) > 0)
    except Exception:
        return False


def download(url: str, dest: Path) -> bool:
    for attempt in range(1, 3):
        time.sleep(DELAY)
        try:
            log(f"GET {url} (attempt {attempt})")
            resp = SESSION.get(url, timeout=60, allow_redirects=True)
            log(
                f"  -> {resp.status_code} "
                f"{resp.headers.get('content-type', '')} {len(resp.content)} bytes"
            )
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "")
                wait = int(retry_after) if retry_after.isdigit() else DELAY
                if wait > 60:
                    log(f"  Retry-After {wait}s too long; skipping mirror")
                    return False
                log(f"  backoff {wait}s")
                time.sleep(wait)
                continue
            if resp.status_code in (500, 502, 503, 504):
                wait = DELAY * (3 ** (attempt - 1))
                log(f"  backoff {wait}s")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                return False
            if not resp.content.startswith(b"%PDF-"):
                log("  not a PDF; skipping")
                return False
            tmp = dest.with_suffix(".part")
            tmp.write_bytes(resp.content)
            if is_pdf(tmp):
                tmp.replace(dest)
                log(f"  saved {dest.name} ({len(resp.content)} bytes)")
                return True
            log("  invalid PDF; skipping")
            tmp.unlink(missing_ok=True)
            return False
        except Exception as exc:  # noqa: BLE001 - network errors are expected
            log(f"  error: {exc}")
            time.sleep(DELAY * (3 ** (attempt - 1)))
    return False


def status_without_pdf(entry: dict) -> str:
    t = (entry.get("type") or "").lower()
    if t == "web":
        return "web"
    # We know an open-access copy exists, but every mirror blocked us.
    if entry.get("oa_urls"):
        return "oa-blocked"
    kind = bibtype(entry)
    if kind == "book":
        return "book"
    if kind == "techreport":
        return "report"
    if t in (
        "article",
        "review",
        "journal",
        "conference",
        "conference-paper",
        "proceedings-article",
        "preprint",
    ):
        return "paywalled"
    return "not-found"


def tex_escape(text: str) -> str:
    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("$", r"\$")
        .replace("#", r"\#")
        .replace("_", r"\_")
        .replace("{", r"\{")
        .replace("}", r"\}")
    )


def write_bib(entries: list[dict]) -> None:
    lines = [
        "% References cited in arXiv:2203.04374 (Code Red).",
        "% Generated by scripts/fetch_references.py.",
        "",
    ]
    for entry in entries:
        typ = bibtype(entry)
        fields: list[tuple[str, str]] = []
        if entry.get("authors"):
            fields.append(("author", tex_escape(" and ".join(entry["authors"]))))
        if entry.get("title"):
            fields.append(("title", tex_escape(entry["title"])))
        if entry.get("year"):
            fields.append(("year", str(entry["year"])))
        venue = entry.get("venue") or ""
        if typ == "article":
            fields.append(("journal", tex_escape(venue)))
        elif typ == "inproceedings":
            fields.append(("booktitle", tex_escape(venue)))
        elif typ == "book":
            fields.append(("publisher", tex_escape(venue)))
        elif typ == "techreport":
            fields.append(("institution", tex_escape(venue)))
        else:
            fields.append(("howpublished", tex_escape(venue)))
        if entry.get("doi"):
            fields.append(("doi", entry["doi"]))
        if entry.get("source_url"):
            fields.append(("url", entry["source_url"]))
        elif entry.get("url"):
            fields.append(("url", entry["url"]))
        if entry.get("raw"):
            fields.append(("note", tex_escape(entry["raw"])))
        lines.append(f"@{typ}{{{bibkey(entry)},")
        for key, value in fields:
            if value:
                lines.append(f"  {key} = {{{value}}},")
        lines.append("}")
        lines.append("")
    BIB.write_text("\n".join(lines), encoding="utf-8")


def short_citation(entry: dict) -> str:
    authors = entry.get("authors") or []
    if not authors:
        who = "Anon."
    elif len(authors) == 1:
        who = authors[0]
    elif len(authors) == 2:
        who = f"{authors[0]} & {authors[1]}"
    else:
        who = f"{authors[0]} et al."
    year = entry.get("year") or "n.d."
    title = entry.get("title") or ""
    return f"{who} ({year}). {title}"


def write_manifest(entries: list[dict]) -> None:
    payload = {
        "source_paper": {
            "title": MAIN_PAPER["title"],
            "arxiv": "2203.04374",
            "doi": MAIN_PAPER["doi"],
        },
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "references": entries,
    }
    MANIFEST.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def write_readme(entries: list[dict]) -> None:
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.get("status", "unknown")] = (
            counts.get(entry.get("status", "unknown"), 0) + 1
        )
    lines = [
        "# References for Code Red (arXiv:2203.04374)",
        "",
        "Open-access copies of the references cited in:",
        "",
        "> Adam Tornhill and Markus Borg. 2022. *Code Red: The Business Impact of",
        "> Code Quality - A Quantitative Study of 39 Proprietary Production Codebases.*",
        "> International Conference on Technical Debt (TechDebt 2022).",
        "",
        "## Fetch policy",
        "",
        "- One request at a time, with **at least 5 seconds** between attempts.",
        "- Exponential backoff on `429`/`5xx`; `Retry-After` is honoured.",
        "- Only open-access and repository copies are downloaded. Paywalled items",
        "  are recorded with metadata and a link, not downloaded from unauthorised",
        "  sources.",
        "- `oa-blocked` means an open-access copy exists, but the host blocked",
        "  automated download; the DOI/link is recorded for manual retrieval.",
        "- Files are named `NNN_<first author>_<title>_<year>.pdf`.",
        "",
        "## Coverage",
        "",
    ]
    for status in (
        "downloaded",
        "oa-blocked",
        "paywalled",
        "book",
        "report",
        "web",
        "not-found",
    ):
        if status in counts:
            lines.append(f"- **{status}**: {counts[status]}")
    lines += [
        "",
        "## Index",
        "",
        "| # | Citation | Type | Status | File |",
        "|---|----------|------|--------|------|",
    ]
    for entry in entries:
        filename = entry.get("filename") or ""
        if entry.get("status") == "downloaded" and filename:
            file_cell = f"[{filename}]({filename})"
        else:
            link = entry.get("source_url") or entry.get("url") or ""
            if not link and entry.get("doi"):
                link = f"https://doi.org/{entry['doi']}"
            file_cell = f"[link]({link})" if link else "-"
        citation = short_citation(entry).replace("|", "\\|")
        lines.append(
            f"| {entry['index']:03d} | {citation} | {bibtype(entry)} "
            f"| {entry.get('status') or '-'} | {file_cell} |"
        )
    lines += [
        "",
        "## Files",
        "",
        "- `manifest.json` - machine-readable status table (citation, DOI, type,",
        "  status, filename, source URL).",
        "- `references.bib` - BibTeX for all 65 entries (main paper + 64 references).",
        "- `SYNTHESIS.md` - design synthesis linking the paper to the MCP server.",
        "- `seed.json` - parsed bibliography metadata used by the fetcher.",
        "- `fetch.log` - timestamped record of every network attempt.",
        "",
        "## Reproducing",
        "",
        "```bash",
        "python3 scripts/fetch_references.py",
        "```",
        "",
        "The script is idempotent: valid PDFs already present are skipped. Use",
        "`--write-only` to regenerate `references.bib`, `manifest.json`, and this",
        "README from the existing manifest without touching the network.",
        "",
    ]
    README.write_text("\n".join(lines), encoding="utf-8")


def log_summary(entries: list[dict]) -> None:
    downloaded = sum(1 for e in entries if e.get("status") == "downloaded")
    counts: dict[str, int] = {}
    for entry in entries:
        status = entry.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    log(f"done: {downloaded}/{len(entries)} PDFs downloaded")
    log("status: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for entry in entries:
        if entry.get("status") == "downloaded":
            log(f"  {entry['index']:03d} {entry['filename']} <- {entry.get('source_url')}")


def assign_filenames(entries: list[dict]) -> None:
    used: set[str] = set()
    for entry in entries:
        filename = make_filename(entry)
        if filename in used:
            stem = filename[:-4]
            for suffix in "abcdefghijklmnopqrstuvwxyz":
                candidate = f"{stem}{suffix}.pdf"
                if candidate not in used:
                    filename = candidate
                    break
        used.add(filename)
        entry["filename"] = filename


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="print plan only")
    parser.add_argument(
        "--only",
        default="",
        help="comma-separated reference indices to process (e.g. 1,9,36)",
    )
    parser.add_argument(
        "--write-only",
        action="store_true",
        help="regenerate bib/manifest/README from the existing manifest",
    )
    args = parser.parse_args()

    REFDIR.mkdir(parents=True, exist_ok=True)

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    entries = [dict(MAIN_PAPER)] + seed
    assign_filenames(entries)

    if args.dry_run:
        for entry in entries:
            print(f"{entry['filename']}")
            for url in candidate_urls(entry):
                print(f"    {url}")
        return 0

    if args.write_only:
        old = {}
        if MANIFEST.exists():
            old = {
                e["index"]: e
                for e in json.loads(MANIFEST.read_text(encoding="utf-8"))["references"]
            }
        for entry in entries:
            if entry["index"] not in old:
                continue
            for key in ("status", "filename"):
                if key in old[entry["index"]]:
                    entry[key] = old[entry["index"]][key]
            source = old[entry["index"]].get("source_url")
            if source and source != "cached":
                entry["source_url"] = source
            elif entry.get("status") == "downloaded":
                urls = candidate_urls(entry)
                entry["source_url"] = urls[0] if urls else None
            if entry.get("status") != "downloaded":
                entry["status"] = status_without_pdf(entry)
        write_bib(entries)
        write_manifest(entries)
        write_readme(entries)
        log("regenerated outputs from existing manifest")
        log_summary(entries)
        return 0

    only = {int(x) for x in args.only.split(",") if x.strip().isdigit()}
    old = {}
    if only and MANIFEST.exists():
        old = {
            e["index"]: e
            for e in json.loads(MANIFEST.read_text(encoding="utf-8"))["references"]
        }
    for entry in entries:
        if only and entry["index"] not in only:
            if entry["index"] in old:
                for key in ("status", "source_url", "filename"):
                    if key in old[entry["index"]]:
                        entry[key] = old[entry["index"]][key]
            continue
        dest = REFDIR / entry["filename"]
        urls = candidate_urls(entry)
        if dest.exists() and is_pdf(dest):
            entry["status"] = "downloaded"
            if not entry.get("source_url"):
                entry["source_url"] = urls[0] if urls else "cached"
            log(f"SKIP {entry['index']:03d} already present: {dest.name}")
            continue

        if not urls:
            entry["status"] = status_without_pdf(entry)
            log(f"NOPDF {entry['index']:03d} {entry.get('title', '')[:60]} -> {entry['status']}")
            continue

        ok = False
        for url in urls:
            if download(url, dest):
                entry["status"] = "downloaded"
                entry["source_url"] = url
                ok = True
                break
        if not ok:
            entry["status"] = status_without_pdf(entry)
            log(f"FAIL {entry['index']:03d} {entry.get('title', '')[:60]} -> {entry['status']}")

    write_bib(entries)
    write_manifest(entries)
    write_readme(entries)

    log_summary(entries)
    return 0


if __name__ == "__main__":
    sys.exit(main())
