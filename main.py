"""
YouTube Downloader CLI
Downloads videos, audio, playlists, and subtitles from YouTube using yt-dlp.
"""

import yt_dlp
import os

# Avoid 403 on YouTube: prefer clients with direct URLs (android/tv) instead of SABR (web)
EXTRACTOR_ARGS_YOUTUBE = {'youtube': {'player_client': ['android', 'tv_embedded', 'tv']}}


def choose_output_path():
    """Prompt for output directory; create it if it does not exist."""
    path = input("Enter output folder name: ").strip()
    if not path:
        path = os.path.expanduser("~/Downloads")  # Default; change to your path.
    if not os.path.exists(path):
        print(f"Path '{path}' does not exist. Creating...")
        os.makedirs(path)
    return path


def download_video(url, output_path):
    """Download a single video as MP4 (best video+audio, merged)."""
    ydl_opts = {
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'quiet': False,
        'extractor_args': EXTRACTOR_ARGS_YOUTUBE,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_audio(url, output_path):
    """Download audio only as MP3."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
        'extractor_args': EXTRACTOR_ARGS_YOUTUBE,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_playlist(url, output_path, mode):
    """Download a full playlist as video (MP4) or audio (MP3)."""
    if mode == 'video':
        ydl_opts = {
            'outtmpl': f'{output_path}/%(playlist_title)s/%(playlist_index)s - %(title)s.%(ext)s',
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'quiet': False,
            'yes_playlist': True,
            'extractor_args': EXTRACTOR_ARGS_YOUTUBE,
        }
    else:
        ydl_opts = {
            'outtmpl': f'{output_path}/%(playlist_title)s/%(playlist_index)s - %(title)s.%(ext)s',
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': False,
            'yes_playlist': True,
            'extractor_args': EXTRACTOR_ARGS_YOUTUBE,
        }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_subtitles_only(url, output_path):
    """Download subtitles only (manual or auto) in the chosen language."""
    lang = input("Enter subtitle language code (e.g. en, pt): ").strip() or 'en'
    use_auto = input("Use automatic subtitles? [y/N]: ").strip().lower()
    auto_sub = use_auto in ('y', 's')

    ydl_opts = {
        'skip_download': True,
        'writesubtitles': not auto_sub,
        'writeautomaticsub': auto_sub,
        'subtitleslangs': [lang],
        'subtitlesformat': 'srt',
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'quiet': False,
        'extractor_args': EXTRACTOR_ARGS_YOUTUBE,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"\nDownloading subtitles only ({'auto' if auto_sub else 'manual'}) in '{lang}'...")
            ydl.download([url])
            print("\n[OK] Subtitles downloaded successfully.")
    except Exception as e:
        print(f"\n[ERROR] Failed to download subtitles: {e}")


def print_menu():
    """Print the main menu."""
    print("\n=== YouTube Downloader ===")
    print("[1] Download video (.mp4)")
    print("[2] Download audio (.mp3)")
    print("[3] Download playlist (videos, .mp4)")
    print("[4] Download playlist (audio, .mp3)")
    print("[5] Download subtitles only")
    print("[6] Exit")


if __name__ == "__main__":
    while True:
        print_menu()
        choice = input("Choose an option [1-6]: ").strip()

        if choice == '6':
            print("Exiting.")
            break

        url = input("Enter video or playlist URL: ").strip()
        output_path = choose_output_path()

        if choice == '1':
            download_video(url, output_path)
        elif choice == '2':
            download_audio(url, output_path)
        elif choice == '3':
            download_playlist(url, output_path, mode='video')
        elif choice == '4':
            download_playlist(url, output_path, mode='audio')
        elif choice == '5':
            download_subtitles_only(url, output_path)
        else:
            print("[ERROR] Invalid option.")
