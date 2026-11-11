"""Tests for the checks and the runner that need no model and no Scryfall.

    python3 evals/test_checks.py

Each one was found red by the pre-PR review of 2026-11-11 and fixed.
"""

from __future__ import annotations

import pathlib
import sys
import traceback
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import checks  # noqa: E402
import run as runner  # noqa: E402

FACT_NULL = {"holds": None, "evidence": ""}


def card(name, type_line, cost="", ci=(), fmt_legal=("brawl", "standard")):
    return {"name": name, "type_line": type_line, "mana_cost": cost, "color_identity": list(ci),
            "legalities": {f: "legal" for f in fmt_legal}, "on_arena": True}


def facts(**over):
    base = {"format": "brawl", "deck_colours": [], "offers": [], "confirmations": [], "basic_split_confirmed": True,
            "review_type_counts": [], "criterion_change_recorded_with_reason": None,
            "card_removed_without_player_word": [], "dismissed_finding_raised_again": None,
            "saved_categories": [], **{k: FACT_NULL for k in checks.EXTRA_FACTS}}
    base.update(over)
    return base


def fake_run(messages, trace, deck=None, start=None, brief="x"):
    r = object.__new__(checks.Run)
    r.path = pathlib.Path("/nonexistent")
    r.summary = {"brief": brief, "start": start, "ended": "player ended", "exchanges": 1, "deckwright_cost_usd": 0}
    r.messages = messages
    r.trace = trace
    r.files = {}
    r.published = {}
    r.deck = lambda: deck
    r.start = start
    return r


def test_c4_is_not_applicable_without_picks():
    # brawl-rats-template ends at the template by design: no pick can be made.
    r = fake_run([{"role": "player", "text": "go"}, {"role": "deckwright", "text": "saved"}], [])
    f = facts()
    r.read = lambda: f
    results = checks.check(r, {})
    assert results["C4"][0] != "fail", results["C4"]


def test_c4_does_not_count_a_refused_publish():
    trace = [
        {"exchange": 0, "type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Artifact", "input": {"file_path": "index.html"}}]}},
        {"exchange": 0, "type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "is_error": True,
             "content": "publish 429: daily publish limit for your plan reached (200)"}]}},
    ]
    r = fake_run([{"role": "player", "text": "I'll take Sol Ring"}, {"role": "deckwright", "text": "added"}], trace)
    assert r.saves_by_exchange().get(0, 0) == 0, "a refused publish was counted as the pick's save"


def test_c3_needs_the_whole_name():
    trace = [{"exchange": 0, "type": "user", "message": {"content": [
        {"type": "tool_result", "content": "Usage: curl [options...] <url>"}]}}]
    r = fake_run([{"role": "player", "text": "hi"}, {"role": "deckwright", "text": "Try Opt"}], trace)
    seen = r.tool_results_before(0).lower()
    assert not checks.named_in("Opt", seen), "Opt counts as looked up because 'options' was in a curl usage line"
    assert checks.named_in("Opt", '{"name": "opt"}')


def test_c3_counts_only_lookups_in_the_same_conversation():
    trace = [
        {"conversation": 1, "exchange": 0, "type": "user", "message": {"content": [
            {"type": "tool_result", "content": '{"name": "Lightning Helix"}'}]}},
        {"conversation": 2, "exchange": 1, "type": "assistant", "message": {"content": []}},
    ]
    messages = [{"role": "player", "conversation": 1, "text": "a"}, {"role": "deckwright", "conversation": 1, "text": "b"},
                {"role": "player", "conversation": 2, "text": "c"}, {"role": "deckwright", "conversation": 2, "text": "Lightning Helix"}]
    r = fake_run(messages, trace)
    seen = r.tool_results_before(checks.message_to_exchange(r, 3)).lower()
    assert "lightning helix" not in seen, "AC22 says 'earlier in that conversation'; conversation 1's lookup counted"


def test_c6_compares_basics_of_a_colour_with_no_pips():
    cache = {"Llanowar Elves": card("Llanowar Elves", "Creature — Elf Druid", "{G}", "G"),
             "Shock": card("Shock", "Instant", "{R}", "R")}
    cards = Counter({"Llanowar Elves": 10, "Shock": 10, "Forest": 14, "Mountain": 14, "Plains": 4})
    r = fake_run([], [])
    r.final_list = lambda: (cards, None)
    r.read = lambda: facts(format="standard")
    result = checks.check(r, cache)["C6"]
    assert result[0] == "fail", f"4 Plains in a deck with no white pips: {result}"


