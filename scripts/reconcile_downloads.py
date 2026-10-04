#!/usr/bin/env python3
"""Reconcile vimeo_links.txt against what's actually in videos/.

Interactive — run it yourself:
  python3 scripts/reconcile_downloads.py

Why this exists: a video can end up in videos/ without ever being
recorded in downloaded.txt — e.g. you downloaded it by hand with a raw
yt-dlp command instead of going through download_vimeo_videos.py. This
script closes that gap by checking, for every link still listed in
vimeo_links.txt, whether it's actually already sitting in videos/.

What it does, for each link in the list:
  1. Visits the Vimeo URL (via `yt-dlp --skip-download --print`, so
     nothing is downloaded) and reads the title that would be assigned
     to the video's file if it were downloaded now.
  2. Looks in videos/ for a file matching that video — matched by the
     "[<id>]" suffix yt-dlp's default naming (and our own download
     script's output template) puts in every filename, since that's a
     far more reliable key than comparing raw title strings, which can
     get truncated/sanitized differently run to run. The fetched title
     is still shown for context.
  3. If a matching file is found (a "coincidence"):
       - its ID is appended to downloaded.txt (in the same "vimeo <id>"
         format yt-dlp's --download-archive uses), so
         download_vimeo_videos.py will recognize it as done too.
       - it's removed from vimeo_links.txt.
     If no match is found, the link is left untouched in both files.

Nothing is downloaded by this script — it only reads metadata and moves
entries between the two tracking files.
"""

import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

ARCHIVE_FILENAME = "downloaded.txt"

VIMEO_ID_RE = re.compile(r"(?:player\.)?vimeo\.com/(?:video/)?(\d{6,})", re.IGNORECASE)
PAGE_HEADER_RE = re.compile(r"^(?P<page>.+) \((?P<count>\d+) videos?\)$")
PAGE_LINK_RE = re.compile(r"^\s+https://player\.vimeo\.com/video/(\d+)\s*$")

SUPPORTED_BROWSERS = ["chrome", "firefox", "edge", "brave", "opera", "vivaldi", "safari"]


def check_yt_dlp():
    path = shutil.which("yt-dlp")
    if path:
        return path
    print("yt-dlp was not found on your PATH.")
    print("Please install it yourself, then re-run this script. For example:")
    print("  pip install -U yt-dlp")
    print("  (or) brew install yt-dlp")
    print("  (or) see https://github.com/yt-dlp/yt-dlp#installation")
    return None


def prompt(text, default=None):
    suffix = " [{}]".format(default) if default else ""
    try:
        value = input("{}{}: ".format(text, suffix)).strip()
    except EOFError:
        value = ""
    return value or default


def parse_links_file(path):
    """Rebuild the {page: {id, id, ...}} structure find_vimeo_links.py wrote."""
    pages = {}
    current_page = None
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if not line.startswith((" ", "\t")):
                match = PAGE_HEADER_RE.match(line)
                if match:
                    current_page = match.group("page")
                    pages.setdefault(current_page, set())
                continue
            match = PAGE_LINK_RE.match(line)
            if match and current_page:
                pages[current_page].add(match.group(1))
    return pages


def write_links_file(path, pages):
    all_ids = set()
    for ids in pages.values():
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
        if not ids:
            continue
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

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def fetch_title(yt_dlp_path, url, cookies_args):
    cmd = [yt_dlp_path] + cookies_args + ["--skip-download", "--no-warnings", "--print", "%(title)s", url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    title = result.stdout.strip().splitlines()
    return title[-1] if title else None


def find_existing_file(videos_dir, vid):
    marker = "[{}]".format(vid)
    for name in os.listdir(videos_dir):
        if name.endswith(".txt") or name == ".gitkeep":
            continue
        if marker in name:
            return name
    return None


def load_archive_entries(archive_path):
    if not os.path.isfile(archive_path):
        return set()
    with open(archive_path, "r", encoding="utf-8", errors="ignore") as f:
        return {line.strip() for line in f if line.strip()}


def main():
    yt_dlp_path = check_yt_dlp()
    if not yt_dlp_path:
        sys.exit(1)
    print("Found yt-dlp at: {}".format(yt_dlp_path))

    links_file = prompt("Path to the file containing the Vimeo links", "videos/vimeo_links.txt")
    links_file = os.path.abspath(links_file)
    if not os.path.isfile(links_file):
        print("File not found: {}".format(links_file))
        sys.exit(1)

    videos_dir = os.path.dirname(links_file) or "."
    archive_path = os.path.join(videos_dir, ARCHIVE_FILENAME)

    pages = parse_links_file(links_file)
    all_ids = sorted({vid for ids in pages.values() for vid in ids}, key=int)
    if not all_ids:
        print("No links found in {}".format(links_file))
        sys.exit(0)
    print("{} link(s) to check in {}".format(len(all_ids), links_file))

    cookies_args = []
    use_cookies = prompt(
        "Do these videos need your logged-in browser session (cookies) to read their title? (y/n)",
        "n",
    )
    if use_cookies.lower().startswith("y"):
        print("Supported browsers: {}".format(", ".join(SUPPORTED_BROWSERS)))
        browser = prompt("Which browser should yt-dlp pull cookies from?", "firefox")
        profile_path = prompt(
            "Path to that browser's profile/cookies (leave blank to let yt-dlp auto-detect)", ""
        )
        browser_spec = "{}:{}".format(browser, profile_path) if profile_path else browser
        cookies_args = ["--cookies-from-browser", browser_spec]

    confirm = prompt(
        "Check {} link(s) against {} and reconcile? (y/n)".format(len(all_ids), videos_dir), "y"
    )
    if not confirm.lower().startswith("y"):
        print("Aborted.")
        sys.exit(0)

    archive_entries = load_archive_entries(archive_path)
    moved = 0
    unverified = 0

    for i, vid in enumerate(all_ids, 1):
        url = "https://player.vimeo.com/video/{}".format(vid)
        print("\n[{}/{}] Checking {}".format(i, len(all_ids), url))

        title = fetch_title(yt_dlp_path, url, cookies_args)
        if title is None:
            print("  Could not read title (network/auth issue) — leaving it in the list.")
            unverified += 1
            continue
        print("  Title: {}".format(title))

        existing = find_existing_file(videos_dir, vid)
        if not existing:
            print("  Not found in {} yet — leaving it in the list.".format(videos_dir))
            continue

        print("  Match: already downloaded as '{}'".format(existing))
        archive_line = "vimeo {}".format(vid)
        if archive_line not in archive_entries:
            archive_entries.add(archive_line)
        for ids in pages.values():
            ids.discard(vid)
        moved += 1

    with open(archive_path, "w", encoding="utf-8") as f:
        for line in sorted(archive_entries):
            f.write(line + "\n")

    write_links_file(links_file, pages)

    remaining = sum(len(ids) for ids in pages.values())
    print(
        "\nDone. {} moved to {}, {} still pending in {}, {} could not be verified.".format(
            moved, archive_path, remaining, links_file, unverified
        )
    )


if __name__ == "__main__":
    main()
