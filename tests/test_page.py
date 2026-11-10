"""The deck page and its decklist: AC8, AC9, AC10, E2, E8, E11; S4's AC15–AC18, E13, E15."""

from __future__ import annotations

import json
import re
import shutil
import time

from conftest import (
    CATEGORIES,
    COMMANDER,
    EXIT_UNREACHABLE,
    Deckwright,
    count_of,
    escaped,
    read_page,
    unfinished_mark,
)

PLAYER_TEXT = "Flying. When this creature enters, draw a card."


def build_with_player_text(deck: Deckwright, unreachable_url: str):
    deck.new()
    deck.add("Command Tower")
    deck.add("Swamp", count=18)
    deck.add("Forest", count=17)
    deck.add("Sol Ring", "Ramp")
    deck.add("Ravenous Chupacabra", "Targeted disruption", "Plan")
    deck.add("Sign in Blood", "Card advantage")
    deck.add("Pernicious Deed", "Mass disruption")
    deck.add("Vampiric Tutor", "Plan")
    deck.add("Lightning Bolt", "Targeted disruption")
    # E2: Scryfall is out of reach; the player gives the card's text.
    deck.add("Homebrew Owl", "Card advantage", api=unreachable_url, expect=EXIT_UNREACHABLE)
    deck.run(
        "add", "Homebrew Owl", "--from-player", PLAYER_TEXT, "--category", "Card advantage", "Plan", api=unreachable_url
    )


# AC8 ---------------------------------------------------------------------------------


def test_page_deterministic(tmp_path, deck, unreachable_url):
    build_with_player_text(deck, unreachable_url)
    first = deck.cwd / "first.html"
    deck.run("page", "--out", str(first), api=unreachable_url)
    time.sleep(1.1)
    deck.run("page", "--out", "second.html", api=unreachable_url)

    # The same deck file somewhere else, at another time, from another folder.
    other = tmp_path / "other-folder"
    other.mkdir()
    shutil.copy2(deck.deck_file, other / "deck.json")
    Deckwright(other, unreachable_url).run("page", "--out", "third.html")

    a = first.read_bytes()
    assert a == (deck.cwd / "second.html").read_bytes()
    assert a == (other / "third.html").read_bytes()
    assert str(deck.cwd).encode() not in a and str(tmp_path).encode() not in a, "no paths on the page"


# AC9 ---------------------------------------------------------------------------------


def test_page_content(deck, unreachable_url):
    build_with_player_text(deck, unreachable_url)
    tally = deck.tally(api=unreachable_url)
    raw = deck.page(api=unreachable_url)
    page = read_page(raw)

    assert COMMANDER in page.section("commander")

    for (name, target), counted in zip(CATEGORIES, tally["categories"]):
        text = page.category(name)
        assert count_of(text, counted["count"], target), f"{name} should show {counted['count']} / {target}: {text!r}"
        for card in counted["cards"]:
            assert card in text, f"{card} counts in {name} and should be listed there"
    assert "Sign in Blood" not in page.category("Ramp")

    total = page.section("total")
    assert count_of(total, tally["total"], 100), total
    assert tally["total"] == 1 + 1 + 18 + 17 + 7

    checks = page.section("checks")
    assert "Lightning Bolt" in checks

    bracket = page.section("bracket")
    assert "Vampiric Tutor" in bracket
    assert re.search(r"target\D{0,40}2(?!\d)", bracket, re.I), bracket
    assert re.search(r"lowest\D{0,40}3(?!\d)", bracket, re.I), bracket

    assert "Homebrew Owl" in page.section("player-text")

    decklist = page.section("decklist")
    assert decklist.strip().startswith("// COMMANDER")
    assert page.decklist_children == 0, "the decklist is plain text inside one element, no markup inside"
    assert escaped(decklist.strip()) in raw

    # The copy button is the page's only script.
    assert page.buttons >= 1
    assert len(page.scripts) <= 1
    assert all("src" not in attrs for attrs in page.scripts), "no script loaded from elsewhere"
    assert "clipboard" in raw


def test_page_marks_player_text(deck, unreachable_url):
    build_with_player_text(deck, unreachable_url)
    page = read_page(deck.page(api=unreachable_url))
    marked = page.section("player-text")
    assert "Homebrew Owl" in marked
    for looked_up in ("Sol Ring", "Vampiric Tutor", "Ravenous Chupacabra", COMMANDER):
        assert looked_up not in marked, f"{looked_up} came from a lookup, not from the player"
    assert "Homebrew Owl" in page.category("Card advantage")
    assert "Homebrew Owl" in page.category("Plan")
    assert "1 Homebrew Owl" in page.section("decklist").splitlines()


# E8 ----------------------------------------------------------------------------------


