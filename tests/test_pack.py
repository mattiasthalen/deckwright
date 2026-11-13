"""Tests for pack.py, which packs a deck folder into one page; no network, no browser.

python3 tests/test_pack.py
"""

from __future__ import annotations

import base64
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
PAGE = pathlib.Path(os.environ.get("DECK_PAGE") or REPO / "plugins/deckwright/skills/deckwright/page/index.html")
PACK = PAGE.parent / "pack.py"

DATA_URL = "data:image/jpeg;base64,"


def scryfall_id(n):
    return f"00000000-0000-4000-8000-{n:012d}"


def fake_jpeg(n):
    return b"\xff\xd8\xff\xe0" + bytes([n % 256]) * 16 + b"\xff\xd9"


def card(n, name, category="Spells"):
    return {
        "scryfall_id": scryfall_id(n),
        "name": name,
        "count": 1,
        "category": category,
        "tags": [],
        "checked": True,
        "bends": None,
        "copy": {
            "mana_cost": "{1}{B}",
            "mana_value": 2,
            "type_line": "Creature — Rat",
            "text": "",
            "rarity": "common",
            "taken": "2026-11-12",
        },
    }


def a_deck(**over):
    deck = {
        "version": 2,
        "name": "Vesk & the <Swarm>",
        "format": "brawl",
        "hero": scryfall_id(1),
        "criteria": [{"kind": "format", "text": "Brawl on Arena"}, {"kind": "theme", "text": "Rats"}],
        "categories": [{"name": "Commander", "target": 1}, {"name": "Spells", "target": 8}],
        "cards": [card(1, "Vesk, the Burrow Mind", "Commander"), card(2, "Gutter Scout")],
        "maybeboard": [
            {"scryfall_id": scryfall_id(3), "name": "Shade of Doubt", "kind": "later", "why": "Saved for later."}
        ],
        "tokens": [{"name": "Rat", "scryfall_id": scryfall_id(4)}],
        "offer": {
            "category": "Removal",
            "groups": [
                {
                    "cards": [
                        {
                            "scryfall_id": scryfall_id(5),
                            "name": "Grim Bargain",
                            "reason": "Kills a blocker.",
                            "copy": {"mana_cost": "{B}", "type_line": "Instant", "text": ""},
                        }
                    ]
                }
            ],
        },
        "approved": False,
    }
    deck.update(over)
    return deck


# Every picture a_deck names, by its path in the folder.
NAMED_PICTURES = {f"cards/{scryfall_id(n)}.jpg": fake_jpeg(n) for n in range(1, 6)} | {
    "cards/back.jpg": fake_jpeg(90),
    f"art/{scryfall_id(1)}.jpg": fake_jpeg(91),
}
STRAY_PICTURE = f"cards/{scryfall_id(77)}.jpg"


def write_folder(
    folder, deck_text, ledger="# Ledger\n\n- 2026-11-12 · in · Gutter Scout · a cheap Rat\n", pictures=None
):
    folder.mkdir(parents=True)
    if deck_text is not None:
        (folder / "deck.json").write_text(deck_text, encoding="utf-8")
    if ledger is not None:
        (folder / "LEDGER.md").write_text(ledger, encoding="utf-8")
    for rel, data in (NAMED_PICTURES if pictures is None else pictures).items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_bytes(data)


def deck_files(packed):
    """The DECK_FILES map read back from the packed page as the HTML parser sees the script that sets
    it: its text runs to the first "</script", and it must hold no "<!--" that could hide that end."""
    setter = re.search(r"window\.DECK_FILES\s*=\s*", packed)
    assert setter, "the packed page does not set window.DECK_FILES"
    opening = packed.rfind("<script", 0, setter.start())
    assert opening >= 0, "window.DECK_FILES is not set in a script element"
    body_from = packed.index(">", opening) + 1
    end = re.compile(r"</script", re.IGNORECASE).search(packed, body_from)
    assert end, "the script that sets window.DECK_FILES never ends"
    body = packed[body_from : end.start()]
    assert "<!--" not in body, "the script that sets window.DECK_FILES holds <!--, which can hide its end"
    assert re.search(r"<script", body, re.IGNORECASE) is None, "the script that sets window.DECK_FILES holds <script"
    try:
        value, at = json.JSONDecoder().raw_decode(body, setter.end() - body_from)
    except json.JSONDecodeError as e:
        raise AssertionError(f"the script that sets window.DECK_FILES ends early, inside its map: {e}") from None
    rest = body[at:].strip()
    assert rest in ("", ";"), f"the script that sets window.DECK_FILES ends early, before {rest[:60]!r}"
    return value, opening, packed[opening : end.end() + 1]


class PackTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PACK.is_file(), f"there is no pack.py beside the page at {PACK}")
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="deck-pack-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def pack(self, folder):
        return subprocess.run(
            [sys.executable, str(PACK), str(folder)], cwd=self.root, capture_output=True, text=True, timeout=60
        )

    def packed(self, deck, **folder_files):
        folder = self.root / "brawl-rats"
        write_folder(folder, json.dumps(deck, ensure_ascii=False, indent=2), **folder_files)
        done = self.pack(folder)
        self.assertEqual(done.returncode, 0, f"pack.py failed: {done.stderr}")
        return folder, done

    def title_of(self, page):
        titles = re.findall(r"<title>(.*?)</title>", page, re.DOTALL)
        self.assertEqual(len(titles), 1, f"the page has {len(titles)} title elements")
        return titles[0]

    def test_p8_writes_the_page_into_the_folder_titled_by_the_deck_name(self):
        folder, _ = self.packed(a_deck())
        page = folder / "index.html"
        self.assertTrue(page.is_file(), "pack.py writes no index.html into the deck folder")
        written = page.read_text(encoding="utf-8")
        self.assertEqual(self.title_of(written), "Vesk &amp; the &lt;Swarm&gt;")
        untitled = lambda text: re.sub(r"<title>.*?</title>", "<title></title>", text, count=1, flags=re.DOTALL)
        self.assertEqual(
            untitled(written),
            untitled(PAGE.read_text(encoding="utf-8")),
            "the folder's index.html is not the deck page with only its title changed",
        )

    def test_p8_titles_a_nameless_deck_by_its_format_and_first_theme_or_its_format_alone(self):
        cases = [
            (
                a_deck(
                    name=None,
                    criteria=[
                        {"kind": "format", "text": "Brawl on Arena"},
                        {"kind": "theme", "text": "Rats"},
                        {"kind": "theme", "text": "Snails"},
                    ],
                ),
                "Brawl · Rats",
            ),
            (
                a_deck(name="", format="standard", criteria=[{"kind": "theme", "text": "Big & green"}]),
                "Standard · Big &amp; green",
            ),
            (a_deck(name=None, criteria=[{"kind": "format", "text": "Brawl on Arena"}]), "Brawl"),
        ]
        for deck, title in cases:
            with self.subTest(title=title):
                deck = {k: v for k, v in deck.items() if v is not None}
                folder = self.root / f"case-{len(list(self.root.iterdir()))}"
                write_folder(folder, json.dumps(deck))
                done = self.pack(folder)
                self.assertEqual(done.returncode, 0, f"pack.py failed: {done.stderr}")
                self.assertEqual(self.title_of((folder / "index.html").read_text(encoding="utf-8")), title)

    def test_p8_writes_the_packed_file_beside_the_folder_and_prints_its_path(self):
        _folder, done = self.packed(a_deck())
        packed = self.root / "brawl-rats.html"
        self.assertTrue(packed.is_file(), "pack.py writes no brawl-rats.html beside the folder brawl-rats")
        printed = done.stdout.strip()
        self.assertEqual(len(printed.splitlines()), 1, f"pack.py prints {done.stdout!r}, not one path")
        self.assertEqual(
            (self.root / printed).resolve(), packed.resolve(), "pack.py does not print the packed file's path"
        )

    def test_p8_sets_deck_files_before_the_pages_own_script_with_the_files_deck_json_names(self):
        folder, _ = self.packed(a_deck())
        (folder / STRAY_PICTURE).write_bytes(fake_jpeg(77))
        self.assertEqual(self.pack(folder).returncode, 0)
        packed = (self.root / "brawl-rats.html").read_text(encoding="utf-8")
        files, at, element = deck_files(packed)
        self.assertGreaterEqual(
            packed.replace(element, "", 1).find("<script"),
            at,
            "the script setting window.DECK_FILES is not before the page's own script",
        )
        self.assertEqual(
            set(files),
            {"deck.json", "LEDGER.md", *NAMED_PICTURES},
            "DECK_FILES does not hold exactly deck.json, LEDGER.md and the pictures deck.json names",
        )
        self.assertNotIn(STRAY_PICTURE, files, "a picture deck.json does not name is packed")
        self.assertEqual(files["deck.json"], (folder / "deck.json").read_text(encoding="utf-8"))
        self.assertEqual(files["LEDGER.md"], (folder / "LEDGER.md").read_text(encoding="utf-8"))
        for rel, data in NAMED_PICTURES.items():
            self.assertTrue(files[rel].startswith(DATA_URL), f"{rel} is not packed as a JPEG data URL")
            self.assertEqual(
                base64.b64decode(files[rel][len(DATA_URL) :]), data, f"{rel} does not decode to the saved picture"
            )
        squeezed = lambda text: re.sub(r"\s+", "", text)
        self.assertEqual(
            squeezed(packed.replace(element, "", 1)),
            squeezed((folder / "index.html").read_text(encoding="utf-8")),
            "the packed file is not the folder's page with one script added",
        )

    def test_p8_packs_an_empty_ledger_when_there_is_none_and_leaves_out_a_picture_not_saved(self):
        missing = f"cards/{scryfall_id(2)}.jpg"
        _folder, _ = self.packed(
            a_deck(), ledger=None, pictures={k: v for k, v in NAMED_PICTURES.items() if k != missing}
        )
        files, _, _ = deck_files((self.root / "brawl-rats.html").read_text(encoding="utf-8"))
        self.assertEqual(files.get("LEDGER.md"), "", "a folder with no LEDGER.md is not packed with an empty one")
        self.assertNotIn(missing, files, "a picture that was never saved is in DECK_FILES")

    def test_p10_text_that_could_end_the_script_is_packed_whole(self):
        for ending in ["</script>", "</SCRIPT >", "</script", "<!--<script>"]:
            with self.subTest(ending=ending):
                for old in self.root.iterdir():
                    shutil.rmtree(old) if old.is_dir() else old.unlink()
                deck = a_deck(name=f"Rats {ending} and more", pitch=f"Then {ending} alert(1) <!-- and on")
                ledger = f"# Ledger\n\n- 2026-11-12 · in · Gutter Scout · {ending} in the ledger\n"
                folder, _ = self.packed(deck, ledger=ledger)
                files, _, _ = deck_files((self.root / "brawl-rats.html").read_text(encoding="utf-8"))
                self.assertEqual(files["deck.json"], (folder / "deck.json").read_text(encoding="utf-8"))
                self.assertEqual(files["LEDGER.md"], ledger)
                self.assertEqual(
                    self.title_of((folder / "index.html").read_text(encoding="utf-8")),
                    html.escape(deck["name"], quote=False),
                )

    def test_p10_a_folder_without_a_readable_deck_json_fails_in_one_line(self):
        cases = {"no deck.json": None, "deck.json not JSON": '{ "version": 2, "name": ', "no folder": "no folder"}
        for case, text in cases.items():
            with self.subTest(case=case):
                folder = self.root / case.replace(" ", "-")
                if text != "no folder":
                    write_folder(folder, text)
                done = self.pack(folder)
                self.assertNotEqual(done.returncode, 0, f"{case}: pack.py exits 0")
                said = done.stderr.strip()
                self.assertTrue(said, f"{case}: pack.py says nothing on stderr")
                self.assertEqual(len(said.splitlines()), 1, f"{case}: pack.py says more than one line: {done.stderr!r}")
                self.assertNotIn("Traceback", said, f"{case}: pack.py ends in a traceback")

    def test_r3_packs_a_deck_json_that_starts_with_a_byte_order_mark_and_packs_it_without(self):
        # The page served over HTTP reads such a file, since fetch().text() drops the mark.
        folder = self.root / "brawl-rats"
        write_folder(folder, None)
        text = json.dumps(a_deck(), ensure_ascii=False)
        (folder / "deck.json").write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
        done = self.pack(folder)
        self.assertEqual(
            done.returncode, 0, f"pack.py fails on a deck.json that starts with a byte-order mark: {done.stderr}"
        )
        files, _, _ = deck_files((self.root / "brawl-rats.html").read_text(encoding="utf-8"))
        self.assertFalse(files["deck.json"].startswith("\ufeff"), "the packed deck.json keeps the byte-order mark")
        self.assertEqual(
            json.loads(files["deck.json"]), json.loads(text), "the packed deck.json is not the folder's deck"
        )

    def test_r4_fails_in_one_line_and_leaves_the_folder_as_it_was(self):
        # A deck pack.py cannot write, or a LEDGER.md it cannot read, ends in a packed page or one line on stderr,
        # never a traceback, and never leaves the folder's page empty or cut short.
        before = "<!doctype html>\n<html><head><title>Packed before</title></head><body></body></html>\n"
        cases = {
            # The JSON escape of a lone surrogate, which no UTF-8 file can hold once decoded.
            "a lone surrogate in the name": ('{"version": 2, "name": "Rats \\ud800", "format": "brawl"}', "ledger"),
            "LEDGER.md a directory": (json.dumps(a_deck()), "directory"),
        }
        for case, (deck_text, ledger) in cases.items():
            with self.subTest(case=case):
                folder = self.root / case.replace(" ", "-")
                write_folder(folder, deck_text, ledger=None)
                if ledger == "directory":
                    (folder / "LEDGER.md").mkdir()
                else:
                    (folder / "LEDGER.md").write_text("# Ledger\n", encoding="utf-8")
                (folder / "index.html").write_text(before, encoding="utf-8")
                done = self.pack(folder)
                self.assertNotIn("Traceback", done.stderr, f"{case}: pack.py ends in a traceback")
                if done.returncode == 0:
                    page = (folder / "index.html").read_bytes().decode("utf-8")
                    self.assertIn("</html>", page, f"{case}: pack.py succeeds and leaves index.html cut short")
                    if ledger == "directory":
                        files, _, _ = deck_files((self.root / f"{folder.name}.html").read_text(encoding="utf-8"))
                        self.assertEqual(
                            files.get("LEDGER.md"), "", f"{case}: the unreadable ledger is not packed as empty"
                        )
                else:
                    self.assertEqual(done.returncode, 1, f"{case}: pack.py exits {done.returncode}")
                    self.assertEqual(
                        len(done.stderr.strip().splitlines()),
                        1,
                        f"{case}: pack.py says more than one line: {done.stderr!r}",
                    )
                    page = (folder / "index.html").read_text(encoding="utf-8", errors="replace")
                    self.assertTrue(
                        page == before or "</html>" in page,
                        f"{case}: pack.py fails and leaves index.html {page[:80]!r}",
                    )

    def test_r5_titles_a_deck_as_the_page_does(self):
        # The page titles a deck by its name trimmed, or by its format read as String(deck.format).toLowerCase(), with
        # no trimming, and its first theme; a format other than "brawl" is Standard. The titles are HTML-escaped.
        rats = [{"kind": "format", "text": "Brawl on Arena"}, {"kind": "theme", "text": "Rats"}]
        cases = [
            (
                "name present",
                {"name": "Vesk & the <Swarm>", "format": "brawl", "criteria": rats},
                "Vesk &amp; the &lt;Swarm&gt;",
            ),
            ("nameless with theme", {"format": "brawl", "criteria": rats}, "Brawl · Rats"),
            (
                "nameless empty name",
                {"name": "", "format": "standard", "criteria": [{"kind": "theme", "text": "Big green creatures"}]},
                "Standard · Big green creatures",
            ),
            (
                "nameless without theme",
                {"format": "brawl", "criteria": [{"kind": "format", "text": "Brawl on Arena"}]},
                "Brawl",
            ),
            ("format with a leading space", {"format": " brawl", "criteria": rats}, "Standard · Rats"),
            ("format in capitals", {"format": "BRAWL", "criteria": rats}, "Brawl · Rats"),
            ("format missing", {"criteria": rats}, "Standard · Rats"),
        ]
        for case, over, title in cases:
            with self.subTest(case=case):
                deck = {k: v for k, v in a_deck(**over).items() if k not in {"name", "format"} or k in over}
                folder = self.root / case.replace(" ", "-")
                write_folder(folder, json.dumps(deck, ensure_ascii=False))
                done = self.pack(folder)
                self.assertEqual(done.returncode, 0, f"pack.py failed: {done.stderr}")
                self.assertEqual(self.title_of((folder / "index.html").read_text(encoding="utf-8")), title)

    def test_r8_a_failed_write_keeps_the_last_good_pages(self):
        # A write cut short by a full disk or a size limit leaves both pages as the last run wrote them, or the
        # folder's page complete, and no half-written file beside either; pack.py says so in one line.
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("R8 needs bash to run pack.py under a file-size limit, and there is no bash")
        limited = lambda *argv: subprocess.run(
            [bash, "-c", 'ulimit -f 200; exec "$@"', "_", *argv],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        probe = self.root / "probe.bin"
        tried = limited(sys.executable, "-c", f"open({str(probe)!r}, 'wb').write(b'0' * 400_000)")
        probe.unlink(missing_ok=True)
        if tried.returncode == 0:
            self.skipTest(
                "R8 needs `ulimit -f` to limit the size of a file written, and here it does not: "
                f"a 400 KB write under `ulimit -f 200` succeeded ({tried.stderr.strip()!r})"
            )

        folder, _ = self.packed(a_deck())
        packed = self.root / "brawl-rats.html"
        page_before, packed_before = (folder / "index.html").read_bytes(), packed.read_bytes()
        self.assertLess(
            len(packed_before),
            150_000,
            "the last good packed file is near the 200 KB limit, so this test proves less than it says",
        )
        (folder / f"cards/{scryfall_id(2)}.jpg").write_bytes(
            b"\xff\xd8\xff\xe0" + bytes(range(256)) * 1600 + b"\xff\xd9"
        )
        listed = lambda: (
            sorted(p.name for p in self.root.iterdir()),
            sorted(str(p.relative_to(folder)) for p in folder.rglob("*")),
        )
        files_before = listed()

        done = limited(sys.executable, str(PACK), str(folder))
        self.assertEqual(
            done.returncode, 1, f"pack.py exits {done.returncode} when its write fails partway: {done.stderr!r}"
        )
        said = done.stderr.strip()
        self.assertTrue(said, "pack.py says nothing on stderr when its write fails partway")
        self.assertNotIn("Traceback", said, "pack.py ends in a traceback when its write fails partway")
        self.assertEqual(
            len(said.splitlines()), 1, f"pack.py says more than one line when its write fails partway: {done.stderr!r}"
        )
        packed_after = packed.read_bytes() if packed.is_file() else b""
        self.assertTrue(
            packed_after == packed_before,
            f"a failed write leaves the packed file {len(packed_after)} bytes long, not the last good one of {len(packed_before)} bytes",
        )
        page_after = (folder / "index.html").read_bytes()
        self.assertTrue(
            page_after == page_before or page_after.rstrip().endswith(b"</html>"),
            f"a failed write leaves the folder's index.html cut short, ending {page_after[-60:]!r}",
        )
        self.assertEqual(
            listed(), files_before, "a failed write leaves a file beside the packed file or in the deck folder"
        )

    def test_r9_a_deck_json_python_cannot_parse_fails_in_one_line(self):
        # Valid JSON both, but Python's int() refuses a number of more than 4300 digits and its parser recurses per "[".
        cases = {
            "an integer of 5000 digits": '{"version": 2, "name": "Rats", "format": "brawl", "count": '
            + "7" * 5000
            + "}",
            "200,000 nested lists": '{"version": 2, "name": "Rats", "format": "brawl", "deep": '
            + "[" * 200_000
            + "]" * 200_000
            + "}",
        }
        for case, text in cases.items():
            with self.subTest(case=case):
                folder = self.root / case.replace(" ", "-").replace(",", "")
                write_folder(folder, text)
                done = self.pack(folder)
                self.assertEqual(done.returncode, 1, f"{case}: pack.py exits {done.returncode}")
                said = done.stderr.strip()
                self.assertTrue(said, f"{case}: pack.py says nothing on stderr")
                self.assertFalse("Traceback" in said, f"{case}: pack.py ends in a traceback: {said.splitlines()[-1]!r}")
                self.assertEqual(len(said.splitlines()), 1, f"{case}: pack.py says more than one line: {said[-200:]!r}")


if __name__ == "__main__":
    unittest.main()
