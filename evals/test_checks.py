"""Tests for the checks and the runner that need no model and no Scryfall.

    python3 evals/test_checks.py
"""

from __future__ import annotations

import atexit
import itertools
import json
import os
import pathlib
import shutil
import socket
import sys
import tempfile
import traceback
import uuid
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import checks  # noqa: E402
import headless  # noqa: E402
import run as runner  # noqa: E402

FACT_NULL = {"holds": None, "evidence": ""}


def card(name, type_line, cost="", ci=(), fmt_legal=("brawl", "standard")):
    return {"name": name, "type_line": type_line, "mana_cost": cost, "color_identity": list(ci),
            "legalities": {f: "legal" for f in fmt_legal}, "on_arena": True}


READER_FACTS_ADDED = ["ladder_steps_with_counts", "suggestions_marked_with_reasons", "you_pick_takes_the_suggested",
                      "limits_question_names_crossover", "commander_before_colours", "set_count_says_any_printing",
                      "terms_explained_where_first_used", "name_asked_once_complete_before_handbook",
                      "handbook_written_unasked"]


def facts(**over):
    base = {"format": "brawl", "deck_colours": [], "offers": [], "confirmations": [], "basic_split_confirmed": True,
            "review_type_counts": [], "criterion_change_recorded_with_reason": None,
            "card_removed_without_player_word": [], "dismissed_finding_raised_again": None,
            "saved_categories": [], "deck_counts_stated": [],
            **{k: FACT_NULL for k in [*checks.EXTRA_FACTS, *READER_FACTS_ADDED]}}
    base.update(over)
    return base


def fact(holds, evidence=""):
    return {"holds": holds, "evidence": evidence}


# Stands for the run's workspace folder in a trace given to fake_run, which knows where it is.
WORKSPACE = "{workspace}"
_runs_root = []


def runs_root() -> pathlib.Path:
    if not _runs_root:
        _runs_root.append(pathlib.Path(tempfile.mkdtemp(prefix="deckwright-test-runs-")))
        atexit.register(shutil.rmtree, _runs_root[0], True)
    return _runs_root[0]


def fake_run(messages, trace, deck=None, start=None, brief="x", workspace=None):
    """A run folder on disk as run.py leaves it, read by checks.Run.

    `workspace` maps a path in the run's workspace to its content: a dict is saved as
    JSON, bytes as they are, anything else as text. `deck`, when given, is what the
    run's deck() returns whatever the workspace holds.
    """
    path = pathlib.Path(tempfile.mkdtemp(dir=runs_root()))
    ws = path / "workspace"
    ws.mkdir()
    (path / "run.json").write_text(json.dumps({"brief": brief, "start": "start" if start else None, "ends": None,
                                               "ended": "player ended", "exchanges": 1, "deckwright_cost_usd": 0}))
    (path / "conversation.jsonl").write_text("".join(json.dumps(m) + "\n" for m in messages))
    (path / "trace.jsonl").write_text("".join(json.dumps(e).replace(WORKSPACE, str(ws)) + "\n" for e in trace))
    for rel, content in (workspace or {}).items():
        target = ws / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(json.dumps(content, indent=2) if isinstance(content, dict) else content)
    if start:
        (path / "start").mkdir()
        (path / "start" / "deck.json").write_text(json.dumps(start))
    r = checks.Run(path)
    if deck is not None:
        r.deck = lambda: deck
    return r


_call_ids = itertools.count(1)


def tool_call(name, given, exchange=0, answer="ok", refused=False):
    """One tool call in a run's trace and the answer it got."""
    call_id = f"call{next(_call_ids)}"
    result = {"type": "tool_result", "tool_use_id": call_id, "content": answer}
    if refused:
        result["is_error"] = True
    return [{"exchange": exchange, "type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": call_id, "name": name, "input": given}]}},
            {"exchange": exchange, "type": "user", "message": {"content": [result]}}]


def write(rel, content, exchange=0, refused=False):
    text = content if isinstance(content, str) else json.dumps(content, indent=2)
    return tool_call("Write", {"file_path": f"{WORKSPACE}/{rel}", "content": text}, exchange,
                     answer=f"File created successfully at: {WORKSPACE}/{rel}", refused=refused)


def edit(rel, old, new, exchange=0):
    return tool_call("Edit", {"file_path": f"{WORKSPACE}/{rel}", "old_string": old, "new_string": new}, exchange)


def bash(command, exchange=0, answer=""):
    return tool_call("Bash", {"command": command}, exchange, answer=answer)


def publish(exchange, url=None, made="aaa", refused=False, code_link=False):
    """An Artifact publish of the deck folder; `url` names the artifact it updates, and `made` the one it answers with.

    The answer is the Artifact tool's as measured in the build thread on 2026-11-13;
    `code_link` answers with the claude.ai/code/artifact/<uuid> form instead.
    """
    page = f"{WORKSPACE}/brawl-rats/index.html"
    given = {"file_path": page, "files": {"deck.json": "deck.json"}}
    if url:
        given["url"] = url
    link = f"https://claude.ai/{'code/' if code_link else ''}artifact/{made}"
    version = 2 if url else 1
    answer = ("publish 429: daily publish limit for your plan reached (200)" if refused
              else f"Published {page} at {link} (Version {version}, version id v{version}-{made})")
    return tool_call("Artifact", given, exchange, answer=answer, refused=refused)


PACK = "python3 /plugins/deckwright/skills/deckwright/page/pack.py brawl-rats"
KNOWN = {"Wick, the Whorled Mind": card("Wick, the Whorled Mind", "Legendary Creature — Rat Warlock", "{1}{B}", "B"),
         "Rat Colony": card("Rat Colony", "Creature — Rat", "{1}{B}", "B"),
         "Infernal Grasp": card("Infernal Grasp", "Instant", "{1}{B}", "B"),
         "Feed the Swarm": card("Feed the Swarm", "Sorcery", "{1}{B}", "B"),
         "Swamp": card("Swamp", "Basic Land — Swamp", "", "B")}


def scryfall_id(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def deck_card(name, count=1, category="Token makers", layout="normal"):
    copy = {"mana_cost": "", "mana_value": 2, "type_line": "", "text": "", "rarity": "common", "taken": "2026-11-12"}
    if layout:
        copy["layout"] = layout
    return {"scryfall_id": scryfall_id(name), "name": name, "count": count, "category": category,
            "tags": [], "checked": True, "bends": None, "why": "Makes Rats.", "copy": copy}


def deck_json(cards=None, fmt="brawl", name=None, theme="Rats", **more):
    cards = cards if cards is not None else [deck_card("Wick, the Whorled Mind", category="Commander"),
                                             deck_card("Rat Colony")]
    deck = {"version": 2, "format": fmt, "criteria": [{"kind": "format", "text": "Brawl on Arena"},
                                                      {"kind": "theme", "text": theme}],
            "categories": [], "cards": cards, "maybeboard": [], "tokens": [], "approved": False, **more}
    if name:
        deck["name"] = name
    return deck


def complete_deck(name=None, **more):
    """A Brawl deck of 100 cards: the commander, 64 Rat Colony and 35 Swamps."""
    return deck_json([deck_card("Wick, the Whorled Mind", category="Commander"), deck_card("Rat Colony", 64),
                      deck_card("Swamp", 35, category="Lands")], name=name, **more)


def offered(name, suggested=False, **marks):
    c = {"scryfall_id": scryfall_id(name), "name": name, "reason": f"{name} does the job.",
         "copy": {"mana_cost": "{1}{B}", "type_line": "Instant", "text": ""}, **marks}
    if suggested:
        c["suggested"] = True
    return c


def group(heading, names, total=None, suggested=()):
    g = {"cards": [offered(n, n in suggested) for n in names]}
    if heading:
        g["heading"] = heading
    if total is not None:
        g["total"] = total
    return g


def offer(*groups, category="Removal"):
    return {"category": category, "groups": list(groups)}


def ladder(sizes=(4, 3, 3), totals=(6, 3, 40), suggested=("Rat 1",)):
    """A round with the three steps of the ladder for Rats."""
    headings = ["Rats that remove", "Cards that reward Rats and remove", "Other removal"]
    names = iter(f"Rat {n}" for n in range(1, 100))
    return offer(*[group(h, [next(names) for _ in range(size)], total, suggested)
                   for h, size, total in zip(headings, sizes, totals)])


def decks_in(run):
    """Every deck.json the run's workspace holds or its trace wrote."""
    texts = [text for rel, text in run.files.items() if rel.endswith("deck.json")]
    texts += [given.get("content", "") for _, _, name, given, _ in checks.tool_uses(run.trace)
              if name == "Write" and str(given.get("file_path", "")).endswith("deck.json")]
    found = []
    for text in texts:
        try:
            found.append(json.loads(text))
        except ValueError:
            pass
    return found


def cache_for(run, printings=None):
    """Card facts for every card the run names, so no check reaches Scryfall. A
    printing is kept under its API path, `/cards/<scryfall id>`; `printings` adds or
    replaces printings by Scryfall id."""
    cache = {}
    for deck in decks_in(run):
        groups = (deck.get("offer") or {}).get("groups") or []
        for c in [*deck.get("cards", []), *deck.get("maybeboard", []), *[c for g in groups for c in g["cards"]]]:
            cache[c["name"]] = KNOWN.get(c["name"]) or card(c["name"], "Creature — Rat", "{B}", "B")
            cache[f"/cards/{c['scryfall_id']}"] = {"id": c["scryfall_id"], "name": c["name"], "games": ["arena", "paper"],
                                                   "promo_types": []}
    for o in run.read()["offers"]:
        for name in o["cards"]:
            cache.setdefault(name, KNOWN.get(name) or card(name, "Creature — Rat", "{B}", "B"))
    for sid, printing in (printings or {}).items():
        cache[f"/cards/{sid}"] = printing
    return cache


def verdict(run, key, f=None, printings=None):
    """The check's (status, evidence) for `key`, with the reader's facts `f`."""
    f = f or facts()
    run.read = lambda: f
    results = checks.check(run, cache_for(run, printings))
    assert key in results, f"check() returns no {key}"
    return results[key]


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
             "Shock": card("Shock", "Instant", "{R}", "R"),
             "Forest": card("Forest", "Basic Land — Forest", "", "G"),
             "Mountain": card("Mountain", "Basic Land — Mountain", "", "R"),
             "Plains": card("Plains", "Basic Land — Plains", "", "W")}
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


