"""Named decks, each its own file and page; an S1 deck file still opens: C29, C30, C32, E14, E15."""

from __future__ import annotations

import html
import json
import re
import shutil

from conftest import COMMANDER, EXIT_USAGE, FIXTURES, copy_tree_files, file_key, read_page, unfinished_mark

S1 = FIXTURES / "s1"


def title(raw: str) -> str:
    found = re.findall(r"<title>(.*?)</title>", raw, re.S | re.I)
    assert len(found) == 1, f"the page has one <title>: {found}"
    return html.unescape(found[0])


def files(folder) -> set[str]:
    return {str(p.relative_to(folder)) for p in copy_tree_files(folder) if "deckwright-cache" not in p.parts}


# C29, E14 ----------------------------------------------------------------------------


def test_deck_name_never_overwrites(deck):
    rats = deck.named("Rat Pack")
    rats.add("Sol Ring", "Ramp")
    before = rats.deck_file.read_bytes()
    on_disk = files(deck.cwd)

    # The same name, then names that become the same file name (E14).
    for name in ("Rat Pack", "rat pack", "Rat-Pack!", "  RAT   PACK  "):
        assert file_key(name) == "rat-pack"
        proc = deck.new("Bloodline Keeper", name=name, expect=EXIT_USAGE)
        said = proc.stdout + proc.stderr
        assert said.strip(), f"the refusal of {name!r} says why"
        assert re.search(r"taken|exists|already", said, re.I), f"{name!r} is refused as taken: {said!r}"
        assert "Traceback" not in proc.stderr
        assert rats.deck_file.read_bytes() == before, f"starting {name!r} left the deck as it was"
        assert files(deck.cwd) == on_disk, "and wrote no other file"


# C30, E15 ----------------------------------------------------------------------------


def test_deck_named_files(deck):
    rats = deck.named("Rat Pack")
    night = deck.named("Night Shift", commander="Meren of Clan Nel Toth")
    assert rats.deck_path == "decks/rat-pack.json" and night.deck_path == "decks/night-shift.json"
    assert not (deck.cwd / "deck.json").exists(), "a named deck is not ./deck.json"

    night_before = night.deck_file.read_bytes()
    rats.add("Sol Ring", "Ramp")
    assert night.deck_file.read_bytes() == night_before, "each deck is its own file"
    assert rats.tally()["name"] == "Rat Pack"
    assert night.tally()["total"] == 1

    # The page is named after the deck, beside its file, and the name titles it.
    rats.run("page")
    page_file = deck.cwd / "decks" / "rat-pack.html"
    assert page_file.is_file(), "page with no --out writes decks/<file name>.html"
    raw = page_file.read_text(encoding="utf-8")
    assert "Rat Pack" in title(raw)
    assert read_page(raw).section("name").strip() == "Rat Pack"
    assert COMMANDER in read_page(raw).section("commander")

    # The decks there are, by name, file and commander.
    listed = deck.json("decks")
    assert listed == [
        {"name": "Night Shift", "file": "decks/night-shift.json", "commander": COMMANDER},
        {"name": "Rat Pack", "file": "decks/rat-pack.json", "commander": COMMANDER},
    ]


def test_deck_named_files_odd_characters(deck):
    # E15: characters a file name cannot hold, and characters outside ASCII.
    for name in ('Rats: "The/Pack" <3?*|\\', "Råttornas kväll", "稲妻デッキ"):
        built = deck.named(name)
        key = file_key(name)
        assert built.deck_path == f"decks/{key}.json"
        assert re.fullmatch(r"[a-z0-9-]+", key), key
        built.run("page")
        raw = (deck.cwd / "decks" / f"{key}.html").read_text(encoding="utf-8")
        assert name in title(raw), f"the page shows the name as given: {title(raw)!r}"
        assert read_page(raw).section("name").strip() == name
    assert file_key('Rats: "The/Pack" <3?*|\\') == "rats-the-pack-3"
    assert len({e["file"] for e in deck.json("decks")}) == 3


# D4 ----------------------------------------------------------------------------------


