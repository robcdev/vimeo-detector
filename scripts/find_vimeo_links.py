#!/usr/bin/env python3
"""Scan the project tree for Vimeo video links/embeds and list them.

Walks every file under the project root (one level up from this script),
looks for vimeo.com / player.vimeo.com references (including the
URL-encoded form Google Docs exports use, e.g. "vimeo%2Ecom" or
"%3A%2F%2Fplayer.vimeo.com"), and groups the videos it finds by the
top-level page they belong to. Saved-page assets live in a sibling
"<Page Name>_files" folder next to "<Page Name>.html" (the standard
"Save As > Webpage, complete" layout), so a video found inside that
folder is attributed back to "<Page Name>.html".

Output is written to videos/vimeo_links.txt.
"""

import os
import re
from urllib.parse import unquote

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR = os.path.join(ROOT, "videos")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "vimeo_links.txt")

# Only scan text-ish files; skip images/fonts/binaries for speed.
SCAN_EXTENSIONS = {".html", ".htm", ".txt", ".js", ".json", ".css", ".md", ".xml"}

# Directories we never need to walk into.
SKIP_DIRS = {".git"}

VIMEO_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:player\.)?vimeo\.com/[^\s\"'<>\\)\]]+",
    re.IGNORECASE,
)
VIMEO_ID_RE = re.compile(r"vimeo\.com/(?:video/)?(\d{6,})", re.IGNORECASE)


def iter_candidate_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.abspath(path) == os.path.abspath(OUTPUT_FILE):
                continue
            if os.path.abspath(path) == os.path.abspath(__file__):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in SCAN_EXTENSIONS:
                yield path


def page_for(path, root):
    """Map a file path to the top-level page it belongs to."""
    rel = os.path.relpath(path, root)
    parts = rel.split(os.sep)
    if len(parts) == 1:
        return parts[0]
    first = parts[0]
    if first.endswith("_files"):
        candidate = first[: -len("_files")] + ".html"
        if os.path.isfile(os.path.join(root, candidate)):
            return candidate
        return first
    return first


def extract_vimeo_ids(text):
    # Handle both raw and percent-encoded ("%3A%2F%2F...") occurrences.
    decoded = unquote(text)
    haystacks = (text, decoded) if decoded != text else (text,)
    ids = set()
    for chunk in haystacks:
        for match in VIMEO_ID_RE.finditer(chunk):
            ids.add(match.group(1))
    return ids


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pages = {}  # page name -> set of vimeo ids
    all_ids = set()

    for path in iter_candidate_files(ROOT):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue

        if "vimeo" not in text.lower():
            continue

        ids = extract_vimeo_ids(text)
        if not ids:
            continue

        page = page_for(path, ROOT)
        pages.setdefault(page, set()).update(ids)
        all_ids.update(ids)

    lines = []
    lines.append("Vimeo links found under: " + ROOT)
    lines.append("Total unique videos: {}".format(len(all_ids)))
    lines.append("")
    lines.append("=" * 60)
    lines.append("By page")
    lines.append("=" * 60)

    for page in sorted(pages):
        ids = sorted(pages[page], key=int)
        lines.append("")
        lines.append("{} ({} video{})".format(page, len(ids), "" if len(ids) == 1 else "s"))
        for vid in ids:
            lines.append("  https://player.vimeo.com/video/{}".format(vid))

    lines.append("")
    lines.append("=" * 60)
    lines.append("All unique Vimeo links")
    lines.append("=" * 60)
    for vid in sorted(all_ids, key=int):
        lines.append("https://player.vimeo.com/video/{}".format(vid))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("Found {} unique Vimeo video(s) across {} page(s).".format(len(all_ids), len(pages)))
    print("Written to: " + OUTPUT_FILE)


if __name__ == "__main__":
    main()
