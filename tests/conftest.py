"""Harness for the deck.py tests: a stand-in Scryfall, a runner for the script, and a reader for the page.

The tests treat deck.py as a black box behind its command line. tests/README.md is the
contract they hold it to; every name used here that the plan leaves open is fixed there.
"""

from __future__ import annotations

import copy
import html
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parent.parent
# DECKWRIGHT_SKILL_DIR points the suite at another copy of the skill, such as a candidate build
# kept outside the repo; by default it is the skill in this repo.
SKILL_DIR = Path(os.environ.get("DECKWRIGHT_SKILL_DIR") or ROOT / "plugins" / "deckwright" / "skills" / "interview")
SCRIPT = SKILL_DIR / "deck.py"
RECORDED = Path(__file__).resolve().parent / "fixtures" / "scryfall"

COMMANDER = "Meren of Clan Nel Toth"
CATEGORIES = [
    ("Lands", 38),
    ("Ramp", 10),
    ("Card advantage", 12),
    ("Targeted disruption", 12),
    ("Mass disruption", 6),
    ("Plan", 30),
]
CARD_FIELDS = {
    "name",
    "mana_cost",
    "type_line",
    "oracle_text",
    "color_identity",
    "commander_legality",
    "game_changer",
}

EXIT_UNREACHABLE = 3
EXIT_NOT_RECORDED = 4

# Real Scryfall answers carry these; the recordings had them stripped, so the stand-in puts
# them back to prove the script drops them.
PRICE_KEYS = {
    "prices": {"usd": "987.65", "usd_foil": "1234.56", "eur": "876.54", "tix": "12.34"},
    "purchase_uris": {"tcgplayer": "https://shop.example/purchase/1"},
    "image_uris": {"normal": "https://img.example/card.jpg"},
}


def load_recorded() -> dict[tuple[str, str], tuple[int, dict]]:
    """Every recorded `cards/named` request, keyed by (mode, query casefolded)."""
    recorded = {}
    for path in sorted(RECORDED.glob("named-*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        recorded[(rec["mode"], rec["q"].casefold())] = (rec["status"], rec["body"])
    return recorded


def scryfall_card(name: str) -> dict:
    """The recorded Scryfall card object for an exact-name request."""
    status, body = load_recorded()[("exact", name.casefold())]
    assert status == 200, f"no recorded card for {name!r}"
    return body


def with_prices(card: dict) -> dict:
    priced = copy.deepcopy(card)
    priced.update(copy.deepcopy(PRICE_KEYS))
    for face in priced.get("card_faces", []):
        face["image_uris"] = copy.deepcopy(PRICE_KEYS["image_uris"])
    return priced


@dataclass
class Request:
    at: float
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]


@dataclass
class FakeScryfall:
    """A local stand-in for api.scryfall.com that serves only the recorded responses.

    `refuse = True` makes it answer like a proxy that blocks the host: 403 and an HTML body.
    An unrecorded request gets a 500, which a correct script reports as unreachable (exit 3),
    so a test that trips one fails loudly rather than seeing a made-up answer.
    """

    url: str = ""
    requests: list[Request] = field(default_factory=list)
    refuse: bool = False
    unrecorded: list[str] = field(default_factory=list)


def _serve(fake: FakeScryfall, recorded):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parts = urlsplit(self.path)
            query = parse_qs(parts.query)
            fake.requests.append(
                Request(time.monotonic(), parts.path, query, {k.lower(): v for k, v in self.headers.items()})
            )
            if fake.refuse:
                return self._send(403, b"<html><body>Blocked by proxy</body></html>", "text/html")
            mode = "exact" if "exact" in query else "fuzzy" if "fuzzy" in query else None
            if parts.path != "/cards/named" or mode is None:
                fake.unrecorded.append(self.path)
                return self._send(500, b'{"object":"error","status":500}', "application/json")
            key = (mode, query[mode][0].casefold())
            if key not in recorded:
                fake.unrecorded.append(self.path)
                return self._send(500, b'{"object":"error","status":500}', "application/json")
            status, body = recorded[key]
            if status == 200:
                body = with_prices(body)
            self._send(status, json.dumps(body).encode(), "application/json")

        def _send(self, status, payload, ctype):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return Handler


@pytest.fixture
def scryfall():
    fake = FakeScryfall()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _serve(fake, load_recorded()))
    fake.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield fake
    server.shutdown()
    server.server_close()


@pytest.fixture
def unreachable_url() -> str:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"


