"""
YouTube Downloader CLI
Downloads videos, audio, playlists, and subtitles from YouTube using yt-dlp.
"""

import os
import yt_dlp

# Avoid 403 on YouTube: prefer clients with direct URLs (android/tv) instead of SABR (web)
EXTRACTOR_ARGS_YOUTUBE = {
    'youtube': {
        'player_client': ['android', 'tv_embedded', 'tv'],
    }
}


def ask_cookies_from_browser():
    """
    Optionally ask the user if yt-dlp should use browser cookies
    (equivalent to --cookies-from-browser on the CLI).
    Returns a (browser, profile, keyring) tuple or None.
    """
    use_cookies = input(
        "Use browser cookies for authentication? "
        "(needed for private/age-restricted videos) [y/N]: "
    ).strip().lower()

    if use_cookies not in ("y", "s"):
        return None

    # Small numeric menu for common browsers.
    browser_menu = {
        "1": "chrome",
        "2": "firefox",
        "3": "brave",
        "4": "edge",
    }

    print("\nSelect browser for cookies:")
    print("[1] Chrome")
    print("[2] Firefox")
    print("[3] Brave")
    print("[4] Edge")

    choice = input("Choose an option [1-4, default 1]: ").strip() or "1"
    browser = browser_menu.get(choice)
    if browser is None:
        print("[WARN] Invalid choice, falling back to Chrome.")
        browser = "chrome"

    # profile=None, keyring=None → let yt-dlp auto-detect the default profile
    return (browser, None, None)


def choose_output_path():
    """Prompt for output directory; create it if it does not exist."""
    path = input("Enter output folder name: ").strip()
    if not path:
        path = os.path.expanduser("~/Downloads")  # Default; change to your path.
    if not os.path.exists(path):
        print(f"Path '{path}' does not exist. Creating...")
        os.makedirs(path)
    return path


def download_video(url, output_path, cookiesfrombrowser=None):
    """Download a single video as MP4 (best video+audio, merged)."""
    ydl_opts = {
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'quiet': False,
        'extractor_args': EXTRACTOR_ARGS_YOUTUBE,
        'js_runtimes': {'node': None},
    }
    if cookiesfrombrowser is not None:
        ydl_opts['cookiesfrombrowser'] = cookiesfrombrowser
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_audio(url, output_path, cookiesfrombrowser=None):
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
        'js_runtimes': {'node': None},
    }
    if cookiesfrombrowser is not None:
        ydl_opts['cookiesfrombrowser'] = cookiesfrombrowser
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_playlist(url, output_path, mode, cookiesfrombrowser=None):
    """Download a full playlist as video (MP4) or audio (MP3)."""
    if mode == 'video':
        ydl_opts = {
            'outtmpl': f'{output_path}/%(playlist_title)s/%(playlist_index)s - %(title)s.%(ext)s',
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'quiet': False,
            'yes_playlist': True,
            'extractor_args': EXTRACTOR_ARGS_YOUTUBE,
            'js_runtimes': {'node': None},
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
            'js_runtimes': {'node': None},
        }
    if cookiesfrombrowser is not None:
        ydl_opts['cookiesfrombrowser'] = cookiesfrombrowser
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_subtitles_only(url, output_path, cookiesfrombrowser=None):
    """Download subtitles only (manual or auto) in the chosen language.

    Implemented to mirror the working CLI pattern, e.g.:
      yt-dlp URL --skip-download --write-auto-sub --sub-lang pt --sub-format srt
                 --check-formats no --ignore-no-formats-error [...]
    """
    # Numeric menu for common subtitle languages, with an "other" option
    # if the user wants to type a custom language code.
    print("\nSelect subtitle language:")
    print("[1] pt-BR")
    print("[2] en")
    print("[3] es")
    print("[4] other (type code manually)")
    lang_choice = input("Choose an option [1-4, default 1]: ").strip() or "1"

    if lang_choice == "1":
        lang = "pt"
    elif lang_choice == "2":
        lang = "en"
    elif lang_choice == "3":
        lang = "es"
    else:
        lang = input("Enter subtitle language code (e.g. en, pt-BR): ").strip() or "en"
    use_auto = input("Use automatic subtitles? [y/N]: ").strip().lower()
    auto_sub = use_auto in ('y', 's')

    # Single yt-dlp instance with options equivalent to the CLI command
    # that you confirmed works.
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': not auto_sub,
        'writeautomaticsub': auto_sub,
        'subtitleslangs': [lang],
        'subtitlesformat': 'srt',
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        # Avoid falhar só porque não há formatos de vídeo/áudio usáveis
        'check_formats': 'no',
        'ignore_no_formats_error': True,
        'quiet': False,
        'extractor_args': EXTRACTOR_ARGS_YOUTUBE,
    }
    if cookiesfrombrowser is not None:
        ydl_opts['cookiesfrombrowser'] = cookiesfrombrowser

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(
                f"\nDownloading subtitles only ({'auto' if auto_sub else 'manual'}) in '{lang}'..."
            )
            ydl.download([url])
            print("\n[OK] Subtitles downloaded successfully.")
    except Exception as e:
        msg = str(e)
        print(f"\n[ERROR] Failed to download subtitles: {msg}")
        if "--cookies-from-browser" in msg or "Sign in to confirm you’re not a bot" in msg:
            print(
                "\n[HINT] This video requires authentication. "
                "Run the command again and choose 'y' when asked about "
                "using browser cookies, then select a browser where you "
                "are logged into YouTube with access to this video."
            )


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
        cookiesfrombrowser = ask_cookies_from_browser()

        if choice == '1':
            download_video(url, output_path, cookiesfrombrowser=cookiesfrombrowser)
        elif choice == '2':
            download_audio(url, output_path, cookiesfrombrowser=cookiesfrombrowser)
        elif choice == '3':
            download_playlist(
                url, output_path, mode='video', cookiesfrombrowser=cookiesfrombrowser
            )
        elif choice == '4':
            download_playlist(
                url, output_path, mode='audio', cookiesfrombrowser=cookiesfrombrowser
            )
        elif choice == '5':
            download_subtitles_only(
                url, output_path, cookiesfrombrowser=cookiesfrombrowser
            )
        else:
            print("[ERROR] Invalid option.")
