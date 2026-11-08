"""The player's collection and what of it is available: C6–C13, E1–E8, E16.

`tests/fixtures/collection/manabox.csv` is 35 real rows of the owner's ManaBox export, CRLF, every
`Purchase price` blank. Other collections are built here from recorded printings with
`manabox_row`, in the export's own column order, or written as `N Name` lines.
"""

from __future__ import annotations

import csv
import io

import pytest
from conftest import (
    COMMANDER,
    EXIT_USAGE,
    MANABOX,
    MANABOX_HEADER,
    copy_tree_files,
    manabox_csv,
    manabox_row,
    printing,
    scryfall_card,
    write_file,
)

GROUPS = ("near_miss", "not_a_card", "unknown")


@pytest.fixture
def player(tmp_path):
    """A folder of the player's own, outside the working folder."""
    folder = tmp_path / "player"
    folder.mkdir()
    return folder


def hand_over(deck, player, name: str, content: str | bytes, **kw) -> dict:
    return deck.collection(write_file(player, name, content), **kw)


def copies(available: dict) -> dict[str, tuple[int, int]]:
    """Each card's (owned, available), by name; asserts each card is listed once."""
    names = [c["name"] for c in available["cards"]]
    assert len(names) == len(set(names)), f"a card is listed more than once: {names}"
    return {c["name"]: (c["owned"], c["available"]) for c in available["cards"]}


def held_back(available: dict) -> list[tuple[str, int]]:
    return sorted((h["binder"], h["copies"]) for h in available["held_back"])


def reported(report: dict) -> int:
    return sum(len(report[g]) for g in GROUPS) + len(report["needs_quantity"])


def is_token(card: dict) -> bool:
    return card["layout"] in ("token", "double_faced_token") or card.get("set_type") == "token"


def fixture_copies() -> dict[str, int]:
    """Copies per card in manabox.csv, from its rows and their printings: tokens are not the card."""
    totals: dict[str, int] = {}
    for row in csv.DictReader(io.StringIO(MANABOX.read_text(encoding="utf-8"), newline="")):
        card = printing(row["Set code"].lower(), row["Collector number"])
        assert card["id"] == row["Scryfall ID"]
        if not is_token(card):
            totals[card["name"]] = totals.get(card["name"], 0) + int(row["Quantity"])
    return totals


# C6, E4 ------------------------------------------------------------------------------


def test_collection_csv_quantities(deck, player):
    report = deck.collection(MANABOX)
    assert report["entries"] == 35, "every row of the export is an entry"
    assert report["matched"] == 35, f"every real row matches a card or a token: {report}"
    assert reported(report) == 0, report

    owned = copies(deck.available())
    expected = fixture_copies()
    assert {name: o for name, (o, _) in owned.items()} == expected
    # Spot checks, so the expectation above is not only computed: copies summed across rows,
    # printings and finishes; basics count what the rows say.
    assert owned["Uncharted Haven"] == (14, 14), "3 + 1 foil from Bloomburrow, 10 from Foundations"
    assert owned["Starscape Cleric"] == (6, 6)
    assert owned["Moonrise Cleric"] == (5, 5)
    assert owned["Forest"] == (15, 15) and owned["Swamp"] == (14, 14) and owned["Plains"] == (14, 14)
    assert owned["Honorbound Page // Forum's Favor"] == (1, 1)
    assert deck.available()["held_back"] == [], "the export's one binder is a binder, not a deck"

    # E4: one card on many rows, across binders and printings: one card, copies summed, each
    # copy keeping its binder.
    haven_blb, haven_fdn = printing("blb", "261"), printing("fdn", "564")
    rows = [
        manabox_row(haven_blb, 3, "Lands", "binder"),
        manabox_row(haven_fdn, 10, "Vren deck", "deck"),
        manabox_row(haven_blb, 1, "Trade binder", "binder"),
        manabox_row(haven_fdn, 2, "Lands", "binder"),
    ]
    report = hand_over(deck, player, "binders.csv", manabox_csv(*rows))
    assert (report["entries"], report["matched"]) == (4, 4)
    available = deck.available()
    assert copies(available) == {"Uncharted Haven": (16, 6)}
    assert held_back(available) == [("Vren deck", 10)]


# C7, E6 ------------------------------------------------------------------------------