def test_c10_leaves_the_ladder_to_s3():
    ladder_facts = ["type_shown_before_broader", "broader_count_stated_and_waited"]
    f = facts(**{name: fact(False, "Rats first; broadened unasked") for name in ladder_facts})
    status, evidence = verdict(fake_run([], []), "C10", f)
    assert status == "n/a", f"C10 still judges ADR-0006's ladder, which S3 now covers: {(status, evidence)}"
    asked = [name for name in ladder_facts if name in checks.READER_SCHEMA["properties"] or name in checks.READER_PROMPT]
    assert not asked, f"the reader is still asked for: {asked}"


def test_c5_accepts_a_count_without_the_commander():
    cache = {"Vren, the Relentless": card("Vren, the Relentless", "Legendary Creature — Rat Rogue", "{2}{U}{B}", "UB"),
             "Rat Colony": card("Rat Colony", "Creature — Rat", "{1}{B}", "B")}
    r = fake_run([], [])
    r.final_list = lambda: (Counter({"Vren, the Relentless": 1, "Rat Colony": 10}), "Vren, the Relentless")
    for said in (10, 11):
        r.read = lambda: facts(review_type_counts=[{"message": 1, "card_type": "Creature", "count": said}])
        assert checks.check(r, cache)["C5"][0] == "pass", said


def test_final_list_drops_a_card_at_count_zero():
    deck = {"cards": [{"name": "Sol Ring", "count": 0, "category": "Ramp"}]}
    r = fake_run([], [], deck=deck)
    cards, _ = checks.Run.final_list(r)
    assert "Sol Ring" not in cards, "a card at count 0 is still in the list: C1, C7 and C8 would read it"


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


def test_isolated_env_cuts_a_run_off_from_shared_memory():
    import os
    from unittest import mock
    shared = {"CLAUDE_MEMORY_STORES": '[{"path": "/v1/code/memory/shared"}]',
              "CLAUDE_COWORK_MEMORY_PATH_OVERRIDE": "/shared/memory"}
    with mock.patch.dict(os.environ, shared):
        env = headless.isolated_env(pathlib.Path("/runs/one/memory"))
    assert "CLAUDE_MEMORY_STORES" not in env, "the run can still reach the project's memory store"
    assert env["CLAUDE_COWORK_MEMORY_PATH_OVERRIDE"] == "/runs/one/memory", env["CLAUDE_COWORK_MEMORY_PATH_OVERRIDE"]


def test_every_turn_of_a_run_starts_from_its_own_empty_memory():
    import json
    import os
    import subprocess
    import tempfile
    from unittest import mock
    turns, found = [], []
    # The stand-in breaks the conversation off once, so Deckwright opens a second one.
    stand_in_says = [runner.NEW_CONVERSATION + "\nHi again", runner.END]
    shared = {"CLAUDE_MEMORY_STORES": '[{"path": "/v1/code/memory/shared"}]',
              "CLAUDE_COWORK_MEMORY_PATH_OVERRIDE": "/shared/memory"}

    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "out"

        class Turn:
            """Stands in for the process behind every subprocess call, however the runner makes it."""

            def __init__(self, args, env=None, **_):
                self.args, self.returncode = args, 0
                who = "stand-in" if "--system-prompt" in args else "deckwright"
                turns.append((who, env))
                self.said = stand_in_says.pop(0) if who == "stand-in" else "Which colours?"
                memory = pathlib.Path((env or {}).get("CLAUDE_COWORK_MEMORY_PATH_OVERRIDE", "/"))
                if out in memory.parents:
                    # The runner swallows an error raised in here, so what is found is kept for the end.
                    if "--session-id" in args and any(memory.iterdir()):
                        found.append(f"a new {who} conversation found memories in {memory}")
                    (memory / "remembered.md").write_text("the player's deck")

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def communicate(self, *_, **__):
                return json.dumps({"type": "result", "result": self.said}), ""

            def poll(self):
                return 0

        brief = pathlib.Path(tmp) / "b.md"
        brief.write_text("## Opening\n\nHi\n\n## Player\n\nYou want a deck.\n")
        with mock.patch.dict(os.environ, shared), mock.patch.object(subprocess, "Popen", Turn):
            summary = runner.run(brief, "bare", out, 5)
    for who, env in turns:
        assert env is not None, f"a {who} turn ran in the parent's environment, shared memory and all"
        assert "CLAUDE_MEMORY_STORES" not in env, f"a {who} turn can reach the project's memory store"
        memory = pathlib.Path(env["CLAUDE_COWORK_MEMORY_PATH_OVERRIDE"])
        assert out in memory.parents, f"a {who} turn keeps its memory outside the run, in {memory}"
    assert not found, found
    assert summary["ended"] == "player ended", summary
    assert [who for who, _ in turns] == ["deckwright", "stand-in"] * 2, turns


def play(deckwright_events, stand_in_says, **run_args):
    """Play one run offline: Deckwright's turns and the stand-in's replies come from the lists, in order."""
    import tempfile
    events, replies = iter(deckwright_events), iter(stand_in_says)
    real = runner.deckwright_turn, runner.stand_in_turn
    runner.deckwright_turn = lambda *a: next(events)
    runner.stand_in_turn = lambda *a: {"type": "result", "result": next(replies)}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            brief = pathlib.Path(tmp) / "b.md"
            brief.write_text("## Opening\n\nHi\n\n## Player\n\nYou want a deck.\n")
            return runner.run(brief, "bare", pathlib.Path(tmp) / "out", 20, **run_args)
    finally:
        runner.deckwright_turn, runner.stand_in_turn = real


def test_a_run_costs_the_last_total_of_each_conversation():
    # Claude Code reports a resumed session's whole running total on every turn.
    running_totals = [0.10, 0.25, 0.40, 0.05, 0.20]
    turns = [[{"type": "result", "result": "Next?", "total_cost_usd": total}] for total in running_totals]
    summary = play(turns, ["ok", "ok", runner.NEW_CONVERSATION + "\nHi again", "ok", runner.END])
    assert summary["exchanges"] == 5, summary
    assert summary["deckwright_cost_usd"] == 0.60, f"0.40 and 0.20 are what the two conversations cost: {summary}"


def artifact_call(call_id, refused=False, action="publish"):
    """One Deckwright turn's trace of an Artifact call and the answer it got."""
    answer = {"type": "tool_result", "tool_use_id": call_id, "content": "published"}
    if refused:
        answer |= {"is_error": True, "content": "publish 429: daily publish limit for your plan reached (200)"}
    return [{"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": call_id, "name": "Artifact", "input": {"file_path": "index.html", "action": action}}]}},
            {"type": "user", "message": {"content": [answer]}}]


def test_the_budget_counts_only_publishes_the_artifact_tool_accepted():
    budget = runner.PublishBudget(2)
    budget.count(artifact_call("t1") + artifact_call("t2", refused=True) + artifact_call("t3", action="read"))
    assert not budget.used_up(), "a refused publish or a read was counted against the budget"
    budget.count(artifact_call("t4"))
    assert budget.used_up(), "two accepted publishes did not use up a budget of two"
    assert 0 < runner.DEFAULT_PUBLISH_BUDGET < 200, "the default leaves the owner nothing of the day's 200 publishes"


def test_a_run_stops_once_the_round_has_published_its_budget():
    turns = [artifact_call(f"t{n}") + [{"type": "result", "result": "Saved. Next?"}] for n in range(6)]
    summary = play(turns, ["ok"] * 6, budget=runner.PublishBudget(2))
    assert summary["ended"] == "publish budget", summary
    assert summary["exchanges"] == 2, f"the run went on publishing past its budget: {summary}"


def test_a_round_out_of_budget_starts_no_more_runs():
    import tempfile
    budget = runner.PublishBudget(1)
    budget.count(artifact_call("t1"))
    real, started = runner.run, []
    runner.run = lambda brief, arm, out, *rest: started.append(out.name)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            round_dir = pathlib.Path(tmp) / "20261111T120000"
            summaries = list(runner.play_round([pathlib.Path(tmp) / "a.md"], "bare", 2, round_dir, 2, 5, budget))
            left = list(round_dir.glob("*"))
    finally:
        runner.run = real
    assert not started, started
    # No folder and no run.json: a later --resume takes these runs as never played.
    assert not left, left
    assert [s["ended"] for s in summaries] == ["not started: publish budget"] * 2, summaries


