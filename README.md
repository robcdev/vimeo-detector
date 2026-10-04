# Vimeo link scanner & downloader

Three scripts to find the Vimeo videos embedded across the saved pages in
this project, download them, and keep track of what's already done.

## Requirements

- Python 3
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — `pip install -U yt-dlp`
- [ffmpeg](https://ffmpeg.org/) — needed to merge the separate video/audio
  streams yt-dlp downloads into a single file (`brew install ffmpeg`,
  `sudo apt install ffmpeg`, or `winget install ffmpeg` on Windows).

Both scripts check for their respective dependency on startup and stop with
install instructions if something is missing.

## 1. Find the Vimeo links — `scripts/find_vimeo_links.py`

Scans every file in this project (the saved `.html` pages and their
`_files` asset folders), finds every Vimeo video reference — including
links Google Docs URL-encodes on export — and writes the result to
`videos/vimeo_links.txt`, grouped by the page each video appears on.

```bash
python3 scripts/find_vimeo_links.py
```

Re-run it any time a page is added or re-saved to refresh the list.

## 2. Download the videos — `scripts/download_vimeo_videos.py`

Interactive — run it yourself (it won't download anything without your
confirmation):

```bash
python3 scripts/download_vimeo_videos.py
```

It will:

1. Check that `yt-dlp` and `ffmpeg` are installed.
2. Ask for the path to the links file (defaults to `videos/vimeo_links.txt`).
3. Ask whether the videos need your logged-in browser session (cookies) to
   download. If so, it asks which browser, plus an optional path to that
   browser's profile/cookies if yt-dlp can't auto-detect it, e.g.:
   ```
   Which browser should yt-dlp pull cookies from? firefox
   Path to that browser's profile/cookies (leave blank to let yt-dlp auto-detect): /home/you/.mozilla/firefox/xxxxxxxx.default
   ```
   (this is passed to yt-dlp as `--cookies-from-browser firefox:<path>`)
4. Ask for confirmation, then download each unique video — using the
   `https://player.vimeo.com/video/<id>` URL form, since plain
   `vimeo.com/<id>` links 404 for some of these videos — merging
   audio+video into a single `.mp4` next to the links file (i.e. into
   `videos/`).
5. Report a summary of any downloads that failed.

### Tracking what's already downloaded

Every completed video (downloaded **and** merged successfully) is recorded
by ID in `videos/downloaded.txt`. On the next run, anything already listed
there is skipped. Anything not listed — including a video left
half-downloaded by an interrupted run — is downloaded again from scratch,
it's never silently resumed from a partial file. `downloaded.txt` is a
local tracking artifact, like `vimeo_links.txt`, so it isn't committed to
the repo (see `.gitignore`).

### Notes on cookies

Some videos are private/domain-restricted and need an authenticated
session to download:

- If you hit `Could not copy Chrome cookie database`, Chrome is locking its
  cookie file while running — fully quit Chrome first.
- If you hit `Failed to decrypt with DPAPI` on Windows (Chrome's newer
  App-Bound Encryption), switch to `--cookies-from-browser firefox` instead,
  or export cookies manually to a `cookies.txt` file and use
  `--cookies cookies.txt`.
- If you hit a TLS-fingerprint block, install the `curl_cffi` extra
  (`pip install -U "yt-dlp[curl-cffi]"`) and add `--impersonate chrome`.

## 3. Reconcile already-downloaded videos — `scripts/reconcile_downloads.py`

Closes the gap for videos that ended up in `videos/` without going through
`download_vimeo_videos.py` — e.g. downloaded by hand with a raw `yt-dlp`
command.

```bash
python3 scripts/reconcile_downloads.py
```

For every link still listed in `vimeo_links.txt`, it:

1. Visits the video's URL (via `yt-dlp --skip-download --print`, so nothing
   is downloaded) and reads the title that would be assigned to it.
2. Looks in `videos/` for a file matching that video, keyed off the
   `[<id>]` suffix yt-dlp's default naming (and our own download script's
   output template) puts in every filename — more reliable than comparing
   title strings, which can get sanitized or truncated differently from
   run to run. The fetched title is still printed for context.
3. On a match, appends the video to `videos/downloaded.txt` (same format
   `--download-archive` uses) and removes it from `vimeo_links.txt`,
   rewritten in the same format `find_vimeo_links.py` produces. No match,
   or the title couldn't be read (network/auth), leaves the entry
   untouched in the list.

It asks about browser cookies the same way the download script does, since
reading metadata for private videos needs the same auth.

## Manually merging audio + video

If you ever download a video's audio and video streams separately, merge
them with ffmpeg:

```bash
ffmpeg -i video.mp4 -i audio.m4a -c copy output.mp4
```

If `-c copy` errors on incompatible streams, re-encode just the audio:

```bash
ffmpeg -i video.mp4 -i audio.m4a -c:v copy -c:a aac output.mp4
```

## What's tracked in this repo

Only `scripts/`, `videos/` (minus the generated `vimeo_links.txt`), and this
`README.md` are committed — see `.gitignore`. The saved source pages
(`*.html` and their `_files` folders) stay local only.
