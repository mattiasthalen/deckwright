"""Cards recorded beyond what the collection has available: C27, E12, E13."""

from __future__ import annotations

import json
import re
import shutil

import pytest
from conftest import (
    COMMANDER,
    EXIT_UNREACHABLE,
    EXIT_USAGE,
    Deckwright,
    manabox_csv,
    manabox_row,
    read_page,
    scryfall_card,
    write_file,
)


@pytest.fixture
def player(tmp_path):
    folder = tmp_path / "player"
    folder.mkdir()
    return folder


def ownership(tally: dict) -> dict[str, tuple[int, int]]:
    cards = tally["ownership"]["cards"]
    names = [c["name"] for c in cards]
    assert len(names) == len(set(names)), f"a card is listed more than once: {names}"
    return {c["name"]: (c["owned"], c["not_owned"]) for c in cards}


def totals(tally: dict) -> tuple[int, int]:
    return tally["ownership"]["owned"], tally["ownership"]["not_owned"]


def shows(section: str, label: str, owned: int, not_owned: int) -> bool:
    """Whether the page's ownership section shows `<label> … N owned … M not owned`."""
    pattern = rf"{re.escape(label)}\D{{0,40}}?(?<!\d){owned} owned\D{{0,40}}?(?<!\d){not_owned} not owned"
    return re.search(pattern, section, re.I) is not None


# C27, E12 ----------------------------------------------------------------------------


def test_not_owned_marked(deck, player):
    deck.collection(write_file(player, "cards.txt", "12 Forest\n1 Sol Ring\n1 Vampiric Tutor\n"))
    built = deck.named("Owned or Not")
    built.add("Forest", count=15)  # E12: 12 owned, 3 after a yes to cards not owned
    built.add("Sol Ring", "Ramp")
    built.add("Mana Vault", "Ramp")  # not in the collection at all
    built.add("Swamp", count=2)

    tally = built.tally()
    assert ownership(tally) == {
        "Forest": (12, 3),
        "Mana Vault": (0, 1),
        "Sol Ring": (1, 0),
        "Swamp": (0, 2),
    }, "every recorded card, the commander apart, with its copies owned and not owned"
    assert totals(tally) == (13, 6)
    assert sum(o + n for o, n in ownership(tally).values()) == tally["total"] - 1

    page = read_page(built.page())
    section = page.section("ownership")
    assert shows(section, "Forest", 12, 3), section
    assert shows(section, "Mana Vault", 0, 1), section
    assert shows(section, "Swamp", 0, 2), section
    assert shows(section, "Total", 13, 6), section
    assert "15 Forest" in page.section("decklist").splitlines(), "the decklist holds every copy recorded"


def test_not_owned_marked_deck_binder(deck, player):
    rows = [
        manabox_row(scryfall_card("Sol Ring"), 1, "Trade binder", "binder"),
        manabox_row(scryfall_card("Sol Ring"), 1, "Vren deck", "deck"),
    ]
    deck.collection(write_file(player, "export.csv", manabox_csv(*rows)))
    deck.new()
    deck.add("Sol Ring", "Ramp", count=2)
    assert ownership(deck.tally()) == {"Sol Ring": (1, 1)}, "a copy held back in a deck binder is not available"

    deck.run("available", "--deck", "deck.json", "--include", "Vren deck")
    assert ownership(deck.tally()) == {"Sol Ring": (2, 0)}, "the deck's filter decides what it owns"


def test_not_owned_marked_only_with_a_collection(tmp_path, scryfall):
    work = tmp_path / "no-collection"
    work.mkdir()
    plain = Deckwright(work, scryfall.url)
    plain.new()
    plain.add("Forest", count=15)
    assert "ownership" not in plain.tally(), "without a collection there is nothing to own"
    assert "section:ownership" not in read_page(plain.page()).texts


# E13 ---------------------------------------------------------------------------------


def test_not_owned_removed_first(deck, player):
    deck.collection(write_file(player, "cards.txt", "12 Forest\n"))
    built = deck.named("Removals")
    built.add("Forest", count=15)

    built.run("remove", "Forest", "--count", "2")
    tally = built.tally()
    assert ownership(tally) == {"Forest": (12, 1)}, "the copies not owned go first"
    assert totals(tally) == (12, 1)

    built.run("remove", "Forest", "--count", "2")
    tally = built.tally()
    assert ownership(tally) == {"Forest": (11, 0)}
    assert totals(tally) == (11, 0)
    assert shows(read_page(built.page()).section("ownership"), "Total", 11, 0)


# D3: the player's answer to building with cards they do not own -------------------------


