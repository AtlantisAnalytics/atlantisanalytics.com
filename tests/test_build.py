import sys
import tempfile
import tomllib
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import build  # noqa: E402

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
CFG = tomllib.loads((HERE / "site.toml").read_text(encoding="utf-8"))


def live(**over):
    base = dict(
        week="2026-11-23",
        picks=[build.Pick("1× RTX 3060 12 GB", "Granite 4.2 3B")],
        crate_version="0.1.2",
        crate_updated=NOW - timedelta(days=3),
        merges=[
            build.Merge(
                "bakeoff", "site: <b>bold</b> & co", "https://github.com/x/y/pull/1", NOW - timedelta(days=1)
            )
        ],
    )
    base.update(over)
    return build.Live(**base)


class RenderTests(unittest.TestCase):
    def test_has_legal_name_contact_and_live_parts(self):
        h = build.render(CFG, live(), NOW)
        self.assertIn("<title>Atlantis Analytics, LLC</title>", h)
        self.assertIn("© 2026 Atlantis Analytics, LLC", h)
        self.assertIn('mailto:dave@atlantisanalytics.com', h)
        self.assertIn('General picks for the week of <span class="d">2026-11-23</span>:', h)
        self.assertIn("Granite 4.2 3B", h)
        self.assertIn("Version 0.1.2 on crates.io, updated 3 days ago.", h)
        self.assertIn('Page rebuilt <span class="d">2026-11-24 12:00 UTC</span>', h)

    def test_escapes_outside_text(self):
        h = build.render(CFG, live(), NOW)
        self.assertNotIn("<b>bold</b>", h)
        self.assertIn("site: &lt;b&gt;bold&lt;/b&gt; &amp; co", h)

    def test_no_scripts_or_trackers(self):
        h = build.render(CFG, live(), NOW)
        self.assertNotIn("<script", h)
        self.assertNotIn("<iframe", h)

    def test_short_hardware(self):
        self.assertEqual(build.short_hardware("1× RTX 3060 12 GB"), "RTX 3060 12 GB")
        self.assertEqual(
            build.short_hardware("Apple M4 Max 36 GB unified (GPU limit raised to 32 GB)"),
            "Apple M4 Max 36 GB unified",
        )
        self.assertEqual(build.short_hardware("4× RTX 3060 12 GB"), "4× RTX 3060 12 GB")

    def test_ago(self):
        self.assertEqual(build.ago(NOW, NOW), "today")
        self.assertEqual(build.ago(NOW - timedelta(days=1), NOW), "yesterday")
        self.assertEqual(build.ago(NOW - timedelta(days=9), NOW), "9 days ago")


class BuildTests(unittest.TestCase):
    def test_build_writes_page_and_assets(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "_site"
            build.build(out, CFG, live(), NOW)
            self.assertTrue((out / "index.html").is_file())
            self.assertTrue((out / "style.css").is_file())
            self.assertTrue((out / "atlantis.webp").is_file())

    def test_failed_source_fails_without_touching_output(self):
        def boom(*a, **k):
            raise OSError("down")

        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "_site"
            out.mkdir()
            (out / "index.html").write_text("last good page")
            orig = build.fetch_json
            build.fetch_json = boom
            try:
                rc = build.main(["--out", str(out)])
            finally:
                build.fetch_json = orig
            self.assertEqual(rc, 1)
            self.assertEqual((out / "index.html").read_text(), "last good page")


if __name__ == "__main__":
    unittest.main()