def test_collection_lines(deck, player):
    lines = "4 Swamp\n1 Sol Ring\nVampiric Tutor\n1 Lord of Lineage\n\n1 Honorbound Page\n2 Forest\n"
    lines += "1 smugglers copter\n"
    report = hand_over(deck, player, "my cards.txt", lines)
    assert report["entries"] == 7, "every line but the blank one"
    assert report["matched"] == 6
    assert report["needs_quantity"] == [{"name": "Vampiric Tutor", "line": 3}]
    assert all(report[g] == [] for g in GROUPS), report

    owned = copies(deck.available())
    assert owned == {
        "Swamp": (4, 4),
        "Sol Ring": (1, 1),
        # E6: a double-faced card by one face's name, back or front, is its card.
        "Bloodline Keeper // Lord of Lineage": (1, 1),
        "Honorbound Page // Forum's Favor": (1, 1),
        "Forest": (2, 2),
        "Smuggler's Copter": (1, 1),
    }, "a line without a number counts nothing"
    assert deck.available()["held_back"] == [], "lines have no binders"


# C8 ----------------------------------------------------------------------------------


def test_collection_token_by_printing(deck):
    report = deck.collection(MANABOX)
    assert report["matched"] == report["entries"], "a token lot matches, as a token"
    owned = copies(deck.available())
    # Six copies of the card on three rows, and a token lot of two by the same name.
    assert owned["Starscape Cleric"] == (6, 6)
    assert owned["Splash Lasher"] == (2, 2)

    deck.new()
    cleric = [e for e in deck.read()["cards"] if e["name"] == "Starscape Cleric"]
    assert len(cleric) == 1 and cleric[0]["available"] == 6
    assert cleric[0]["card"]["type_line"] == "Creature — Bat Cleric", "the card, not the token"


# C9 ----------------------------------------------------------------------------------


def test_collection_printing_missing_matches_name(deck, scryfall, player):
    masterpiece = printing("soa", "35")
    # The masterpiece printing is newer than the bulk file; Vampiric Tutor is in it by another printing.
    scryfall.bulk = [c for c in scryfall.bulk if c["id"] != masterpiece["id"]]
    assert any(c["name"] == "Vampiric Tutor" for c in scryfall.bulk)

    rows = manabox_row(masterpiece, 1), manabox_row(printing("fdn", "280"), 3)
    report = hand_over(deck, player, "export.csv", manabox_csv(*rows))
    assert (report["entries"], report["matched"]) == (2, 2), report
    assert copies(deck.available()) == {"Vampiric Tutor": (1, 1), "Forest": (3, 3)}


# C10, E5 -----------------------------------------------------------------------------


def test_collection_unmatched_reported(deck, player):
    lines = "1 Cultivat\n1 Sol Ring\n1 Xyzzy Plover Quux\n2 Forest\n1 Vampiric Tutr\n"
    report = hand_over(deck, player, "list.txt", lines)

    near = {(m["name"], m["line"]): m["card"] for m in report["near_miss"]}
    # E5: a typo is a near miss naming the card it nearly names.
    assert near.get(("Cultivat", 1)) == "Cultivate", report
    assert near.get(("Vampiric Tutr", 5)) == "Vampiric Tutor", report
    groups = [g for g in GROUPS for m in report[g] if (m["name"], m["line"]) == ("Xyzzy Plover Quux", 3)]
    assert len(groups) == 1 and groups[0] != "near_miss", f"a name that is no card is reported once: {report}"
    named = [(m["name"], m["line"]) for g in GROUPS for m in report[g]]
    assert len(named) == len(set(named)) == 3, f"each unmatched line in exactly one group: {report}"

    assert report["matched"] == 2
    assert report["matched"] + reported(report) == report["entries"] == 5
    assert copies(deck.available()) == {"Sol Ring": (1, 1), "Forest": (2, 2)}, "nothing unmatched is counted"

    # The same for an export: a row is reported by its row number, the header being row 1.
    unknown_id = "00000000-0000-4000-8000-000000000000"
    rows = [
        manabox_row(scryfall_card("Sol Ring"), 1),
        manabox_row({**printing("trc", "460"), "id": unknown_id, "name": "Cultivat"}, 1),
        manabox_row({**printing("trc", "460"), "id": unknown_id, "name": "Xyzzy Plover Quux"}, 2),
    ]
    report = hand_over(deck, player, "export.csv", manabox_csv(*rows))
    near = {(m["name"], m["row"]): m["card"] for m in report["near_miss"]}
    assert near == {("Cultivat", 3): "Cultivate"}, report
    other = [(g, m["row"]) for g in GROUPS for m in report[g] if m["name"] == "Xyzzy Plover Quux"]
    assert len(other) == 1 and other[0] in {("not_a_card", 4), ("unknown", 4)}, report
    assert report["matched"] + reported(report) == report["entries"] == 3
    assert copies(deck.available()) == {"Sol Ring": (1, 1)}