def test_page_partial_deck(deck, unreachable_url):
    deck.new()
    deck.add("Swamp", count=20)
    deck.add("Forest", count=18)
    deck.add("Sol Ring", "Ramp")
    deck.add("Mana Vault", "Ramp")
    page = read_page(deck.page(api=unreachable_url))

    assert count_of(page.section("total"), 41, 100), page.section("total")
    assert "over" not in page.section("total").lower()
    assert count_of(page.category("Lands"), 38, 38)
    assert count_of(page.category("Ramp"), 2, 10)
    for name, target in CATEGORIES[2:]:
        assert count_of(page.category(name), 0, target), f"{name} is open and should show 0 / {target}"


# AC10, E11 ---------------------------------------------------------------------------


def test_import_format(deck):
    deck.new()
    deck.add("Vampiric Tutor", "Plan")
    deck.add("Swamp", count=10)
    deck.add("Forest", count=15)
    deck.add("Sol Ring", "Ramp")
    deck.add("Forest", count=5)  # E11: 20 Forest in all, one row
    deck.add("Command Tower")
    raw = deck.page()
    decklist = read_page(raw).section("decklist").strip("\n")

    assert decklist.splitlines() == [
        "// COMMANDER",
        "1 Meren of Clan Nel Toth",
        "",
        "// MAINBOARD",
        "1 Command Tower",
        "20 Forest",
        "1 Sol Ring",
        "10 Swamp",
        "1 Vampiric Tutor",
    ]
    assert not re.search(r"\([A-Za-z0-9]{2,6}\)", decklist), "no set codes"
    assert deck.tally()["total"] == 1 + 1 + 20 + 1 + 10 + 1


def test_page_content_not_checked(deck, unreachable_url):
    build_with_player_text(deck, unreachable_url)
    tally = deck.tally(api=unreachable_url)
    for check, names in tally["checks"].items():
        assert "Homebrew Owl" not in names, f"a card from the player's text is not checked, so not flagged by {check}"
    checks = read_page(deck.page(api=unreachable_url)).section("checks")
    assert re.search(r"not checked", checks, re.I), f"cards from the player's text are not checked: {checks!r}"
    assert "Lightning Bolt" in checks


def test_page_bracket_over(deck):
    over = re.compile(r"\bover\b", re.I)
    deck.new()
    deck.add("Sol Ring", "Ramp")
    deck.run("bracket", "1")
    bracket = read_page(deck.page()).section("bracket")
    assert not over.search(bracket), f"target 1 with no Game Changers is not over: {bracket!r}"

    deck.run("bracket", "2")
    deck.add("Vampiric Tutor", "Plan")
    bracket = read_page(deck.page()).section("bracket")
    assert over.search(bracket), f"target 2 with one Game Changer is over: {bracket!r}"

    deck.run("bracket", "3")
    bracket = read_page(deck.page()).section("bracket")
    assert not over.search(bracket), f"target 3 with one Game Changer is not over: {bracket!r}"


# S4: the finished page -----------------------------------------------------------------


def reviewable(deck: Deckwright) -> Deckwright:
    """A deck at its deck size, holding a land that makes no mana."""
    deck.new()
    deck.add("Sol Ring", "Ramp")
    deck.add("Sign in Blood", "Card advantage")
    deck.add("Ravenous Chupacabra", "Targeted disruption", "Plan")
    deck.add("Pernicious Deed", "Mass disruption")
    deck.add("Evolving Wilds")
    deck.fill()
    return deck


def raw_section(raw: str, name: str) -> str:
    """The source of one marked section, from its mark to the next section's (or the end)."""
    start = raw.index(f'data-section="{name}"')
    end = raw.find("data-section=", start + 1)
    return raw[start : end if end != -1 else len(raw)]


# AC15 --------------------------------------------------------------------------------


def test_decklist_maybeboard_section(deck):
    reviewable(deck)
    plain = read_page(deck.page()).section("decklist").strip("\n").splitlines()
    assert "// MAYBEBOARD" not in plain, "with no maybeboard, the decklist is S1's"
    assert plain[:4] == ["// COMMANDER", "1 Meren of Clan Nel Toth", "", "// MAINBOARD"]
    assert plain[-1] != ""

    deck.maybeboard_add("Vampiric Tutor", "Sign in Blood", "Finds the answer")
    deck.maybeboard_add("demonic tutor", "Sol Ring", "Finds anything")
    deck.maybeboard_add("Feed the Cycle", "Ravenous Chupacabra", "Cheaper")
    page = read_page(deck.page())
    lines = page.section("decklist").strip("\n").splitlines()
    assert lines[: len(plain)] == plain, "the commander and the mainboard are unchanged"
    assert lines[len(plain) :] == ["", "// MAYBEBOARD", "1 Demonic Tutor", "1 Feed the Cycle", "1 Vampiric Tutor"], (
        "a blank line, // MAYBEBOARD, then one `1 Name` row per card, names only, sorted as the mainboard is"
    )
    assert page.decklist_children == 0


# AC16 --------------------------------------------------------------------------------


