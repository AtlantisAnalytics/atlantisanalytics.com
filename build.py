"""Build atlantisanalytics.com into _site/ from site.toml plus live public data.

Sources: bakeoff.si's public API, crates.io, and GitHub's REST API (GITHUB_TOKEN is used when set,
as in the Pages workflow). If any source fails, the build fails, and the last good page stays live.

Usage: python3 build.py [--out _site]
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
import tomllib
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
UA = "atlantisanalytics.com site builder"
TIMEOUT_S = 30


def fetch_json(url: str, token: str | None = None) -> object:
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.load(r)


@dataclass(frozen=True)
class Pick:
    hardware: str  # e.g. "1× RTX 3060 12 GB"
    model: str


@dataclass(frozen=True)
class Merge:
    repo: str
    title: str
    url: str
    merged_at: datetime


@dataclass(frozen=True)
class Live:
    week: str
    picks: list[Pick]
    crate_version: str
    crate_updated: datetime
    merges: list[Merge]


def _when(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def short_hardware(envelope: str) -> str:
    """'1× RTX 3060 12 GB' -> 'RTX 3060 12 GB'; drops any parenthetical note."""
    label = re.sub(r"\s*\(.*?\)", "", envelope).strip()
    return re.sub(r"^1×\s*", "", label)


def bakeoff_picks(base: str) -> tuple[str, list[Pick]]:
    """This week's general pick for each tier, labelled by its hardware."""
    latest = fetch_json(f"{base}/api/v1/latest.json")
    picks = fetch_json(f"{base}/api/v1/picks.json")
    hardware = {
        t["id"]: short_hardware(t.get("envelope") or t.get("name") or t["id"])
        for t in latest["tiers"]
    }
    out = []
    for tier_id, tracks in picks.items():
        general = tracks.get("general")
        if general:
            out.append(Pick(hardware.get(tier_id, tier_id), general["label"]))
    return latest["week"], out


def crate(name: str) -> tuple[str, datetime]:
    c = fetch_json(f"https://crates.io/api/v1/crates/{name}")["crate"]
    return c["max_version"], _when(c["updated_at"])


def recent_merges(repos: list[str], count: int, token: str | None) -> list[Merge]:
    merges: list[Merge] = []
    for repo in repos:
        url = f"https://api.github.com/repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=30"
        for pr in fetch_json(url, token):
            if pr.get("merged_at"):
                merges.append(
                    Merge(repo.split("/")[-1], pr["title"], pr["html_url"], _when(pr["merged_at"]))
                )
    merges.sort(key=lambda m: m.merged_at, reverse=True)
    return merges[:count]


def gather(cfg: dict, token: str | None) -> Live:
    week, picks = bakeoff_picks(cfg["bakeoff"]["url"])
    version, updated = crate(cfg["watchmaker"]["crate"])
    merges = recent_merges(cfg["activity"]["repos"], cfg["activity"]["count"], token)
    return Live(week, picks, version, updated, merges)


def _e(s: str) -> str:
    return html.escape(s, quote=True)


def ago(then: datetime, now: datetime) -> str:
    days = (now - then).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"{days} days ago"


def render(cfg: dict, live: Live, now: datetime) -> str:
    co, bk, wm, at = cfg["company"], cfg["bakeoff"], cfg["watchmaker"], cfg["athena"]
    picks = "".join(
        f"<li><span class=\"hw\">{_e(p.hardware)}</span> {_e(p.model)}</li>" for p in live.picks
    )
    merges = "".join(
        f'<li><a href="{_e(m.url)}">{_e(m.title)}</a> <span class="meta">{_e(m.repo)} · '
        f'<span class="d">{m.merged_at:%Y-%m-%d}</span></span></li>'
        for m in live.merges
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(co["name"])}</title>
<meta name="description" content="{_e(co["tagline"])}">
<link rel="stylesheet" href="style.css">
<link rel="icon" href="atlantis.webp">
</head>
<body>
<main>
<header>
<img src="atlantis.webp" width="64" height="64" alt="">
<div>
<h1>{_e(co["name"])}</h1>
<p class="tagline">{_e(co["tagline"])}</p>
</div>
</header>

<section>
<h2>Projects</h2>

<article>
<h3><a href="{_e(bk["url"])}">bakeoff.si</a></h3>
<p>{_e(bk["summary"])}</p>
<p class="live">General picks for the week of <span class="d">{_e(live.week)}</span>:</p>
<ul class="picks">{picks}</ul>
<p>{_e(bk["topology"])} <a href="{_e(bk["url"])}/topology/">Multi-GPU results</a></p>
<p class="links"><a href="{_e(bk["url"])}">bakeoff.si</a> · <a href="https://github.com/{_e(bk["repo"])}">Source</a></p>
</article>

<article>
<h3>watchmaker <span class="meta">({_e(wm["crate"])})</span></h3>
<p>{_e(wm["summary"])}</p>
<p class="live">Version {_e(live.crate_version)} on crates.io, updated {ago(live.crate_updated, now)}.</p>
<p class="links"><a href="https://crates.io/crates/{_e(wm["crate"])}">crates.io</a> · <a href="https://github.com/{_e(wm["repo"])}">Source</a></p>
</article>

<article>
<h3>Athena</h3>
<p>{_e(at["summary"])}</p>
</article>
</section>

<section>
<h2>Recently merged</h2>
<ul class="activity">{merges}</ul>
</section>

<section>
<h2>Contact</h2>
<p><a href="mailto:{_e(co["email"])}">{_e(co["email"])}</a> · {_e(co["location"])} · <a href="https://x.com/{_e(co["x"])}" rel="me noopener">@{_e(co["x"])} on X</a></p>
</section>
</main>
<footer>
<p>© {now:%Y} {_e(co["name"])} · Page rebuilt <span class="d">{now:%Y-%m-%d %H:%M} UTC</span> from live data.</p>
</footer>
</body>
</html>
"""


def build(out: Path, cfg: dict, live: Live, now: datetime) -> None:
    tmp = out.with_name(out.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    (tmp / "index.html").write_text(render(cfg, live, now), encoding="utf-8")
    for asset in ("style.css", "atlantis.webp"):
        shutil.copy2(HERE / "assets" / asset, tmp / asset)
    if out.exists():
        shutil.rmtree(out)
    tmp.rename(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "_site"))
    args = ap.parse_args(argv)
    cfg = tomllib.loads((HERE / "site.toml").read_text(encoding="utf-8"))
    try:
        live = gather(cfg, os.environ.get("GITHUB_TOKEN") or None)
    except Exception as e:  # noqa: BLE001 - any failed source fails the build
        print(f"build failed, keeping the last published page: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if not live.picks or not live.merges:
        print("build failed: a live section came back empty", file=sys.stderr)
        return 1
    build(Path(args.out), cfg, live, datetime.now(UTC))
    print(f"built {args.out}: week {live.week}, {len(live.picks)} picks, {len(live.merges)} merges")
    return 0


if __name__ == "__main__":
    sys.exit(main())
