#!/usr/bin/env python3
"""Copy the static site and inline a single-file snapshot."""

from __future__ import annotations

import json
import shutil
import urllib.parse
from pathlib import Path

DATA_FILES = ("news.json", "fixtures.json", "podcasts.json", "status.json")


def embed_script(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    raw = (
        raw.replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    return f"<script>window.__AIC_DATA__={raw};</script>"


def build(root: Path, dist: Path | None = None) -> Path:
    root = root.resolve()
    dist = (root / "dist") if dist is None else dist
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)
    for name in ("index.html", "favicon.svg"):
        shutil.copy2(root / name, dist / name)
    for folder in ("css", "js"):
        shutil.copytree(root / folder, dist / folder)
    data_dest = dist / "data"
    data_dest.mkdir()
    payload = {}
    for name in DATA_FILES:
        source = root / "data" / name
        if not source.is_file():
            raise SystemExit(f"缺少 {source}")
        shutil.copy2(source, data_dest / name)
        payload[name.removesuffix(".json")] = json.loads(source.read_text(encoding="utf-8"))
    version = (payload.get("status") or {}).get("generatedAt") or "local"
    version = version.replace(":", "").replace("+", "")
    index = (dist / "index.html").read_text(encoding="utf-8")
    index = index.replace('window.__AIC_VERSION__=""', f'window.__AIC_VERSION__="{version}"', 1)
    (dist / "index.html").write_text(index, encoding="utf-8")
    css = (dist / "css" / "site.css").read_text(encoding="utf-8")
    js = (dist / "js" / "app.js").read_text(encoding="utf-8")
    svg = (dist / "favicon.svg").read_text(encoding="utf-8")
    snapshot = index.replace("<!--snapshot-->", embed_script(payload), 1)
    snapshot = snapshot.replace(
        '<link rel="stylesheet" href="css/site.css">',
        "<style>\n" + css + "\n</style>",
        1,
    )
    snapshot = snapshot.replace(
        'href="favicon.svg"',
        'href="data:image/svg+xml,' + urllib.parse.quote(svg) + '"',
        1,
    )
    snapshot = snapshot.replace(
        '<script src="js/app.js" defer></script>',
        "<script>\n" + js + "\n</script>",
        1,
    )
    (dist / "snapshot.html").write_text(snapshot, encoding="utf-8")
    return dist


def main() -> int:
    build(Path(__file__).resolve().parents[1])
    print("built dist/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