def test_deck_new_prints_file(deck):
    """`new --name` prints the deck's `file`, the path every later command takes as `--deck`, so
    the skill never derives it from the name: a name outside ASCII is keyed with a hash."""
    for name in ("Rat Pack", "Råttornas kväll", "稲妻デッキ"):
        out = json.loads(deck.new(name=name).stdout)
        assert out["file"] == f"decks/{file_key(name)}.json", out.get("file")
        assert (deck.cwd / out["file"]).is_file()
        assert deck.using(out["file"]).tally()["name"] == name
    assert sorted(e["file"] for e in deck.json("decks")) == sorted(
        f"decks/{file_key(n)}.json" for n in ("Rat Pack", "Råttornas kväll", "稲妻デッキ")
    )


def test_deck_new_missing_parents(deck):
    """R2-A4: `new --deck a/b/c.json` makes the folders it needs and writes the deck, with no traceback."""
    proc = deck.run("new", "--template", "commander", "--commander", COMMANDER, "--deck", "a/b/c.json")
    assert "Traceback" not in proc.stderr, proc.stderr
    assert (deck.cwd / "a" / "b" / "c.json").is_file()
    assert deck.using("a/b/c.json").tally()["total"] == 1


# A11 ---------------------------------------------------------------------------------


def test_deck_name_very_long(deck):
    """A name far past a file name's limit (255 bytes) still starts a deck, whose file name fits."""
    for name in ("Rats " * 60, "Råttornas kväll och natt " * 12, "x" * 300):
        proc = deck.new(name=name)
        assert "Traceback" not in proc.stderr, proc.stderr
        file = json.loads(proc.stdout)["file"]
        assert re.fullmatch(r"decks/[a-z0-9-]+\.json", file), file
        assert len(file.removeprefix("decks/").encode("utf-8")) <= 255
        built = deck.using(file)
        assert built.tally()["name"] == name
        built.run("page")
        raw = (deck.cwd / file).with_suffix(".html").read_text(encoding="utf-8")
        assert name in title(raw), "the page shows the whole name as given"
        deck.new("Bloodline Keeper", name=name, expect=EXIT_USAGE)  # still never overwritten
    assert len(deck.json("decks")) == 3


# C32 ---------------------------------------------------------------------------------


def assert_s1_page(raw: str):
    """S1's page, section for section, as 017a7a0 rendered it, with S4's unfinished mark beside it (AC17):
    an S1 deck holds 44 of 100 cards and was never reviewed. The bytes were S1's own until S4 (C32)."""
    s1 = read_page((S1 / "deck.html").read_text(encoding="utf-8"))
    page = read_page(raw)
    for key, texts in s1.texts.items():
        assert page.texts.get(key) == texts, f"{key} is as S1 rendered it"
    assert unfinished_mark(44).search(page.section("unfinished")), page.section("unfinished")
    for section in ("measures", "review", "swaps", "maybeboard"):
        assert f"section:{section}" not in page.texts, f"an S1 deck has no {section}"
    assert page.decklist_children == 0


def test_s1_deck_file_opens(deck, unreachable_url):
    """A deck.json written by 017a7a0, with no name, theme, plan or judgements, gives base's tally
    byte for byte and base's page with the unfinished mark, with no network."""
    shutil.copy(S1 / "deck.json", deck.cwd / "deck.json")
    offline = deck.offline(unreachable_url)
    tally = (S1 / "tally.json").read_text(encoding="utf-8")

    assert offline.run("tally").stdout == tally
    assert offline.run("tally", "--deck", "deck.json").stdout == tally
    offline.run("page", "--out", "deck.html")
    assert_s1_page((deck.cwd / "deck.html").read_text(encoding="utf-8"))
    assert (deck.cwd / "deck.json").read_bytes() == (S1 / "deck.json").read_bytes(), "reading it changes nothing"

    # Kept among named decks, it opens there too, and is listed by its file's name.
    (deck.cwd / "decks").mkdir()
    shutil.copy(S1 / "deck.json", deck.cwd / "decks" / "meren-graveyard.json")
    assert offline.run("tally", "--deck", "decks/meren-graveyard.json").stdout == tally
    offline.run("page", "--deck", "decks/meren-graveyard.json", "--out", "old.html")
    assert_s1_page((deck.cwd / "old.html").read_text(encoding="utf-8"))
    assert deck.json("decks") == [
        {"name": "meren-graveyard", "file": "decks/meren-graveyard.json", "commander": COMMANDER}
    ]