def test_not_owned_answer_recorded(deck, player):
    deck.collection(write_file(player, "cards.txt", "1 Sol Ring\n"))
    asked = deck.named("Asked Once")
    other = deck.named("Never Asked")
    assert "not_owned" not in asked.tally(), "absent until the player answers"

    before = asked.deck_file.read_bytes()
    other_before = other.deck_file.read_bytes()
    asked.run("not-owned", "yes")
    assert asked.deck_file.read_bytes() != before, "the answer is kept in the deck's file"
    assert asked.tally()["not_owned"] is True
    assert other.deck_file.read_bytes() == other_before and "not_owned" not in other.tally(), "and only in that deck's"

    asked.run("not-owned", "no")
    assert asked.tally()["not_owned"] is False, "a new answer replaces the old"
    asked.add("Sol Ring", "Ramp")
    asked.run("theme", "Artifacts")
    assert asked.tally()["not_owned"] is False, "and survives later commands"

    mid = asked.deck_file.read_bytes()
    proc = asked.run("not-owned", "maybe", expect=EXIT_USAGE)
    assert "Traceback" not in proc.stderr
    assert asked.deck_file.read_bytes() == mid


# A12: ownership joins through the card's names and faces ----------------------------------


def test_not_owned_joined_by_card_names(deck, player, unreachable_url):
    lines = "1 Bloodline Keeper\n1 Forum's Favor\n1 Smuggler's Copter\n2 Lim-Dûl's Vault\n"
    deck.collection(write_file(player, "cards.txt", lines))
    built = deck.named("Spellings")
    built.add("Honorbound Page", "Plan")  # looked up: recorded as Honorbound Page // Forum's Favor
    offline = built.offline(unreachable_url)
    # From the player's text, under other spellings of the card's name.
    offline.run("add", "smugglers copter", "--from-player", "Flying. Crew 1.", "--category", "Plan")
    offline.run("add", "Lim-Dul's Vault", "--from-player", "Draw.", "--count", "2", "--category", "Plan")

    owned = ownership(built.tally())
    assert owned == {
        "Honorbound Page // Forum's Favor": (1, 0),
        "Lim-Dul's Vault": (2, 0),
        "smugglers copter": (1, 0),
    }, "a card recorded under a face name or another spelling is the card the player owns"
    assert totals(built.tally()) == (4, 0)


def test_not_owned_joined_by_face_name_from_player(deck, player, unreachable_url):
    """A12: the collection holds Bloodline Keeper // Lord of Lineage; the deck holds it from the
    player's text under its back face's name. The face name is the card's, so it is owned."""
    deck.collection(write_file(player, "cards.txt", "1 Bloodline Keeper\n"))
    built = deck.named("Back Face")
    built.offline(unreachable_url).run("add", "Lord of Lineage", "--from-player", "Flying.", "--category", "Plan")
    assert ownership(built.tally()) == {"Lord of Lineage": (1, 0)}


# A7, D16: with a collection and no bulk file, counting and rendering stay off the network --

COUNT_OR_RENDER = [
    ("tally",),
    ("page", "--out", "elsewhere.html"),
    ("target", "Ramp", "9"),
    ("bracket", "3"),
    ("remove", "Sol Ring"),
    ("theme", "Elves and their mana"),
    ("plan", "Ramp out an early commander."),
]


def test_not_owned_no_bulk_file_counts_offline(deck, scryfall, player):
    deck.collection(write_file(player, "cards.txt", "12 Forest\n1 Sol Ring\n"))
    built = deck.named("No Bulk Here")
    built.add("Forest", count=15)
    built.add("Sol Ring", "Ramp", count=2)
    assert "ownership" in built.tally()

    shutil.rmtree(deck.cache)  # no bulk file, and nothing else the cache held
    scryfall.requests.clear()
    scryfall.data_requests.clear()
    for args in COUNT_OR_RENDER:
        proc = built.run(*args)
        assert '"ownership"' not in proc.stdout, f"{args[0]} prints no ownership it could not compute"
    assert "ownership" not in built.tally()
    assert "section:ownership" not in read_page(built.page()).texts
    assert not scryfall.requests and not scryfall.data_requests, (
        "a command that only counts or renders never downloads",
        [r.path for r in scryfall.requests],
        [r.path for r in scryfall.data_requests],
    )

    # Once a lookup has fetched the file again, ownership is back.
    assert deck.json("lookup", "Forest")[0]["result"] == "found"
    assert ownership(built.tally())["Forest"] == (12, 3)


def test_not_owned_no_bulk_file_new(deck, player, unreachable_url):
    """`new` with a collection kept and no bulk file to be had either starts the deck or fails
    having written nothing: never a deck file left behind by a failure."""
    deck.collection(write_file(player, "cards.txt", "12 Forest\n"))
    shutil.rmtree(deck.cache)
    deck.cache.mkdir()
    (deck.cache / "meren-of-clan-nel-toth.json").write_text(json.dumps(scryfall_card(COMMANDER)), encoding="utf-8")
    offline = deck.offline(unreachable_url)

    proc = offline.new(name="Fails Cleanly", expect=None)
    assert "Traceback" not in proc.stderr, proc.stderr
    written = deck.cwd / "decks" / "fails-cleanly.json"
    if proc.returncode == 0:
        assert written.is_file()
        assert "ownership" not in offline.using("decks/fails-cleanly.json").tally()
    else:
        assert proc.returncode == EXIT_UNREACHABLE, (proc.returncode, proc.stdout, proc.stderr)
        assert not written.exists(), "a failed new writes no deck file"
        assert not (deck.cwd / "decks").exists() or not any((deck.cwd / "decks").iterdir())