# C11 ---------------------------------------------------------------------------------


def test_collection_kept_as_is(deck, player):
    first = MANABOX.read_bytes()
    handed = write_file(player, "ManaBox_Collection.csv", first)
    deck.collection(handed)
    handed.unlink()

    kept = copy_tree_files(deck.cwd)
    assert first in kept.values(), "the file handed over is kept in the working folder, byte for byte"
    assert copies(deck.available())["Starscape Cleric"] == (6, 6), "the kept copy is the one read"

    second = b"3 Sol Ring\r\n1 Forest\r\n"
    handed = write_file(player, "today.txt", second)
    deck.collection(handed)
    handed.unlink()
    kept = copy_tree_files(deck.cwd)
    assert second in kept.values(), "the new file is kept byte for byte"
    assert first not in kept.values(), "handing over another replaces the first"
    assert copies(deck.available()) == {"Sol Ring": (3, 3), "Forest": (1, 1)}


# E1 ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [MANABOX_HEADER + "\r\n", b"", "\n\n"],
    ids=["header only", "empty file", "blank lines"],
)
def test_collection_empty(deck, player, content):
    report = hand_over(deck, player, "collection.csv", content)
    assert (report["entries"], report["matched"], reported(report)) == (0, 0, 0)
    available = deck.available()
    assert available["cards"] == [] and available["held_back"] == [], "a collection of no cards"

    deck.new()
    read = deck.read()
    assert read["cards"] == [] and read["unjudged"] == 0


# E2 ----------------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["Scryfall ID", "Name", "Quantity"])
def test_collection_unreadable(deck, player, missing):
    columns = MANABOX_HEADER.split(",")
    keep = [i for i, c in enumerate(columns) if c != missing]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    for row in csv.reader(io.StringIO(MANABOX.read_text(encoding="utf-8"), newline="")):
        writer.writerow([row[i] for i in keep])
    broken = out.getvalue()
    path = write_file(player, "export.csv", broken)

    proc = deck.run("collection", str(path), expect=EXIT_USAGE)
    said = proc.stdout + proc.stderr
    assert missing in said, f"the message names the missing column: {said!r}"
    assert "Traceback" not in proc.stderr, proc.stderr
    assert broken.encode() not in copy_tree_files(deck.cwd).values(), "nothing is kept"
    deck.run("available", expect=EXIT_USAGE)