def test_a_round_out_of_budget_keeps_what_a_cut_off_run_left():
    import tempfile
    budget = runner.PublishBudget(1)
    budget.count(artifact_call("t1"))
    with tempfile.TemporaryDirectory() as tmp:
        cut_off = pathlib.Path(tmp) / "20261111T120000" / "a--bare--1"
        cut_off.mkdir(parents=True)
        (cut_off / "trace.jsonl").write_text("{}\n")
        list(runner.play_round([pathlib.Path(tmp) / "a.md"], "bare", 1, cut_off.parent, 2, 5, budget))
        assert (cut_off / "trace.jsonl").exists(), "the run was cleared though it could not be played again"


def test_a_resumed_round_plays_only_its_unfinished_runs():
    import json
    import tempfile
    real, played, leftovers = runner.run, [], []

    def fake_run(brief, arm, out, max_exchanges, budget):
        played.append(out.name)
        leftovers.extend(out.rglob("*"))
        out.mkdir(parents=True, exist_ok=True)
        (out / "run.json").write_text(json.dumps({"ended": "player ended"}))
        return {"brief": brief.stem, "arm": arm, "ended": "player ended"}
    runner.run = fake_run
    try:
        with tempfile.TemporaryDirectory() as tmp:
            round_dir = pathlib.Path(tmp) / "20261111T120000"
            finished, cut_off = round_dir / "a--bare--1", round_dir / "a--bare--2"
            (cut_off / "workspace").mkdir(parents=True)
            (cut_off / "trace.jsonl").write_text("{}\n")
            finished.mkdir()
            (finished / "run.json").write_text('{"ended": "turn cap"}')
            summaries = list(runner.play_round([pathlib.Path(tmp) / "a.md"], "bare", 3, round_dir, 2, 5,
                                               runner.PublishBudget(10)))
            kept = (finished / "run.json").read_text()
    finally:
        runner.run = real
    assert sorted(played) == ["a--bare--2", "a--bare--3"], f"played {played}"
    assert kept == '{"ended": "turn cap"}', "the finished run was played again"
    assert not leftovers, f"the cut-off run began on what its first try left behind: {leftovers}"
    assert len(summaries) == 2, summaries


def test_a_resumed_round_plays_a_run_the_budget_stopped_again():
    import tempfile
    real, played, leftovers = runner.run, [], []

    def fake_run(brief, arm, out, max_exchanges, budget):
        played.append(out.name)
        leftovers.extend(out.rglob("*"))
        return {"brief": brief.stem, "arm": arm, "ended": "player ended"}
    runner.run = fake_run
    try:
        with tempfile.TemporaryDirectory() as tmp:
            stopped = pathlib.Path(tmp) / "20261111T120000" / "a--bare--1"
            stopped.mkdir(parents=True)
            (stopped / "trace.jsonl").write_text("{}\n")
            (stopped / "run.json").write_text('{"ended": "publish budget"}')
            list(runner.play_round([pathlib.Path(tmp) / "a.md"], "bare", 1, stopped.parent, 2, 5, runner.PublishBudget(10)))
    finally:
        runner.run = real
    assert played == ["a--bare--1"], "a run the budget stopped short was taken as finished"
    assert not leftovers, f"the run began on what its first try left behind: {leftovers}"


def test_resume_continues_in_the_rounds_own_folder():
    import tempfile
    from unittest import mock
    real = runner.RUNS_DIR, runner.play_round
    rounds = []
    runner.play_round = lambda briefs, arm, runs, round_dir, *rest: rounds.append((arm, runs, round_dir)) or []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            runner.RUNS_DIR = pathlib.Path(tmp)
            (runner.RUNS_DIR / "20261111T120000").mkdir()
            with mock.patch.object(sys, "argv", ["run.py", "a.md", "--arm", "skill", "--runs", "2",
                                                 "--resume", "20261111T120000"]):
                runner.main()
            with mock.patch.object(sys, "argv", ["run.py", "a.md", "--arm", "skill", "--resume", "20250101T000000"]), \
                    mock.patch.object(sys, "stderr"):
                try:
                    runner.main()
                    unknown = "played"
                except SystemExit:
                    unknown = "refused"
            assert rounds == [("skill", 2, runner.RUNS_DIR / "20261111T120000")], rounds
            assert unknown == "refused", "resuming a round that does not exist started a new one under its name"
    finally:
        runner.RUNS_DIR, runner.play_round = real


def test_the_reader_and_the_judge_start_claude_cut_off_from_shared_memory():
    import json
    import os
    import subprocess
    import tempfile
    from unittest import mock
    import judge
    starts = []

    class Claude:
        """Stands in for the process behind every subprocess call."""

        def __init__(self, args, env=None, **_):
            self.args, self.returncode = args, 0
            starts.append(env)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def communicate(self, *_, **__):
            return json.dumps({"structured_output": facts()}), ""

        def poll(self):
            return 0

    shared = {"CLAUDE_MEMORY_STORES": '[{"path": "/v1/code/memory/shared"}]',
              "CLAUDE_COWORK_MEMORY_PATH_OVERRIDE": "/shared/memory"}
    with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, shared), \
            mock.patch.object(subprocess, "Popen", Claude):
        r = fake_run([{"role": "player", "text": "hi"}], [])
        r.path = pathlib.Path(tmp)
        checks.Run.read(r)
        judge.ask("one conversation", "another")
    assert len(starts) == 2, starts
    for who, env in zip(("reader", "judge"), starts):
        assert env is not None, f"the {who} ran in the parent's environment, shared memory and all"
        assert "CLAUDE_MEMORY_STORES" not in env, f"the {who} can reach the project's memory store"
        assert env.get("CLAUDE_COWORK_MEMORY_PATH_OVERRIDE") not in (None, "/shared/memory"), \
            f"the {who} was shown the project's memory folder"


def test_starts_on_the_same_day_share_one_publish_budget():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        ledger = pathlib.Path(tmp) / "publishes"
        ledger.mkdir()
        (ledger / "2020-01-01").write_text("publish\n" * 5)
        one_round, beside_it = runner.PublishBudget(2, ledger), runner.PublishBudget(2, ledger)
        assert not one_round.used_up(), "another day's publishes were counted against today's budget"
        one_round.count(artifact_call("t1"))
        beside_it.count(artifact_call("t2"))
        assert one_round.used_up() and beside_it.used_up(), "two rounds side by side each kept a budget of their own"
        assert runner.PublishBudget(2, ledger).used_up(), "a start later the same day began a new count"


def test_every_start_of_the_runner_counts_against_the_days_budget():
    import tempfile
    from unittest import mock
    real = runner.RUNS_DIR, runner.play_round
    budgets = []
    runner.play_round = lambda *args: budgets.append(args[-1]) or []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            runner.RUNS_DIR = pathlib.Path(tmp)
            for _ in range(2):
                with mock.patch.object(sys, "argv", ["run.py", "a.md", "--arm", "bare", "--publish-budget", "1"]):
                    runner.main()
            budgets[0].count(artifact_call("t1"))
            assert budgets[1].used_up(), "a second start of run.py did not see the first one's publish"
    finally:
        runner.RUNS_DIR, runner.play_round = real


def test_the_tests_exit_non_zero_when_one_fails_and_zero_when_none_do():
    import contextlib
    import io

    def fails():
        raise AssertionError("a stand-in failure")

    with contextlib.redirect_stdout(io.StringIO()):
        one_fails = run_tests({"test_passes": lambda: None, "test_fails": fails})
        none_fail = run_tests({"test_passes": lambda: None})
    with contextlib.redirect_stdout(io.StringIO()) as printed:
        none_run = run_tests({})
    assert one_fails == 1, f"a failing test left the exit status at {one_fails}, so CI goes green"
    assert none_fail == 0, f"every test passed and the exit status is {none_fail}"
    assert none_run == 1, f"no test ran and the exit status is {none_run}, so CI goes green on nothing"
    said = printed.getvalue()
    assert "no tests found" in said, f"a run with no tests does not say so: {said!r}"
    assert "0 failed" in said.splitlines(), f"a run with no tests prints no tally: {said!r}"


def test_a_test_that_exits_does_not_end_the_run():
    import contextlib
    import io

    def exits():
        sys.exit(0)

    with contextlib.redirect_stdout(io.StringIO()) as printed:
        try:
            status = run_tests({"test_exits": exits, "test_passes": lambda: None})
        except SystemExit as e:
            status = f"SystemExit({e.code}) out of run_tests"
    said = printed.getvalue().splitlines()
    assert status != "SystemExit(0) out of run_tests", \
        "a test calling sys.exit(0) ended the run, so CI goes green on the tests it never ran"
    assert status == 1, f"a test called sys.exit(0) and the exit status is {status}"
    assert any(line.startswith("FAIL test_exits") for line in said), f"the exiting test is not reported as failed: {said}"
    assert "PASS test_passes" in said, f"the test after the exiting one never ran: {said}"