def test_finished_page_sections(deck):
    reviewable(deck)
    deck.maybeboard_add("Demonic Tutor", "Sol Ring", "Finds the missing piece")
    deck.swap("Sign in Blood", "Feed the Cycle", "Removal was short", "--category", "Targeted disruption")
    measured = deck.measure()
    deck.review("The deck wins late, through Meren's recursion.")
    page = read_page(deck.page())

    assert "section:unfinished" not in page.texts, "a finished deck carries no unfinished mark"

    measures = page.section("measures")
    assert "Evolving Wilds" in measures, "the lands that make no mana"
    average = measured["average_mana_value"]
    assert re.search(rf"(?<![\d.]){average:.2f}(?!\d)|(?<![\d.]){average}(?![\d])", measures), (
        f"the average mana value as measure printed it, {average}: {measures!r}"
    )
    assert "The deck wins late, through Meren's recursion." in page.section("review")

    swaps = page.section("swaps")
    for part in ("Sign in Blood", "Feed the Cycle", "Removal was short"):
        assert part in swaps, f"the swap's {part!r}: {swaps!r}"
    maybeboard = page.section("maybeboard")
    for part in ("Demonic Tutor", "Sol Ring", "Finds the missing piece"):
        assert part in maybeboard, f"the maybeboard's {part!r}: {maybeboard!r}"
    assert "Demonic Tutor" not in page.category("Plan"), "a maybeboard card counts nowhere"


# AC17, E13 ---------------------------------------------------------------------------


def test_unfinished_mark(deck):
    deck.new()
    deck.add("Sol Ring", "Ramp")
    deck.add("Swamp", count=32)
    page = read_page(deck.page())
    assert unfinished_mark(34).search(page.section("unfinished")), page.section("unfinished")
    for section in ("measures", "review"):
        assert f"section:{section}" not in page.texts, f"an unreviewed deck has no {section} section"

    # E13: at the deck size, stopped before the review.
    deck.fill()
    assert unfinished_mark(100).search(read_page(deck.page()).section("unfinished"))
    # Measured, with no written review yet: still not reviewed.
    deck.measure()
    assert unfinished_mark(100).search(read_page(deck.page()).section("unfinished"))
    deck.review("Done.")
    assert "section:unfinished" not in read_page(deck.page()).texts

    # Over the deck size is unfinished too.
    deck.add("Forest", count=2)
    assert unfinished_mark(102).search(read_page(deck.page()).section("unfinished"))


# AC18, E15 ---------------------------------------------------------------------------

NASTY = "Wins with <script>alert(1)</script> & &amp; {T}: **bold**, _not em_, # no heading, [no](link)."
SECOND = "Second paragraph\nwith a line break inside it."


def test_review_text_is_plain(deck):
    reviewable(deck)
    deck.maybeboard_add("Demonic Tutor", "Sol Ring", NASTY)
    deck.swap("Sign in Blood", "Feed the Cycle", NASTY)
    deck.measure()
    deck.review(f"{NASTY}\n\n{SECOND}")
    raw = deck.page()
    page = read_page(raw)

    for section in ("review", "swaps", "maybeboard"):
        text = page.section(section)
        assert NASTY in text, f"{section} shows the text as written: {text!r}"
        assert escaped(NASTY) in raw_section(raw, section), f"{section} escapes it, nothing more"
    assert "Second paragraph" in page.section("review")

    # Nothing in the text is read as HTML or Markdown.
    assert len(page.scripts) <= 1 and "alert(1)</script>" not in raw.replace(escaped("alert(1)</script>"), "")
    for tag in ("<strong", "<b>", "<em", "<i>", "<h1", "<a ", "<a>"):
        assert tag not in raw_section(raw, "review").lower(), f"no {tag} from the text"
    assert "&amp;amp;" in raw_section(raw, "review"), "a written &amp; is shown as those five characters"

    # Blank lines make paragraphs: the two are in separate elements.
    review = raw_section(raw, "review")
    between = review[review.index("no](link).") : review.index("Second paragraph")]
    assert re.search(r"<\w", between), f"the paragraphs are separate elements: {between!r}"


def test_measures_are_plain(deck):
    """R1: what the deck file's stored measures hold is shown as text, never read as markup, the colour
    and the theme density included: a deck file is the builder's to write, and can be edited by hand."""
    reviewable(deck)
    deck.run("theme", "Graveyard")
    deck.measure()
    stored = deck.stored()
    measures = stored["review"]["measures"]
    measures["colours"][0]["colour"] = "<b>B</b>"
    measures["theme_density"] = {"serving": "<i>7</i>", "of": 99}
    deck.deck_file.write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")

    raw = raw_section(deck.page(), "measures")
    for markup in ("<b>B</b>", "<i>7</i>"):
        assert markup not in raw, f"{markup} is read as markup: {raw!r}"
        assert escaped(markup) in raw, f"{markup} is shown as written, escaped: {raw!r}"
