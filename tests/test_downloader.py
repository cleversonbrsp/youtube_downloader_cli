import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "webapp"))

import yt_dlp  # noqa: E402

import downloader  # noqa: E402
from app import app  # noqa: E402
from platforms import INSTAGRAM, OTHER, YOUTUBE, detect_platform  # noqa: E402

REEL = "https://www.instagram.com/reel/Chunk8-jurw/"  # vídeo sem faixa de áudio
REEL_WITH_AUDIO = "https://www.instagram.com/reel/CDUMkliABpa/"


class FakeYDL:
    """Substitui o YoutubeDL: guarda as opções e simula sucesso ou falha, sem rede."""

    opts = None
    error = None
    raises = None
    creates_file = True

    def __init__(self, opts):
        type(self).opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def download(self, _urls):
        if self.raises:
            raise yt_dlp.utils.DownloadError(self.raises)
        if self.error:
            self.opts["logger"].error(self.error)
        elif self.creates_file:
            (Path(self.opts["outtmpl"]).parent / "video.mp4").write_bytes(b"x")
            for hook in self.opts["progress_hooks"]:
                hook({"status": "finished", "filename": "video.mp4"})

    def extract_info(self, *_a, **_k):
        return {"entries": []}


class PlatformTest(unittest.TestCase):
    def test_detection(self):
        for url in (REEL, "instagram.com/p/abc/", "https://m.instagram.com/stories/a/1"):
            self.assertEqual(detect_platform(url), INSTAGRAM, url)
        for url in ("https://youtu.be/x", "https://music.youtube.com/watch?v=x"):
            self.assertEqual(detect_platform(url), YOUTUBE, url)
        for url in (
            "https://instagram.com.evil.example/p/1",
            "https://notinstagram.com/p/1",
            "https://example.com/?u=instagram.com",
            "http://[invalid",
            "",
        ):
            self.assertEqual(detect_platform(url), OTHER, url)


class RunJobTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name) / "out"
        self.out.mkdir()
        self.log = Path(tmp.name) / "job.log"
        FakeYDL.error = FakeYDL.raises = None
        FakeYDL.creates_file = True
        patcher = mock.patch.object(downloader.yt_dlp, "YoutubeDL", FakeYDL)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_job(self, mode="video", url=REEL):
        return downloader.run_job(mode=mode, url=url, output_dir=self.out, log_path=self.log)

    def assert_fails(self, fragment, **kwargs):
        with self.assertRaises(downloader.DownloadError) as ctx:
            self.run_job(**kwargs)
        self.assertIn(fragment, str(ctx.exception))

    def test_instagram_video_options(self):
        self.assertEqual(self.run_job(), [])
        self.assertEqual(FakeYDL.opts["format_sort"][1], "vcodec:h264")
        self.assertIn("instagram", FakeYDL.opts["outtmpl"])

    def test_youtube_options_unchanged(self):
        self.run_job(url="https://youtu.be/x")
        self.assertNotIn("format_sort", FakeYDL.opts)
        self.assertTrue(FakeYDL.opts["outtmpl"].endswith("%(title).150B [%(id)s].%(ext)s"))

    def test_instagram_subtitles_rejected(self):
        self.assert_fails("não oferece legendas", mode="subtitles")

    def test_instagram_login_message(self):
        FakeYDL.raises = "ERROR: [Instagram] abc: You need to log in. Use --cookies"
        self.assert_fails("Instagram recusou o acesso")

    def test_instagram_swallowed_error_in_playlist_mode_fails(self):
        FakeYDL.error = "ERROR: [instagram:story] 123: You need to log in to access this content"
        self.assert_fails("Instagram recusou o acesso", mode="playlist_video")

    def test_instagram_without_audio(self):
        FakeYDL.raises = "ERROR: Postprocessing: WARNING: unable to obtain file audio codec with ffprobe"
        self.assert_fails("não tem áudio", mode="audio")

    def test_instagram_without_video(self):
        FakeYDL.creates_file = False
        self.assert_fails("não tem vídeo")

    def test_youtube_login_message_unchanged(self):
        FakeYDL.raises = "Sign in to confirm you're not a bot"
        self.assert_fails("O YouTube pediu confirmação", url="https://youtu.be/x")


class ApiTest(unittest.TestCase):
    def test_instagram_subtitles_return_400(self):
        resp = app.test_client().post("/api/jobs", data={"url": REEL, "mode": "subtitles"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("legendas", resp.get_json()["error"])

    def test_pages(self):
        client = app.test_client()
        self.assertEqual(client.get("/health").status_code, 200)
        self.assertIn("Instagram", client.get("/").get_data(as_text=True))


@unittest.skipUnless(os.environ.get("LIVE_TESTS"), "defina LIVE_TESTS=1 para baixar de verdade")
class LiveInstagramTest(unittest.TestCase):
    def test_public_downloads(self):
        cases = (
            ("video", REEL, ".mp4"),
            ("video", REEL_WITH_AUDIO, ".mp4"),
            ("audio", REEL_WITH_AUDIO, ".mp3"),
            ("playlist_video", "https://www.instagram.com/p/BQ0eAlwhDrw/", ".mp4"),
        )
        for mode, url, ext in cases:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "out"
                out.mkdir()
                downloader.run_job(mode=mode, url=url, output_dir=out, log_path=Path(tmp) / "log")
                files = [p for p in out.iterdir() if p.suffix == ext]
                print(mode, [(p.name, p.stat().st_size) for p in files])
                self.assertTrue(files)
                self.assertTrue(all(p.stat().st_size > 10_000 for p in files))
                if url == REEL_WITH_AUDIO and ext == ".mp4":
                    probe = subprocess.run(
                        [shutil.which("ffmpeg"), "-hide_banner", "-i", str(files[0])],
                        capture_output=True,
                        text=True,
                    ).stderr
                    self.assertIn("Video:", probe)
                    self.assertIn("Audio:", probe)


if __name__ == "__main__":
    unittest.main()