def test_the_tests_cannot_reach_scryfall():
    import time
    began = time.monotonic()
    try:
        checks.scryfall_get("/cards/named?exact=Forest", 0)
    except Exception as e:
        error = e
    else:
        error = None
    took = time.monotonic() - began
    assert error is not None, "a test reached Scryfall"
    assert "api.scryfall.com" in str(error), f"the blocked request's error does not name the host: {error!r}"
    assert took < 2, f"the blocked request took {took:.1f}s, so scryfall_get retried it as a network error"


def test_the_workflow_never_starts_claude():
    workflow = pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows" / "tests.yml"
    assert workflow.is_file(), f"no workflow at {workflow}"
    import re
    text = workflow.read_text()
    assert not re.search(r"\bsecrets\b", text), "the workflow reads a secret, so it can hold a key that starts Claude"
    assert "claude" not in text.lower(), "the workflow names Claude"


def test_p14_every_saved_start_carries_every_copy_field_the_example_carries():
    # A start saved without a field the page reads draws the deck otherwise than a real build.
    import json
    repo = pathlib.Path(__file__).resolve().parent.parent
    example = json.loads((repo / "plugins/deckwright/skills/deckwright/page/deck.example.json").read_text())
    fields = set.intersection(*(set(c["copy"]) for c in example["cards"]))
    starts = sorted((repo / "evals" / "starts").glob("*/deck.json"))
    assert starts, "no saved start was found, so this test proves nothing"
    lacking = {}
    for start in starts:
        for c in json.loads(start.read_text())["cards"]:
            missing = fields - set(c.get("copy", {}))
            if missing:
                lacking.setdefault(start.parent.name, set()).update(missing)
    assert not lacking, "saved starts lack copy fields every example card carries: " + "; ".join(
        f"{name} lacks {', '.join(sorted(missing))}" for name, missing in sorted(lacking.items()))


# ---------- the deck kept as a folder in the workspace ----------

LEDGER_LINE = "- 2026-11-12 · in · Rat Colony · Makes a Rat every turn."
PICKED = [{"role": "player", "text": "I'll take Rat Colony"}, {"role": "deckwright", "text": "Rat Colony is in. Removal next?"}]


def saved_pick(exchange=0, deck=None, ledger=True):
    """The writes that save one pick to the folder brawl-rats."""
    saved = write("brawl-rats/deck.json", deck or deck_json(), exchange)
    if ledger:
        saved += edit("brawl-rats/LEDGER.md", "# Ledger\n", f"# Ledger\n{LEDGER_LINE}\n", exchange)
    return saved


def deck_folder(deck=None, folder="brawl-rats", **more):
    return {f"{folder}/deck.json": deck or deck_json(), f"{folder}/LEDGER.md": f"# Ledger\n{LEDGER_LINE}\n", **more}


def test_final_list_reads_the_deck_from_the_workspace_when_nothing_was_published():
    r = fake_run([], [], workspace=deck_folder())
    cards, commander = r.final_list()
    assert cards == Counter({"Wick, the Whorled Mind": 1, "Rat Colony": 1}), f"the workspace's deck.json was not read: {cards}"
    assert commander == "Wick, the Whorled Mind", commander


def test_final_list_reads_the_deck_folder_the_run_last_wrote():
    other = deck_json([deck_card("Infernal Grasp")], name="Another deck")
    r = fake_run([], write("brawl-rats-2/deck.json", deck_json()),
                 workspace={**deck_folder(other), **deck_folder(folder="brawl-rats-2")})
    cards, _ = r.final_list()
    assert "Rat Colony" in cards and "Infernal Grasp" not in cards, f"read the folder the run did not write: {cards}"


def test_c8_passes_a_complete_deck_kept_only_in_the_workspace():
    r = fake_run([], [], workspace=deck_folder(complete_deck()))
    status, evidence = verdict(r, "C8")
    assert status == "pass", f"a 100-card deck in the workspace, never published: {evidence}"


def test_c12_finds_the_page_in_the_workspace_folder_without_a_publish():
    sid = scryfall_id("Rat Colony")
    r = fake_run([], [], workspace=deck_folder(complete_deck(), **{"brawl-rats/index.html": "<title>Deck</title>",
                                                                   f"brawl-rats/cards/{sid}.jpg": b"\xff\xd8\xff"}))
    _, evidence = verdict(r, "C12")
    missing = [part for part in ("no page", "no deck.json", "no LEDGER.md", "no card images") if part in evidence]
    assert not missing, f"the folder holds the page and C12 says it is missing: {evidence}"


def test_a_save_is_a_write_to_deck_json_not_a_publish():
    trace = (write("brawl-rats/deck.json", deck_json(), 0)
             + publish(1)
             + edit("brawl-rats/deck.json", '"approved": false', '"approved": true', 2)
             + bash("cat brawl-rats/deck.json", 3)
             + bash("python3 - <<'EOF'\nimport json\nd = json.load(open('brawl-rats/deck.json'))\n"
                    "d['cards'].pop()\njson.dump(d, open('brawl-rats/deck.json', 'w'))\nEOF", 4)
             + write("brawl-rats/deck.json", deck_json(), 5, refused=True)
             + write("brawl-rats/notes.json", {"note": "x"}, 6))
    r = fake_run([], trace, workspace=deck_folder())
    saves = r.saves_by_exchange()
    counted = {e for e in range(7) if saves.get(e)}
    assert counted == {0, 2, 4}, (f"saves counted in exchanges {sorted(counted)}; a save is a Write, an Edit or a script "
                                  "that changes deck.json (0, 2, 4), not a publish, a read, a refused write or another file")


def test_c4_counts_a_pick_saved_to_disk_without_a_publish():
    r = fake_run(PICKED, saved_pick(), workspace=deck_folder())
    status, evidence = verdict(r, "C4", facts(confirmations=[{"message": 0, "cards": ["Rat Colony"]}]))
    assert status == "pass", f"the pick was written to deck.json in its exchange: {evidence}"


def test_a_count_printed_with_stdout_write_is_not_a_save():
    script = ("python3 -c \"import json,sys; d=json.load(open('brawl-rats/deck.json')); "
              "sys.stdout.write(str(len(d['cards'])))\"")
    r = fake_run(PICKED, bash(script, 0, answer="2"), workspace=deck_folder())
    saves = r.saves_by_exchange()
    assert not saves.get(0), f"a count that only reads deck.json was taken as a save of it: {dict(saves)}"


def test_a_script_that_reads_deck_json_and_writes_only_the_ledger_does_not_save_deck_json():
    script = ("python3 -c \"import json; d=json.load(open('brawl-rats/deck.json')); "
              "open('brawl-rats/LEDGER.md','a').write('- in Rat Colony ' + d['cards'][1]['scryfall_id'])\"")
    r = fake_run(PICKED, bash(script, 0), workspace=deck_folder())
    status, evidence = verdict(r, "C4", facts(**PICK_FACTS))
    assert status == "fail", f"deck.json was only read, and C4 says the pick was saved: {(status, evidence)}"


def test_a_card_whose_count_is_not_a_number_counts_as_zero():
    deck = complete_deck()
    deck["cards"] += [{**deck_card("Infernal Grasp"), "count": None}, {**deck_card("Feed the Swarm"), "count": "two"}]
    r = fake_run([], [], workspace=deck_folder(deck))
    try:
        status, evidence = verdict(r, "S11")
    except Exception as e:
        raise AssertionError(f"one card with a count that is not a number stops the checks of every run: {e!r}")
    assert status != "n/a", f"100 cards and two counted as zero is a complete deck: {(status, evidence)}"


def test_deck_folder_breaks_a_tie_on_modification_time_by_name():
    # Made in an order whose listing does not put the folder that sorts last first, either in
    # ext4's hashed order or in tmpfs's newest first.
    folders = ["brawl-tokens", "brawl-elves", "brawl-rats", "brawl-angels"]
    r = fake_run([], [], workspace={rel: text for folder in folders for rel, text in deck_folder(folder=folder).items()})
    for folder in folders:
        os.utime(r.path / "workspace" / folder / "deck.json", (1_700_000_000, 1_700_000_000))
    chosen = checks.Run(r.path).folder.name
    assert chosen == "brawl-tokens", f"four decks saved in the same instant, and the listing's order chose {chosen}"


# ---------- S1: a save writes the folder; a publish only on asking for a link ----------

PICK_FACTS = {"confirmations": [{"message": 0, "cards": ["Rat Colony"]}]}


def test_s1_passes_a_pick_written_to_deck_json_and_ledger_with_no_publish():
    r = fake_run(PICKED, saved_pick(), workspace=deck_folder())
    status, evidence = verdict(r, "S1", facts(**PICK_FACTS))
    assert status == "pass", evidence


def test_s1_fails_a_publish_the_player_never_asked_for():
    r = fake_run(PICKED, saved_pick() + publish(0), workspace=deck_folder())
    status, evidence = verdict(r, "S1", facts(**PICK_FACTS))
    assert status == "fail", f"published with no link asked for: {(status, evidence)}"
    assert "publish" in evidence.lower(), f"the evidence does not name the publish: {evidence}"


def test_s1_fails_a_pick_that_was_only_published():
    r = fake_run(PICKED, publish(0), workspace=deck_folder())
    status, evidence = verdict(r, "S1", facts(**PICK_FACTS))
    assert status == "fail", f"the pick never reached deck.json: {(status, evidence)}"
    assert "Rat Colony" in evidence or "deck.json" in evidence, f"the evidence does not name the unsaved pick: {evidence}"


