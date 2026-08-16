# YouTube Downloader CLI with yt-dlp

## Overview

This Python script provides an interactive command-line interface to download **videos**, **audio**, **playlists**, and **subtitles** from YouTube. It uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) and **ffmpeg** for merging and converting media.

**Prefer a graphical interface?** See [Tube Fetch Desktop](#tube-fetch-desktop-windows) below — a local
web-based GUI for Windows with the same features (video/audio/playlist/subtitles), packaged as a
one-click installer, no Python or ffmpeg setup required.

---

## Features

- Download full video as `.mp4` (best available quality)
- Download audio only as `.mp3`
- Download full playlists (video or audio)
- Download **subtitles only** (manual or auto) in any language
- Choose output directory for each run

---

## Requirements

- **Python 3.7+**
- **yt-dlp:** `pip install -U "yt-dlp[default]"` (or `py -m pip install -U "yt-dlp[default]"` on Windows)  
  This installs yt-dlp with the recommended EJS scripts package (`yt-dlp-ejs`) for solving YouTube JS challenges.
- **ffmpeg** (for merging video+audio and converting to MP3)

### Installing ffmpeg

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install ffmpeg
```

**Fedora:**

```bash
sudo dnf install ffmpeg
```

**Windows:** Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

---

## Project structure

```
.
├── main.py                              # CLI script with interactive menu
├── readme.md                            # This documentation
├── notes.txt                            # Optional local notes
├── webapp/                              # Tube Fetch Desktop (local web GUI, source)
│   ├── app.py, downloader.py, jobs.py   # Flask app + async download jobs (same engine as the CLI)
│   ├── launcher.py                      # Entry point: starts the local server and opens the browser
│   ├── templates/, static/              # UI (mode picker, live log, file downloads)
│   └── requirements.txt
├── packaging/                           # Windows build: PyInstaller spec + Inno Setup installer script
└── .github/workflows/build-windows.yml  # Builds the .exe on a real Windows runner, publishes a Release
```

---

## Tube Fetch Desktop (Windows) {#tube-fetch-desktop-windows}

A local, no-install-hassle graphical version of this CLI: same video/audio/playlist/subtitles
features, in a clean web-based interface that opens in your browser — but everything runs on
**your own machine**, packaged as a single Windows installer (Python, ffmpeg and the JS runtime
needed by yt-dlp are all bundled in).

### Install

1. Go to the [**Releases**](../../releases) page of this repository.
2. Download the latest `TubeFetchDesktop-Setup-*.exe`.
3. Run it and follow the installer (Portuguese/English). A desktop shortcut is optional.
4. Launch **Tube Fetch Desktop** — it opens `http://127.0.0.1:5000` in your default browser
   automatically. Closing the black console window stops the local server.

Because it runs from your own residential IP (not a cloud/datacenter IP), most videos download
**without needing `cookies.txt`** — unlike a cloud-hosted deployment of the same tool, which
YouTube treats with far more suspicion. `cookies.txt` is still available as an optional,
collapsed field for private/age-restricted/members-only videos.

### Building it yourself

The installer is built by [`.github/workflows/build-windows.yml`](.github/workflows/build-windows.yml)
on a `windows-latest` GitHub Actions runner (PyInstaller can't reliably cross-compile Windows
binaries from Linux/macOS). It runs automatically on every push to `main` that touches `webapp/`
or `packaging/`, and publishes the resulting `.exe` as a new GitHub Release. You can also trigger
it manually from the **Actions** tab (`workflow_dispatch`).

To run from source instead (any OS, for development):

```bash
cd webapp
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python launcher.py
```

---

## How to run

```bash
python main.py
```

On Windows (if `python` is not in PATH):

```bash
py main.py
```

---

## Menu options

When you start the script you will see:

```
=== YouTube Downloader ===
[1] Download video (.mp4)
[2] Download audio (.mp3)
[3] Download playlist (videos, .mp4)
[4] Download playlist (audio, .mp3)
[5] Download subtitles only
[6] Exit
```

You choose an option, enter the video or playlist URL, then enter (or confirm) the output folder.

**Output folder:**

- If you press Enter without typing a path, the default is `~/Downloads` (change this in the code if needed).
- If the path does not exist, it is created automatically.

---

## Option details

| Option | Description |
|--------|-------------|
| **[1] Video** | Downloads best video+audio and merges to `.mp4`. |
| **[2] Audio** | Extracts audio and converts to `.mp3` (192 kbps). |
| **[3] Playlist (video)** | Downloads all videos in the playlist into a folder named after the playlist. |
| **[4] Playlist (audio)** | Same as above but audio only (`.mp3`). |
| **[5] Subtitles only** | Lets you pick language (via menu) and manual vs automatic subtitles (`.srt`). |

---

## Example usage

### Download automatic subtitles (with browser cookies)

```
Choose an option [1-6]: 5
Enter video or playlist URL: https://www.youtube.com/watch?v=...
Enter output folder name: subtitles
Use browser cookies for authentication? (needed for private/age-restricted videos) [y/N]: y

Select browser for cookies:
[1] Chrome
[2] Firefox
[3] Brave
[4] Edge
Choose an option [1-4, default 1]: 2

Select subtitle language:
[1] pt-BR
[2] en
[3] es
[4] other (type code manually)
Choose an option [1-4, default 1]: 2
Use automatic subtitles? [y/N]: y
```

**Download a playlist as audio:**

```
Choose an option [1-6]: 4
Enter video or playlist URL: https://www.youtube.com/playlist?list=...
Enter output folder name: my_music
```

---

## File naming

- Single video/audio: filename is the video title.
- Playlists: files go into a folder named after the playlist; each file is numbered (e.g. `1 - Title.mp4`).
- Subtitles: `video-title.srt`.

---

## Permissions

Ensure you have write permission in the output directory you choose.

---

## YouTube / yt-dlp notes

- If you get **403**, **“format not available”**, or **JS challenge / EJS warnings**, update yt-dlp: `pip install -U "yt-dlp[default]"`.
- The script already supports using **browser cookies** via yt-dlp’s `cookiesfrombrowser` option.  
  - On each run, you can choose to use cookies and select the browser (Chrome, Firefox, Brave, Edge).  
  - This is recommended for **private**, **age-restricted** or **Premium-only** videos.

---

## Possible future improvements

- ~~GUI~~ → done, see [Tube Fetch Desktop](#tube-fetch-desktop-windows)
- Convert `.srt` to `.txt`
- Burn subtitles into video with ffmpeg
- Support other sites (Vimeo, TikTok, etc.)
- Export metadata to JSON/CSV
- Automate downloads (e.g. RSS or “watch later” queue)

---

## License / author

Free to use and modify. Original author: Cleverson — DevOps Engineer.
