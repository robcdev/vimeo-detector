#!/usr/bin/env python3
"""Download Vimeo videos listed in a links file, using yt-dlp.

Interactive — run it yourself:
  python3 scripts/download_vimeo_videos.py

What it does, in order:
  1. Checks that yt-dlp is installed. If it isn't, it tells you how to
     install it and stops (it will not install anything for you).
  2. Checks that ffmpeg is installed — yt-dlp needs it to merge the
     separate video and audio streams into a single file; without it
     you end up with two files per video. If it isn't found on PATH,
     asks whether you already have it installed somewhere and, if so,
     the folder its binary lives in (passed to yt-dlp as
     --ffmpeg-location). Otherwise stops with install instructions.
  3. Asks for the path to the file that holds the Vimeo links (e.g. the
     videos/vimeo_links.txt produced by find_vimeo_links.py).
  4. Asks whether the download needs your logged-in browser session
     (some Vimeo embeds refuse anonymous downloads), and if so, which
     browser to pull cookies from, plus an optional path to that
     browser's profile/cookies if auto-detection doesn't find it
     (e.g. "firefox" with path "/home/you/.mozilla/firefox/xxxx.default",
     passed to yt-dlp as --cookies-from-browser firefox:<path>).
  5. After you confirm, downloads each unique video next to the links
     file, one at a time, using the player.vimeo.com/video/<id> URL
     form (plain vimeo.com/<id> links 404 for some of these videos),
     merges audio+video into a single .mp4 via ffmpeg, and reports any
     that failed at the end.
"""

import os
import re
import shutil
import subprocess
import sys

# Matches both "vimeo.com/<id>" and "player.vimeo.com/video/<id>" so the
# links file can contain either form; we always download via the
# player.vimeo.com/video/<id> URL below since plain vimeo.com/<id> links
# 404 for some of these videos.
VIMEO_ID_RE = re.compile(r"(?:player\.)?vimeo\.com/(?:video/)?(\d{6,})", re.IGNORECASE)

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


def check_ffmpeg():
    # Needed to merge the separate video+audio streams yt-dlp downloads
    # into a single file. Without it, you end up with two files per video.
    return shutil.which("ffmpeg")


def prompt(text, default=None):
    suffix = " [{}]".format(default) if default else ""
    try:
        value = input("{}{}: ".format(text, suffix)).strip()
    except EOFError:
        value = ""
    return value or default


def load_links(path):
    links = []
    seen = set()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            for match in VIMEO_ID_RE.finditer(line):
                vid = match.group(1)
                if vid not in seen:
                    seen.add(vid)
                    links.append("https://player.vimeo.com/video/{}".format(vid))
    return links


def main():
    yt_dlp_path = check_yt_dlp()
    if not yt_dlp_path:
        sys.exit(1)
    print("Found yt-dlp at: {}".format(yt_dlp_path))

    ffmpeg_location_args = []
    ffmpeg_path = check_ffmpeg()
    if ffmpeg_path:
        print("Found ffmpeg at: {}".format(ffmpeg_path))
    else:
        print("ffmpeg wasn't found automatically on your PATH.")
        has_ffmpeg = prompt(
            "Do you already have ffmpeg installed somewhere on this machine? (y/n)", "n"
        )
        if has_ffmpeg.lower().startswith("y"):
            ffmpeg_dir = prompt(
                "Path to the folder containing the ffmpeg binary (e.g. C:\\ffmpeg\\bin)"
            )
            if ffmpeg_dir and os.path.isdir(ffmpeg_dir):
                ffmpeg_location_args = ["--ffmpeg-location", ffmpeg_dir]
                print("Will use ffmpeg from: {}".format(ffmpeg_dir))
            else:
                print(
                    "That path wasn't found. Continuing without it — downloads may be "
                    "left as separate audio/video files instead of merged."
                )
        else:
            print("Without ffmpeg, yt-dlp cannot merge video+audio into one file —")
            print("you'll get two separate files per video instead.")
            print("Please install it, then re-run this script. For example:")
            print("  brew install ffmpeg      (Linux/macOS via Homebrew)")
            print("  sudo apt install ffmpeg  (Debian/Ubuntu)")
            print("  winget install ffmpeg    (Windows)")
            sys.exit(1)

    links_file = prompt("Path to the file containing the Vimeo links", "videos/vimeo_links.txt")
    links_file = os.path.abspath(links_file)
    if not os.path.isfile(links_file):
        print("File not found: {}".format(links_file))
        sys.exit(1)

    links = load_links(links_file)
    if not links:
        print("No Vimeo links found in {}".format(links_file))
        sys.exit(1)

    print("Found {} unique video link(s) in {}".format(len(links), links_file))

    cookies_args = []
    use_cookies = prompt(
        "Do these videos need your logged-in browser session (cookies) to download? (y/n)", "n"
    )
    if use_cookies.lower().startswith("y"):
        print("Supported browsers: {}".format(", ".join(SUPPORTED_BROWSERS)))
        browser = prompt("Which browser should yt-dlp pull cookies from?", "firefox")
        profile_path = prompt(
            "Path to that browser's profile/cookies (leave blank to let yt-dlp auto-detect)", ""
        )
        browser_spec = "{}:{}".format(browser, profile_path) if profile_path else browser
        cookies_args = ["--cookies-from-browser", browser_spec]

    out_dir = os.path.dirname(links_file) or "."
    confirm = prompt(
        "Start downloading {} video(s) into {}? (y/n)".format(len(links), out_dir), "y"
    )
    if not confirm.lower().startswith("y"):
        print("Aborted.")
        sys.exit(0)

    output_template = os.path.join(out_dir, "%(title)s [%(id)s].%(ext)s")

    failures = []
    for i, url in enumerate(links, 1):
        print("\n[{}/{}] Downloading {}".format(i, len(links), url))
        cmd = (
            [yt_dlp_path]
            + cookies_args
            + ffmpeg_location_args
            + ["--merge-output-format", "mp4", "-o", output_template, url]
        )
        result = subprocess.run(cmd)
        if result.returncode != 0:
            failures.append(url)

    print("\nDone. {} succeeded, {} failed.".format(len(links) - len(failures), len(failures)))
    if failures:
        print("Failed links:")
        for url in failures:
            print("  " + url)


if __name__ == "__main__":
    main()