def test_s1_fails_a_pick_written_to_deck_json_but_not_to_the_ledger():
    r = fake_run(PICKED, saved_pick(ledger=False), workspace=deck_folder())
    status, evidence = verdict(r, "S1", facts(**PICK_FACTS))
    assert status == "fail", f"the pick has no ledger line: {(status, evidence)}"
    assert "LEDGER.md" in evidence, f"the evidence does not name the ledger: {evidence}"


LINK_ASKED = PICKED + [{"role": "player", "text": "Can I have a link to the deck?"},
                       {"role": "deckwright", "text": "Here it is: https://claude.ai/artifact/aaa"},
                       {"role": "player", "text": "Add Infernal Grasp, and update the link"},
                       {"role": "deckwright", "text": "Infernal Grasp is in; the same link shows it."}]
LINK_FACTS = {"confirmations": [{"message": 0, "cards": ["Rat Colony"]}, {"message": 4, "cards": ["Infernal Grasp"]}]}


def test_s1_passes_publishes_to_one_artifact_once_the_player_asks_for_a_link():
    trace = saved_pick(0) + publish(1, made="aaa") + saved_pick(2) + publish(2, url="https://claude.ai/artifact/aaa")
    r = fake_run(LINK_ASKED, trace, workspace=deck_folder())
    status, evidence = verdict(r, "S1", facts(**LINK_FACTS))
    assert status == "pass", evidence


def test_s1_passes_a_refused_publish_when_the_build_goes_on():
    trace = saved_pick(0) + publish(1, refused=True) + saved_pick(2)
    r = fake_run(LINK_ASKED, trace, workspace=deck_folder())
    status, evidence = verdict(r, "S1", facts(**LINK_FACTS))
    assert status == "pass", f"the publish failed and the next pick was saved: {evidence}"


def test_s1_fails_a_second_artifact_for_the_same_deck():
    trace = (saved_pick(0) + publish(1, made="aaa", code_link=True)
             + saved_pick(2) + publish(2, made="bbb", code_link=True))
    r = fake_run(LINK_ASKED, trace, workspace=deck_folder())
    status, evidence = verdict(r, "S1", facts(**LINK_FACTS))
    assert status == "fail", f"the deck went to two artifacts: {(status, evidence)}"
    assert "bbb" in evidence, f"the evidence does not name the second artifact: {evidence}"


# ---------- S2: a round is shown as the packed file ----------

ROUND = [{"role": "player", "text": "Removal next"},
         {"role": "deckwright", "text": "Two removal spells are on offer; open brawl-rats.html to see them: "
                                        "1 Infernal Grasp, 2 Feed the Swarm."}]
ROUND_FACTS = {"offers": [{"message": 1, "cards": ["Infernal Grasp", "Feed the Swarm"]}]}
ON_OFFER = deck_json(offer=offer(group(None, ["Infernal Grasp", "Feed the Swarm"])))


def shown_round(reply=None, written=ON_OFFER, packed=True, more_calls=()):
    """The round of ROUND in a run; `written` is the deck.json its exchange writes, or a command that writes it."""
    messages = [ROUND[0], {**ROUND[1], "text": reply or ROUND[1]["text"]}]
    trace = bash(written, 0) if isinstance(written, str) else write("brawl-rats/deck.json", written, 0)
    if packed:
        trace += bash(PACK, 0, answer=f"{WORKSPACE}/brawl-rats.html")
    trace += list(more_calls)
    return fake_run(messages, trace, workspace=deck_folder(ON_OFFER, **{"brawl-rats.html": "<html></html>"}))


def test_s2_passes_a_round_written_as_offer_packed_and_named():
    status, evidence = verdict(shown_round(), "S2", facts(**ROUND_FACTS))
    assert status == "pass", evidence


