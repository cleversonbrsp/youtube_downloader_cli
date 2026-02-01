# YouTube Downloader CLI with yt-dlp

## Overview

This Python script provides an interactive command-line interface to download **videos**, **audio**, **playlists**, and **subtitles** from YouTube. It uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) and **ffmpeg** for merging and converting media.

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
- **yt-dlp:** `pip install yt-dlp` (or `py -m pip install yt-dlp` on Windows)
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
├── main.py      # Main script with interactive menu
├── readme.md    # This documentation
└── notes.txt    # Optional local notes
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
| **[5] Subtitles only** | Lets you pick language and manual vs automatic subtitles (`.srt`). |

---

## Example usage

**Download automatic subtitles in English:**

```
Choose an option [1-6]: 5
Enter video or playlist URL: https://www.youtube.com/watch?v=...
Enter output folder name: subtitles
Enter subtitle language code (e.g. en, pt): en
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

- If you get **403** or **“format not available”**, update yt-dlp: `py -m pip install -U yt-dlp`.
- Optionally use **browser cookies** (e.g. Chrome) for age-restricted or region-locked videos; this would require adding cookie support in the script (see yt-dlp docs for `--cookies-from-browser`).

---

## Possible future improvements

- GUI (e.g. Tkinter or PyQt)
- Convert `.srt` to `.txt`
- Burn subtitles into video with ffmpeg
- Support other sites (Vimeo, TikTok, etc.)
- Export metadata to JSON/CSV
- Automate downloads (e.g. RSS or “watch later” queue)

---

## License / author

Free to use and modify. Original author: Cleverson — DevOps Engineer.