def test_c12_finds_a_plural_creature_type():
    cache = {"Llanowar Elves": card("Llanowar Elves", "Creature — Elf Druid", "{G}", "G")}
    r = fake_run([], [])
    f = facts(saved_categories=[{"name": "Elves", "target": 8}])
    result = checks.page_shape(r, f, "standard", Counter({"Llanowar Elves": 4}), cache)
    assert "creature-type" in result[1], f"an 'Elves' category passed AC10: {result}"


def test_c12_reads_the_creature_face_of_an_adventure():
    cache = {"Bonecrusher Giant // Stomp": card("Bonecrusher Giant // Stomp",
                                                "Creature — Giant // Instant — Adventure", "{2}{R} // {1}{R}", "R")}
    r = fake_run([], [])
    f = facts(saved_categories=[{"name": "Giant makers", "target": 4}])
    result = checks.page_shape(r, f, "standard", Counter({"Bonecrusher Giant // Stomp": 4}), cache)
    assert "creature-type" in result[1], f"'Giant' lost to the Adventure face's subtype: {result}"


def test_c12_excuses_only_the_starts_own_categories():
    cache = {"Ghalta, Primal Hunger": card("Ghalta, Primal Hunger", "Legendary Creature — Dinosaur", "{10}{G}{G}", "G")}
    r = fake_run([], [], start={"cards": [], "categories": [{"name": "Token makers", "target": 8}]})
    f = facts(saved_categories=[{"name": "Dinosaur payoffs", "target": 8}])
    result = checks.page_shape(r, f, "brawl", Counter({"Ghalta, Primal Hunger": 1}), cache)
    assert "creature-type" in result[1], f"a new 'Dinosaur payoffs' category is excused: {result}"


def test_c5_accepts_a_count_without_the_commander():
    cache = {"Vren, the Relentless": card("Vren, the Relentless", "Legendary Creature — Rat Rogue", "{2}{U}{B}", "UB"),
             "Rat Colony": card("Rat Colony", "Creature — Rat", "{1}{B}", "B")}
    r = fake_run([], [])
    r.final_list = lambda: (Counter({"Vren, the Relentless": 1, "Rat Colony": 10}), "Vren, the Relentless")
    for said in (10, 11):
        r.read = lambda: facts(review_type_counts=[{"message": 1, "card_type": "Creature", "count": said}])
        assert checks.check(r, cache)["C5"][0] == "pass", said


def test_final_list_keeps_a_count_of_zero():
    deck = {"cards": [{"name": "Sol Ring", "count": 0, "category": "Ramp"}]}
    r = fake_run([], [], deck=deck)
    cards, _ = checks.Run.final_list(r)
    assert cards["Sol Ring"] == 0, f"count 0 read as {cards['Sol Ring']}: C7 would fail on a card taken out"


def test_a_stand_in_failure_ends_the_run():
    import tempfile
    real = runner.deckwright_turn, runner.stand_in_turn
    runner.deckwright_turn = lambda *a: [{"type": "result", "result": "Which colours?", "total_cost_usd": 0.1}]
    runner.stand_in_turn = lambda *a: {"type": "result", "is_error": True, "result": "Error: rate limited"}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            brief = pathlib.Path(tmp) / "b.md"
            brief.write_text("## Opening\n\nHi\n\n## Player\n\nYou want a deck.\n")
            summary = runner.run(brief, "bare", pathlib.Path(tmp) / "out", 5)
            said = (pathlib.Path(tmp) / "out" / "conversation.jsonl").read_text()
    finally:
        runner.deckwright_turn, runner.stand_in_turn = real
    assert summary["ended"] == "stand-in error", summary
    assert "rate limited" not in said, "the stand-in's error reached Deckwright as the player's message"


def test_a_crashed_run_still_writes_run_json():
    import tempfile
    real = runner.deckwright_turn

    def crash(*a):
        raise TimeoutError
    runner.deckwright_turn = crash
    try:
        with tempfile.TemporaryDirectory() as tmp:
            brief = pathlib.Path(tmp) / "b.md"
            brief.write_text("## Opening\n\nHi\n\n## Player\n\nYou want a deck.\n")
            summary = runner.run(brief, "bare", pathlib.Path(tmp) / "out", 5)
            assert (pathlib.Path(tmp) / "out" / "run.json").exists()
    finally:
        runner.deckwright_turn = real
    assert summary["ended"] == "runner error: TimeoutError", summary


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("PASS", name)
            except Exception as e:
                failed += 1
                print("FAIL", name, "--", e if isinstance(e, AssertionError) else traceback.format_exc(limit=1))
    print(f"{failed} failed")