def test_s2_fails_a_round_never_packed():
    status, evidence = verdict(shown_round(packed=False), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"pack.py never ran for the round: {(status, evidence)}"
    assert "pack.py" in evidence, f"the evidence does not name pack.py: {evidence}"


def test_s2_fails_a_round_not_written_to_deck_json_as_offer():
    status, evidence = verdict(shown_round(written=deck_json()), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"deck.json held no offer for the round: {(status, evidence)}"
    assert "offer" in evidence, f"the evidence does not name the missing offer: {evidence}"


def test_s2_fails_a_round_whose_reply_does_not_name_the_packed_file():
    reply = "Two removal spells: 1 Infernal Grasp, 2 Feed the Swarm."
    status, evidence = verdict(shown_round(reply), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"the player was never given the packed file: {(status, evidence)}"
    assert "brawl-rats.html" in evidence or "packed" in evidence, f"the evidence does not name the packed file: {evidence}"


def test_s2_fails_a_card_name_linked_to_scryfall():
    reply = ("On offer in brawl-rats.html: 1 [Infernal Grasp](https://scryfall.com/card/2xm/107/infernal-grasp), "
             "2 Feed the Swarm.")
    status, evidence = verdict(shown_round(reply), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"a card name links to Scryfall (#29): {(status, evidence)}"
    assert "scryfall.com" in evidence, f"the evidence does not name the link: {evidence}"


def test_s2_fails_a_card_picture_shown_alone():
    sid = scryfall_id("Infernal Grasp")
    reply = f"On offer in brawl-rats.html: 1 Infernal Grasp ![Infernal Grasp](brawl-rats/cards/{sid}.jpg), 2 Feed the Swarm."
    status, evidence = verdict(shown_round(reply), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"a card picture went to the chat alone (#29): {(status, evidence)}"
    assert f"{sid}.jpg" in evidence or "Infernal Grasp" in evidence, f"the evidence does not name the picture: {evidence}"


def test_s2_fails_a_card_picture_in_an_img_tag():
    sid = scryfall_id("Infernal Grasp")
    reply = f'On offer in brawl-rats.html: 1 Infernal Grasp <img src="brawl-rats/cards/{sid}.jpg">, 2 Feed the Swarm.'
    status, evidence = verdict(shown_round(reply), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"a card picture went to the chat as an <img>: {(status, evidence)}"
    assert f"{sid}.jpg" in evidence, f"the evidence does not name the picture: {evidence}"


def test_s2_fails_any_scryfall_url_in_a_reply():
    urls = ["https://api.scryfall.com/cards/named?exact=Infernal%20Grasp", "api.scryfall.com/cards/2xm/107",
            "https://scryfall.com/search?q=infernal+grasp", "https://svgs.scryfall.io/card-symbols/B.svg"]
    passed = []
    for url in urls:
        reply = f"On offer in brawl-rats.html: 1 Infernal Grasp ({url}), 2 Feed the Swarm."
        status, evidence = verdict(shown_round(reply), "S2", facts(**ROUND_FACTS))
        if status != "fail" or url not in evidence:
            passed.append((url, status))
    assert not passed, f"Scryfall URLs in a reply that S2 does not fail on by name: {passed}"


def test_s2_fails_a_write_that_removes_the_offer():
    passed = []
    for removal in ("d.pop('offer', None)", "del d['offer']"):
        script = (f"python3 -c \"import json; d=json.load(open('brawl-rats/deck.json')); {removal}; "
                  "json.dump(d, open('brawl-rats/deck.json','w'))\"")
        status, evidence = verdict(shown_round(written=script), "S2", facts(**ROUND_FACTS))
        if status != "fail" or "offer" not in evidence:
            passed.append((removal, status))
    assert not passed, f"a write that removes the offer counts as putting the round on offer: {passed}"


def test_s2_leaves_a_file_sent_into_chat_to_the_runner_which_disallows_it():
    sent = tool_call("SendUserFile", {"files": [f"{WORKSPACE}/brawl-rats/cards/{scryfall_id('Infernal Grasp')}.jpg"]})
    assert "SendUserFile" in runner.DECKWRIGHT_DISALLOWED, "the runner lets Deckwright send a file into the chat"
    status, evidence = verdict(shown_round(more_calls=sent), "S2", facts(**ROUND_FACTS))
    assert status == "pass", f"S2 still judges a SendUserFile call, which no run can make: {(status, evidence)}"


# ---------- S3: a round shows every step of the ladder ----------

def ladder_round(offer_now, holds=True, evidence="Rats that remove (6), Cards that reward Rats (3), Other removal (40)"):
    deck = deck_json(offer=offer_now) if offer_now else deck_json()
    return fake_run([], [], workspace=deck_folder(deck)), facts(ladder_steps_with_counts=fact(holds, evidence))


def test_s3_passes_a_round_of_three_steps_with_headings_and_counts():
    r, f = ladder_round(ladder())
    status, evidence = verdict(r, "S3", f)
    assert status == "pass", evidence


def test_s3_fails_a_round_of_the_creature_type_alone():
    # The first real build: eight Rats for eight places, and the wider steps never shown (#40).
    r, f = ladder_round(None, holds=False, evidence="Token makers: eight Rats, nothing wider")
    status, evidence = verdict(r, "S3", f)
    assert status == "fail", (status, evidence)
    assert "eight Rats" in evidence, f"the evidence does not quote the round: {evidence}"


def test_s3_fails_a_saved_ladder_with_a_step_missing():
    r, f = ladder_round(ladder(sizes=(5, 5), totals=(6, 3)))
    status, evidence = verdict(r, "S3", f)
    assert status == "fail", f"a ladder of two steps on offer: {(status, evidence)}"
    assert "2" in evidence and "Removal" in evidence, f"the evidence does not name the round or its steps: {evidence}"


def test_s3_fails_a_saved_step_without_its_full_count():
    r, f = ladder_round(ladder(totals=(6, None, 40)))
    status, evidence = verdict(r, "S3", f)
    assert status == "fail", f"a step on offer states no total: {(status, evidence)}"
    assert "Cards that reward Rats and remove" in evidence, f"the evidence does not name the step: {evidence}"


def test_s3_fails_a_saved_round_far_from_about_ten_cards():
    r, f = ladder_round(ladder(sizes=(5, 5, 5)))
    status, evidence = verdict(r, "S3", f)
    assert status == "fail", f"15 cards on offer in one round: {(status, evidence)}"
    assert "15" in evidence, f"the evidence does not give the round's size: {evidence}"


def test_s3_is_not_applicable_without_a_creature_type():
    r, f = ladder_round(offer(group(None, ["Infernal Grasp", "Feed the Swarm"])), holds=None, evidence="")
    status, evidence = verdict(r, "S3", f)
    assert status == "n/a", f"no creature type among the criteria: {(status, evidence)}"


def test_s3_passes_a_further_round_of_one_step_with_its_heading_and_count():
    said = "three steps in the first round; then more Rats that remove on the player's word"
    one_step = offer(group("Rats that remove", [f"Rat {n}" for n in range(1, 6)], total=14, suggested=("Rat 1",)))
    r, f = ladder_round(one_step, evidence=said)
    status, evidence = verdict(r, "S3", f)
    assert status == "pass", f"a further round of one step, shown on the player's word: {evidence}"
    r, f = ladder_round(offer(group("Rats that remove", [f"Rat {n}" for n in range(1, 6)])), evidence=said)
    status, evidence = verdict(r, "S3", f)
    assert status == "fail", f"a round of one step must still state its full count: {(status, evidence)}"


ASHCOAT = "Ashcoat of the Shadow Swarm"
OFFERED_THEN_REMOVED = [{"role": "player", "text": "Payoffs next"},
                        {"role": "deckwright", "text": f"On offer in brawl-rats.html: 1 {ASHCOAT}."}]


def offer_written_by_a_script_then_removed():
    """A run whose round went to deck.json by a script and was removed once decided, so no
    whole deck.json with the offer is ever seen."""
    unmarked = offer(group(None, [ASHCOAT]), category="Payoffs")
    script = ("import json\nd = json.load(open('brawl-rats/deck.json'))\n"
              f"d['offer'] = {unmarked!r}\njson.dump(d, open('brawl-rats/deck.json', 'w'))\n")
    trace = (write("save_offer.py", script, 0) + bash(f"python3 {WORKSPACE}/save_offer.py", 0)
             + bash(PACK, 0, answer=f"{WORKSPACE}/brawl-rats.html"))
    return fake_run(OFFERED_THEN_REMOVED, trace, workspace=deck_folder())


SEEN_BY_THE_READER = {"offers": [{"message": 1, "cards": [ASHCOAT]}]}


def test_s3_cannot_tell_a_ladder_no_offer_shows():
    f = facts(**SEEN_BY_THE_READER, ladder_steps_with_counts=fact(True, "three steps, each with its count"))
    status, evidence = verdict(offer_written_by_a_script_then_removed(), "S3", f)
    assert (status, "cannot tell" in evidence) == ("n/a", True), \
        f"S3 judges the saved ladder though no offered card could be read: {(status, evidence)}"


# ---------- S4: a round marks the tutor's picks ----------

def marked_round_facts(marked=True, taken=True):
    return facts(suggestions_marked_with_reasons=fact(marked, "Suggested: 1 and 3, because they answer flyers"),
                 you_pick_takes_the_suggested=fact(taken, "Player: you pick. Tutor: taking 1 and 3"))


def test_s4_passes_marked_suggestions_taken_on_you_pick():
    r = fake_run([], [], workspace=deck_folder(deck_json(offer=ladder())))
    status, evidence = verdict(r, "S4", marked_round_facts())
    assert status == "pass", evidence


def test_s4_fails_you_pick_answered_with_a_new_suggestion():
    # The first real build: "go with your suggestion", answered "I hadn't given a suggestion for this one yet" (#41).
    f = facts(suggestions_marked_with_reasons=fact(True, "Suggested: 1 and 3"),
              you_pick_takes_the_suggested=fact(False, "I hadn't given a suggestion for this one yet, so here it is."))
    r = fake_run([], [], workspace=deck_folder(deck_json(offer=ladder())))
    status, evidence = verdict(r, "S4", f)
    assert status == "fail", (status, evidence)
    assert "hadn't given a suggestion" in evidence, f"the evidence does not quote the reply: {evidence}"


def test_s4_fails_a_saved_round_with_no_suggested_card():
    deck = deck_json(offer=ladder(suggested=()), categories=[{"name": "Removal", "target": 8}])
    r = fake_run([], [], workspace=deck_folder(deck))
    status, evidence = verdict(r, "S4", marked_round_facts())
    assert status == "fail", f"the round on offer marks no card suggested: {(status, evidence)}"
    assert "Removal" in evidence, f"the evidence does not name the round: {evidence}"


def test_s4_is_not_applicable_when_no_round_was_asked_for():
    r = fake_run([], [], workspace=deck_folder())
    status, evidence = verdict(r, "S4", facts())
    assert status == "n/a", (status, evidence)


def test_s4_asks_no_suggested_mark_of_a_commander_offer():
    commanders = offer(group(None, ["Wick, the Whorled Mind", "Marrow-Gnawer"]), category="Commander")
    r = fake_run([], [], workspace=deck_folder(deck_json(offer=commanders)))
    status, evidence = verdict(r, "S4", facts())
    assert status != "fail", f"a commander offer is not a category's round, and fails S4 for marking none: {evidence}"


def test_s4_cannot_tell_marks_no_offer_shows():
    f = facts(**SEEN_BY_THE_READER, suggestions_marked_with_reasons=fact(True, "Suggested: 1"))
    status, evidence = verdict(offer_written_by_a_script_then_removed(), "S4", f)
    assert (status, "cannot tell" in evidence) == ("n/a", True), \
        f"S4 judges the saved marks though no offered card could be read: {(status, evidence)}"


# ---------- S5: crossover printings are marked and named as printed ----------

def crossover_printing(name, flavor_name=None, faces=None):
    printing = {"id": scryfall_id(name), "name": name, "games": ["arena"], "promo_types": ["universesbeyond"]}
    if flavor_name:
        printing["flavor_name"] = flavor_name
    if faces:
        printing["card_faces"] = faces
    return printing


def crossover_round(*marked, holds=True, said="Any limits, for example sets, or crossover cards?"):
    deck = deck_json(offer=offer(group(None, ["Infernal Grasp"]), category="Payoffs"))
    deck["offer"]["groups"][0]["cards"] += marked
    r = fake_run([], [], workspace=deck_folder(deck))
    return r, facts(limits_question_names_crossover=fact(holds, said))


def test_s5_passes_a_crossover_printing_marked_with_its_printed_name():
    r, f = crossover_round(offered(ASHCOAT, crossover=True, printed_name="Splinter of the Shadows"))
    status, evidence = verdict(r, "S5", f, {scryfall_id(ASHCOAT): crossover_printing(ASHCOAT, "Splinter of the Shadows")})
    assert status == "pass", evidence


def test_s5_passes_a_two_faced_crossover_named_by_its_first_face():
    name = "Rat Front // Rat Back"
    printing = crossover_printing(name, faces=[{"name": "Rat Front", "flavor_name": "Shredder's Rat"}, {"name": "Rat Back"}])
    r, f = crossover_round(offered(name, crossover=True, printed_name="Shredder's Rat"))
    status, evidence = verdict(r, "S5", f, {scryfall_id(name): printing})
    assert status == "pass", f"a two-faced card's printed name is on its first face: {evidence}"


def test_s5_fails_a_crossover_printing_offered_unmarked():
    # The first real build: Ashcoat was shown as Splinter of the Shadows, unmarked (#42).
    r, f = crossover_round(offered(ASHCOAT))
    status, evidence = verdict(r, "S5", f, {scryfall_id(ASHCOAT): crossover_printing(ASHCOAT, "Splinter of the Shadows")})
    assert status == "fail", (status, evidence)
    assert ASHCOAT in evidence, f"the evidence does not name the card: {evidence}"


def test_s5_fails_a_printed_name_that_is_not_the_printings_flavor_name():
    r, f = crossover_round(offered(ASHCOAT, crossover=True, printed_name=ASHCOAT))
    status, evidence = verdict(r, "S5", f, {scryfall_id(ASHCOAT): crossover_printing(ASHCOAT, "Splinter of the Shadows")})
    assert status == "fail", f"Arena prints it as Splinter of the Shadows: {(status, evidence)}"
    assert ASHCOAT in evidence, f"the evidence does not name the card: {evidence}"


def test_s5_fails_a_limits_question_that_leaves_out_crossover_cards():
    r, f = crossover_round(holds=False, said="Any limits on sets or cards to avoid?")
    status, evidence = verdict(r, "S5", f)
    assert status == "fail", (status, evidence)
    assert "cards to avoid" in evidence, f"the evidence does not quote the question: {evidence}"


def test_s5_fails_a_crossover_printing_arena_does_not_print():
    paper_only = {**crossover_printing(ASHCOAT, "Splinter of the Shadows"), "games": ["paper"]}
    r, f = crossover_round(offered(ASHCOAT, crossover=True, printed_name="Splinter of the Shadows"))
    status, evidence = verdict(r, "S5", f, {scryfall_id(ASHCOAT): paper_only})
    assert status == "fail", f"the page would show a printing Arena never prints: {(status, evidence)}"
    assert ASHCOAT in evidence, f"the evidence does not name the card: {evidence}"


def test_s5_cannot_tell_crossover_marks_no_offer_shows():
    f = facts(**SEEN_BY_THE_READER, limits_question_names_crossover=fact(True, "e.g. crossover cards"))
    status, evidence = verdict(offer_written_by_a_script_then_removed(), "S5", f,
                               {scryfall_id(ASHCOAT): crossover_printing(ASHCOAT, "Splinter of the Shadows")})
    assert (status, "cannot tell" in evidence) == ("n/a", True), \
        f"S5 judges the crossover marks though no offered card could be read: {(status, evidence)}"


# ---------- S6 to S11: what the reader reads ----------

def reader_verdict(key, fact_name, holds, said, fmt="brawl", workspace=None):
    r = fake_run([], [], workspace=workspace or deck_folder())
    return verdict(r, key, facts(format=fmt, **{fact_name: fact(holds, said)}))


def test_s6_passes_a_commander_chosen_before_colours():
    status, evidence = reader_verdict("S6", "commander_before_colours", True, "Which commander? ... Wick sets black")
    assert status == "pass", evidence


def test_s6_fails_colours_asked_before_the_commander_in_brawl():
    # The first real build: "which colours do you want the deck to be?", answered "we decide on the commander first" (#43).
    status, evidence = reader_verdict("S6", "commander_before_colours", False, "which colours do you want the deck to be?")
    assert status == "fail", (status, evidence)
    assert "which colours" in evidence, evidence


def test_s6_is_not_applicable_in_standard():
    status, evidence = reader_verdict("S6", "commander_before_colours", None, "", fmt="standard")
    assert status == "n/a", f"Standard has no commander: {(status, evidence)}"


def test_s7_passes_a_set_count_that_says_any_printing_counts():
    status, evidence = reader_verdict("S7", "set_count_says_any_printing", True,
                                      "7 Rats with a Bloomburrow printing, counting reprints")
    assert status == "pass", evidence


def test_s7_fails_a_set_count_read_from_one_printing():
    # The first real build missed Lightshell Duo, "filed under a later reprint" (#44).
    status, evidence = reader_verdict("S7", "set_count_says_any_printing", False, "all six from Bloomburrow")
    assert status == "fail", (status, evidence)
    assert "all six from Bloomburrow" in evidence, evidence


def test_s7_is_not_applicable_without_a_set_criterion():
    status, evidence = reader_verdict("S7", "set_count_says_any_printing", None, "")
    assert status == "n/a", (status, evidence)


def test_s9_passes_terms_explained_where_first_used():
    status, evidence = reader_verdict("S9", "terms_explained_where_first_used", True,
                                      "Recursion (bringing cards back from the graveyard)")
    assert status == "pass", evidence


def test_s9_fails_a_category_name_left_unexplained():
    # The first real build: "Recursion" was accepted in the template; five categories later, "what is recursion?" (#46).
    status, evidence = reader_verdict("S9", "terms_explained_where_first_used", False, "Template: ... Recursion 8")
    assert status == "fail", (status, evidence)
    assert "Recursion" in evidence, evidence


def test_s11_passes_a_complete_deck_with_handbook_and_scenes_unasked():
    deck = complete_deck(name="The Whorled Swarm", handbook=[{"title": "How it wins", "blocks": []}],
                         scenes=[{"title": "Every kill is a Rat", "steps": []}])
    status, evidence = reader_verdict("S11", "handbook_written_unasked", True, "Here is the handbook and two scenes.",
                                      workspace=deck_folder(deck, "brawl-the-whorled-swarm"))
    assert status == "pass", evidence


def test_s11_fails_a_handbook_asked_about():
    # The first real build: "Do you want the handbook, or is the deck done?" (#48).
    deck = complete_deck(name="The Whorled Swarm", handbook=[{"title": "How it wins", "blocks": []}],
                         scenes=[{"title": "Every kill is a Rat", "steps": []}])
    status, evidence = reader_verdict("S11", "handbook_written_unasked", False,
                                      "Do you want the handbook, or is the deck done?",
                                      workspace=deck_folder(deck, "brawl-the-whorled-swarm"))
    assert status == "fail", (status, evidence)
    assert "Do you want the handbook" in evidence, evidence


def test_s11_fails_a_complete_deck_saved_without_a_handbook():
    status, evidence = reader_verdict("S11", "handbook_written_unasked", True, "",
                                      workspace=deck_folder(complete_deck(name="The Whorled Swarm"),
                                                            "brawl-the-whorled-swarm"))
    assert status == "fail", f"a complete deck.json has no handbook and no scenes: {(status, evidence)}"
    assert "handbook" in evidence, f"the evidence does not name what is missing: {evidence}"


def test_s11_is_not_applicable_to_an_unfinished_deck():
    status, evidence = reader_verdict("S11", "handbook_written_unasked", None, "")
    assert status == "n/a", f"a deck of two cards is not complete: {(status, evidence)}"


# ---------- S8: every number about the deck comes from a script ----------

COUNTED = [{"role": "player", "text": "How many Rats now?"}, {"role": "deckwright", "text": "The deck has 31 Rats."}]
COUNT_FACTS = {"deck_counts_stated": [{"message": 1, "said": "31 Rats"}]}
COUNT_SCRIPT = ("python3 -c \"import json; d = json.load(open('brawl-rats/deck.json')); "
                "print(sum(c['count'] for c in d['cards'] if 'Rat' in c['copy']['type_line']))\"")


def test_s8_passes_a_count_read_by_a_script_over_deck_json():
    r = fake_run(COUNTED, bash(COUNT_SCRIPT, 0, answer="31"), workspace=deck_folder())
    status, evidence = verdict(r, "S8", facts(**COUNT_FACTS))
    assert status == "pass", evidence


def test_s8_fails_a_count_made_by_hand():
    # The first real build said "32 Rats" from 66 cards to the end; the review script found 31 (#45).
    r = fake_run(COUNTED, [], workspace=deck_folder())
    status, evidence = verdict(r, "S8", facts(**COUNT_FACTS))
    assert status == "fail", (status, evidence)
    assert "31 Rats" in evidence, f"the evidence does not quote the count: {evidence}"


def test_s8_fails_a_count_whose_script_ran_in_an_earlier_exchange():
    messages = [{"role": "player", "text": "Count the Rats"}, {"role": "deckwright", "text": "30 Rats."}, *COUNTED]
    r = fake_run(messages, bash(COUNT_SCRIPT, 0, answer="30"), workspace=deck_folder())
    status, evidence = verdict(r, "S8", facts(deck_counts_stated=[{"message": 1, "said": "30 Rats"},
                                                                  {"message": 3, "said": "31 Rats"}]))
    assert status == "fail", f"31 Rats was said in exchange 1 and counted in exchange 0: {(status, evidence)}"
    assert "31 Rats" in evidence and "30 Rats" not in evidence, evidence


def test_s8_fails_a_count_read_off_deck_json_by_eye():
    r = fake_run(COUNTED, bash("cat brawl-rats/deck.json", 0), workspace=deck_folder())
    status, evidence = verdict(r, "S8", facts(**COUNT_FACTS))
    assert status == "fail", f"cat is not a script: {(status, evidence)}"


def test_s8_fails_a_count_whose_exchange_ran_only_the_save_script():
    save = ("python3 - <<'EOF'\nimport json\nd = json.load(open('brawl-rats/deck.json'))\n"
            "d['cards'].append({'name': 'Rat Colony', 'count': 1})\njson.dump(d, open('brawl-rats/deck.json', 'w'))\nEOF")
    r = fake_run(COUNTED, bash(save, 0), workspace=deck_folder())
    status, evidence = verdict(r, "S8", facts(**COUNT_FACTS))
    assert status == "fail", f"the only script saved deck.json and printed no count: {(status, evidence)}"
    assert "31 Rats" in evidence, f"the evidence does not quote the count: {evidence}"


def test_s8_fails_a_count_its_script_did_not_print():
    r = fake_run(COUNTED, bash(COUNT_SCRIPT, 0, answer="30"), workspace=deck_folder())
    status, evidence = verdict(r, "S8", facts(**COUNT_FACTS))
    assert status == "fail", f"the script printed 30 and the reply says 31 Rats: {(status, evidence)}"
    assert "31 Rats" in evidence, f"the evidence does not quote the count: {evidence}"


# ---------- S10 and S12: the deck's name and its folder ----------

NAMED = [{"role": "player", "text": "Rats, with Wick"},
         {"role": "deckwright", "text": "The deck is complete. What would you like to call it?"},
         {"role": "player", "text": "The Whorled Swarm"},
         {"role": "deckwright", "text": "It is The Whorled Swarm now; the handbook is written."}]
RENAME_LINE = "- 2026-11-12 · name · The Whorled Swarm · folder brawl-rats renamed brawl-the-whorled-swarm"
NAME_FACTS = {"name_asked_once_complete_before_handbook": fact(True, "What would you like to call it?")}


def named_run(name="The Whorled Swarm", folder="brawl-the-whorled-swarm", ledger=True, early_name=None):
    final = complete_deck(name=name)
    trace = (write("brawl-rats/deck.json", deck_json(name=early_name), 0)
             + write("brawl-rats/deck.json", complete_deck(), 0))
    if folder != "brawl-rats":
        trace += bash(f"mv brawl-rats {folder}", 1)
    trace += write(f"{folder}/deck.json", final, 1)
    lines = f"# Ledger\n{LEDGER_LINE}\n" + (f"{RENAME_LINE}\n" if ledger else "")
    return fake_run(NAMED, trace, workspace={f"{folder}/deck.json": final, f"{folder}/LEDGER.md": lines})


def test_s10_passes_a_name_the_player_gave_once_the_deck_was_complete():
    status, evidence = verdict(named_run(), "S10", facts(**NAME_FACTS))
    assert status == "pass", evidence


def test_s10_fails_a_name_the_tutor_made_up():
    # The first real build was approved as "Wick's Rats", a name the tutor made up (#47).
    status, evidence = verdict(named_run("Wick's Rats", "brawl-wicks-rats"), "S10", facts(**NAME_FACTS))
    assert status == "fail", (status, evidence)
    assert "Wick's Rats" in evidence, f"the evidence does not name the made-up name: {evidence}"


def test_s10_fails_a_name_saved_before_the_deck_was_complete():
    status, evidence = verdict(named_run(early_name="Wick's Rats"), "S10", facts(**NAME_FACTS))
    assert status == "fail", f"deck.json had a name at two cards: {(status, evidence)}"
    assert "Wick's Rats" in evidence, f"the evidence does not name the early name: {evidence}"


def test_s10_fails_a_name_never_asked_for():
    f = facts(name_asked_once_complete_before_handbook=fact(False, "Handbook written. Is the deck done?"))
    status, evidence = verdict(named_run(), "S10", f)
    assert status == "fail", (status, evidence)
    assert "Is the deck done?" in evidence, evidence


def test_s10_fails_a_name_the_player_said_only_before_it_was_asked_for():
    messages = [{"role": "player", "text": "I love rats, build me a rat deck"},
                {"role": "deckwright", "text": "The deck is complete; I've called it Rats."}]
    r = fake_run(messages, write("brawl-rats/deck.json", complete_deck(name="Rats")),
                 workspace=deck_folder(complete_deck(name="Rats")))
    status, evidence = verdict(r, "S10")
    assert status == "fail", f"the tutor named the deck after a word of the player's opening: {(status, evidence)}"
    assert "not a name the player gave" in evidence, evidence


def test_s12_passes_a_folder_named_by_theme_then_renamed_by_name():
    status, evidence = verdict(named_run(), "S12", facts(**NAME_FACTS))
    assert status == "pass", evidence


def test_s12_passes_an_unnamed_deck_in_its_theme_folder():
    r = fake_run(PICKED, saved_pick(), workspace=deck_folder())
    status, evidence = verdict(r, "S12")
    assert status == "pass", evidence


def test_s12_passes_a_theme_folder_numbered_when_taken():
    other = deck_json([deck_card("Infernal Grasp")], name="Another deck")
    r = fake_run(PICKED, write("brawl-rats-2/deck.json", deck_json()),
                 workspace={**deck_folder(other), **deck_folder(folder="brawl-rats-2")})
    status, evidence = verdict(r, "S12")
    assert status == "pass", f"brawl-rats was taken by another deck: {evidence}"


def test_s12_fails_a_folder_named_by_date():
    # Before #57 decks were saved as brawl-2026-11-11, so two decks of a day collide.
    r = fake_run(PICKED, write("brawl-2026-11-11/deck.json", deck_json()), workspace=deck_folder(folder="brawl-2026-11-11"))
    status, evidence = verdict(r, "S12")
    assert status == "fail", (status, evidence)
    assert "brawl-2026-11-11" in evidence, f"the evidence does not name the folder: {evidence}"


def test_s12_fails_a_named_deck_left_in_its_theme_folder():
    status, evidence = verdict(named_run(folder="brawl-rats"), "S12", facts(**NAME_FACTS))
    assert status == "fail", f"The Whorled Swarm is still in brawl-rats: {(status, evidence)}"
    assert "brawl-rats" in evidence, f"the evidence does not name the folder: {evidence}"


def test_s12_fails_a_rename_the_ledger_does_not_record():
    status, evidence = verdict(named_run(ledger=False), "S12", facts(**NAME_FACTS))
    assert status == "fail", (status, evidence)
    assert "ledger" in evidence.lower(), f"the evidence does not name the ledger: {evidence}"


def test_s12_sees_a_rename_made_through_python():
    renames = ["python3 -c \"import os; os.rename('brawl-rats', 'brawl-the-whorled-swarm')\"",
               "python3 -c \"import shutil; shutil.move('brawl-rats', 'brawl-the-whorled-swarm')\"",
               "python3 -c \"import pathlib; pathlib.Path('brawl-rats').rename('brawl-the-whorled-swarm')\""]
    final = complete_deck(name="The Whorled Swarm")
    unseen = []
    for rename in renames:
        # Nothing was written to brawl-rats in the trace, so only the rename shows the move.
        trace = bash(rename, 1) + write("brawl-the-whorled-swarm/deck.json", final, 1)
        r = fake_run(NAMED, trace, workspace=deck_folder(final, "brawl-the-whorled-swarm"))
        status, evidence = verdict(r, "S12", facts(**NAME_FACTS))
        if status != "fail" or "ledger" not in evidence.lower():
            unseen.append((rename, status))
    assert not unseen, f"renames the ledger does not record, and S12 does not see: {unseen}"


def test_s12_passes_a_folder_named_by_words_of_the_theme():
    deck = deck_json(theme="Creature tokens")
    r = fake_run(PICKED, write("brawl-tokens/deck.json", deck), workspace=deck_folder(deck, "brawl-tokens"))
    status, evidence = verdict(r, "S12")
    assert status == "pass", f"brawl-tokens is made only of words of the theme Creature tokens: {evidence}"
    r = fake_run(PICKED, write("brawl-goblins/deck.json", deck), workspace=deck_folder(deck, "brawl-goblins"))
    status, evidence = verdict(r, "S12")
    assert status == "fail", f"goblins is no word of the theme Creature tokens: {(status, evidence)}"


def test_the_runner_lets_deckwright_rename_a_folder_with_mv():
    allowed = [tool for tool in runner.DECKWRIGHT_ALLOWED if tool == "Bash" or tool.startswith("Bash(mv")]
    assert allowed, f"the skill renames the deck folder with mv, and the runner refuses it: {runner.DECKWRIGHT_ALLOWED}"


# ---------- S13: each card's copy saves its layout ----------

def test_s13_passes_every_card_copy_with_a_layout():
    r = fake_run([], [], workspace=deck_folder())
    status, evidence = verdict(r, "S13")
    assert status == "pass", evidence


def test_s13_fails_a_card_copy_without_a_layout():
    deck = deck_json([deck_card("Wick, the Whorled Mind", category="Commander"), deck_card("Rat Colony", layout=None)])
    r = fake_run([], [], workspace=deck_folder(deck))
    status, evidence = verdict(r, "S13")
    assert status == "fail", (status, evidence)
    assert "Rat Colony" in evidence and "Wick" not in evidence, f"the evidence does not name only the card: {evidence}"


class NetworkBlocked(RuntimeError):
    """Not an OSError: checks.scryfall_get retries those, and urllib wraps them in URLError."""


def block_the_network():
    def refuse(host):
        raise NetworkBlocked(f"the offline tests tried to reach {host}")

    def resolve(host, *args, **kwargs):
        refuse(host)

    def connect(connect_to):
        def checked(sock, address):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                refuse(address[0])
            return connect_to(sock, address)
        return checked

    # Name lookups are refused so the error names the host the test asked for; through a proxy
    # the only host a connection names is the proxy's, and these tests need none.
    for key in [key for key in os.environ if key.lower().endswith("_proxy")]:
        del os.environ[key]
    socket.getaddrinfo = resolve
    socket.socket.connect = connect(socket.socket.connect)
    socket.socket.connect_ex = connect(socket.socket.connect_ex)


def run_tests(tests):
    failed = 0
    for name, fn in tests.items():
        try:
            fn()
            print("PASS", name)
        except SystemExit as e:
            failed += 1
            print("FAIL", name, "--", f"exited with status {e.code}")
        except Exception as e:
            failed += 1
            print("FAIL", name, "--", e if isinstance(e, AssertionError) else traceback.format_exc(limit=1))
    if not tests:
        print("no tests found")
    print(f"{failed} failed")
    return 1 if failed or not tests else 0


if __name__ == "__main__":
    block_the_network()
    sys.exit(run_tests({name: fn for name, fn in list(globals().items()) if name.startswith("test_")}))