@pytest.mark.parametrize(
    "content",
    [b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00", b"\xc3\x28 not text \xa0\xa1\x00\x9f"],
    ids=["an image", "not UTF-8"],
)
def test_collection_unreadable_neither_shape(deck, player, content):
    hand_over(deck, player, "before.txt", "2 Forest\n")
    path = write_file(player, "collection.csv", content)

    proc = deck.run("collection", str(path), expect=EXIT_USAGE)
    assert (proc.stdout + proc.stderr).strip(), "it says why"
    assert "Traceback" not in proc.stderr, proc.stderr
    assert content not in copy_tree_files(deck.cwd).values(), "nothing is kept"
    assert copies(deck.available()) == {"Forest": (2, 2)}, "the collection kept before stays"


# E3 ----------------------------------------------------------------------------------


def test_collection_bad_quantity(deck, player):
    rows = [
        manabox_row(scryfall_card("Sol Ring"), 0),
        manabox_row(scryfall_card("Forest"), "three"),
        manabox_row(scryfall_card("Swamp"), 4),
        manabox_row(scryfall_card("Command Tower"), ""),
    ]
    report = hand_over(deck, player, "export.csv", manabox_csv(*rows))
    assert sorted((m["name"], m["row"]) for m in report["needs_quantity"]) == [
        ("Command Tower", 5),
        ("Forest", 3),
        ("Sol Ring", 2),
    ], report
    assert report["matched"] == 1
    assert report["matched"] + reported(report) == report["entries"] == 4
    assert copies(deck.available()) == {"Swamp": (4, 4)}, "a row with no good quantity counts nothing"

    report = hand_over(deck, player, "list.txt", "0 Sol Ring\n4 Swamp\nx Forest\n")
    assert {m["line"] for m in report["needs_quantity"]} == {1, 3}, report
    assert copies(deck.available()) == {"Swamp": (4, 4)}


# E16 ---------------------------------------------------------------------------------


def test_collection_replaced_mid_build(deck, player):
    hand_over(deck, player, "first.txt", "12 Forest\n1 Sol Ring\n")
    deck.new()
    deck.add("Forest", count=15)
    deck.add("Sol Ring", "Ramp")
    owned = {c["name"]: (c["owned"], c["not_owned"]) for c in deck.tally()["ownership"]["cards"]}
    assert owned == {"Forest": (12, 3), "Sol Ring": (1, 0)}

    hand_over(deck, player, "second.txt", "15 Forest\n")
    owned = {c["name"]: (c["owned"], c["not_owned"]) for c in deck.tally()["ownership"]["cards"]}
    assert owned == {"Forest": (15, 0), "Sol Ring": (0, 1)}, "the not-owned marks follow the new file"
    assert copies(deck.available()) == {"Forest": (15, 15)}
    read = {e["name"]: e["available"] for e in deck.read()["cards"]}
    assert read == {"Forest": 15}


# C12, E7, E8 -------------------------------------------------------------------------

BINDERS = [
    manabox_row(scryfall_card("Sol Ring"), 1, "Trade binder", "binder"),
    manabox_row(scryfall_card("Sol Ring"), 1, "Vren deck", "deck"),
    manabox_row(scryfall_card("Vampiric Tutor"), 1, "Vren deck", "deck"),
    manabox_row(scryfall_card("Forest"), 10, "Lands", "binder"),
    manabox_row(scryfall_card("Forest"), 5, "Meren deck", "deck"),
]


def test_available_holds_back_deck_binders(deck, player):
    hand_over(deck, player, "export.csv", manabox_csv(*BINDERS))
    available = deck.available()
    owned = copies(available)
    # E7: two copies owned, one in a deck binder: one available.
    assert owned["Sol Ring"] == (2, 1)
    assert owned["Vampiric Tutor"] == (1, 0)
    assert owned["Forest"] == (15, 10)
    assert held_back(available) == [("Meren deck", 5), ("Vren deck", 2)], "how many, per binder name"

    deck.new()
    read = {e["name"]: e["available"] for e in deck.read()["cards"]}
    assert read.get("Sol Ring") == 1 and read.get("Forest") == 10
    assert "Vampiric Tutor" not in read, "a card with no copy available is not in the narrowing"

    # E8: a list of lines has no binders: every copy is available.
    hand_over(deck, player, "list.txt", "2 Sol Ring\n15 Forest\n1 Vampiric Tutor\n")
    available = deck.available()
    assert copies(available) == {"Sol Ring": (2, 2), "Forest": (15, 15), "Vampiric Tutor": (1, 1)}
    assert available["held_back"] == []


# C13 ---------------------------------------------------------------------------------


def test_available_filter(deck, player):
    hand_over(deck, player, "export.csv", manabox_csv(*BINDERS))

    # "Use the cards in my Vren deck too."
    included = deck.available("--include", "Vren deck")
    assert copies(included)["Sol Ring"] == (2, 2)
    assert copies(included)["Vampiric Tutor"] == (1, 1)
    assert held_back(included) == [("Meren deck", 5)], "it says what it still leaves out"

    # "Leave my trade binder out."
    excluded = deck.available("--exclude", "Trade binder")
    assert copies(excluded)["Sol Ring"] == (2, 0)
    assert held_back(excluded) == [("Meren deck", 5), ("Trade binder", 1), ("Vren deck", 2)]

    # Without a deck, a filter is that call's only.
    assert held_back(deck.available()) == [("Meren deck", 5), ("Vren deck", 2)]

    # Given with a deck, the deck keeps it: later commands for that deck use it.
    deck.new(COMMANDER)
    deck.run("available", "--deck", "deck.json", "--include", "Vren deck")
    later = deck.available("--deck", "deck.json")
    assert held_back(later) == [("Meren deck", 5)]
    read = {e["name"]: e["available"] for e in deck.read()["cards"]}
    assert read.get("Vampiric Tutor") == 1 and read.get("Sol Ring") == 2

    # Given again, it replaces what the deck kept.
    deck.run("available", "--deck", "deck.json", "--exclude", "Trade binder")
    read = {e["name"]: e["available"] for e in deck.read()["cards"]}
    assert "Vampiric Tutor" not in read and read.get("Sol Ring") is None