class Deckwright:
    """Runs deck.py as the skill does, in one working folder, against one Scryfall URL."""

    def __init__(self, cwd: Path, api: str, script: Path = SCRIPT):
        self.cwd = cwd
        self.api = api
        self.script = script

    def env(self, api: str | None = None, extra: dict | None = None) -> dict:
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.lower().endswith("_proxy") and not k.startswith("DECKWRIGHT_")
        }
        env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
        env["DECKWRIGHT_SCRYFALL_API"] = api or self.api
        env.update(extra or {})
        return env

    def run(self, *args: str, api: str | None = None, env: dict | None = None, expect: int | None = 0):
        assert self.script.exists(), f"the script is not built yet: {self.script}"
        proc = subprocess.run(
            [sys.executable, str(self.script), *args],
            cwd=self.cwd,
            env=self.env(api, env),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if expect is not None:
            assert proc.returncode == expect, (
                f"deck.py {' '.join(args)} exited {proc.returncode}, expected {expect}\n"
                f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
            )
        return proc

    def json(self, *args: str, **kw):
        return json.loads(self.run(*args, **kw).stdout)

    def new(self, commander: str = COMMANDER, template: str = "commander"):
        return self.run("new", "--template", template, "--commander", commander)

    def add(self, name: str, *categories: str, count: int | None = None, **kw):
        args = ["add", name]
        if count is not None:
            args += ["--count", str(count)]
        if categories:
            args += ["--category", *categories]
        return self.run(*args, **kw)

    def tally(self, **kw) -> dict:
        return self.json("tally", **kw)

    def page(self, out: str = "deck.html", **kw) -> str:
        self.run("page", "--out", out, **kw)
        return (self.cwd / out).read_text(encoding="utf-8")

    @property
    def deck_file(self) -> Path:
        return self.cwd / "deck.json"


@pytest.fixture
def deck(tmp_path, scryfall) -> Deckwright:
    work = tmp_path / "work"
    work.mkdir()
    return Deckwright(work, scryfall.url)


def category(tally: dict, name: str) -> dict:
    matches = [c for c in tally["categories"] if c["name"] == name]
    assert len(matches) == 1, f"tally has no single category {name!r}: {tally['categories']}"
    return matches[0]


# The page ------------------------------------------------------------------------------

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _PageReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, str | None]] = []
        self.texts: dict[str, list[str]] = {}
        self.open: list[list[str]] = []
        self.scripts: list[dict] = []
        self.buttons = 0
        self.decklist_raw_children = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self.scripts.append(attrs)
        if tag == "button":
            self.buttons += 1
        if any(key == "section:decklist" for key, _ in self.stack):
            self.decklist_raw_children += 1
        if tag in _VOID:
            return
        key = None
        if attrs.get("data-section"):
            key = "section:" + attrs["data-section"]
        elif attrs.get("data-category"):
            key = "category:" + attrs["data-category"]
        if key:
            buf: list[str] = []
            self.texts.setdefault(key, []).append(buf)  # type: ignore[arg-type]
            self.open.append(buf)
        self.stack.append((key or "", tag))

    def handle_endtag(self, tag):
        if tag in _VOID:
            return
        while self.stack:
            key, open_tag = self.stack.pop()
            if key:
                self.open.pop()
            if open_tag == tag:
                break

    def handle_data(self, data):
        for buf in self.open:
            buf.append(data)


@dataclass
class Page:
    raw: str
    texts: dict[str, list[str]]
    scripts: list[dict]
    buttons: int
    decklist_children: int

    def one(self, key: str) -> str:
        found = self.texts.get(key, [])
        assert len(found) == 1, f"the page should have exactly one element marked {key!r}, found {len(found)}"
        return found[0]

    def section(self, name: str) -> str:
        return self.one("section:" + name)

    def category(self, name: str) -> str:
        return self.one("category:" + name)


def read_page(raw: str) -> Page:
    reader = _PageReader()
    reader.feed(raw)
    reader.close()
    texts = {k: ["".join(buf) for buf in bufs] for k, bufs in reader.texts.items()}
    return Page(raw, texts, reader.scripts, reader.buttons, reader.decklist_raw_children)


def count_of(text: str, count: int, target: int) -> bool:
    """Whether the text shows `count / target`, as the page and the tally's prose render it."""
    return re.search(rf"(?<!\d){count}\s*/\s*{target}(?!\d)", text) is not None


def escaped(text: str) -> str:
    return html.escape(text, quote=False)
