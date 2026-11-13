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
import checks
import headless
import run as runner

FACT_NULL = {"holds": None, "evidence": ""}


def card(name, type_line, cost="", ci=(), fmt_legal=("brawl", "standard")):
    return {
        "name": name,
        "type_line": type_line,
        "mana_cost": cost,
        "color_identity": list(ci),
        "legalities": {f: "legal" for f in fmt_legal},
        "on_arena": True,
    }


READER_FACTS_ADDED = [
    "ladder_steps_with_counts",
    "suggestions_marked",
    "you_pick_takes_the_suggested",
    "limits_question_names_crossover",
    "commander_before_colours",
    "set_count_says_any_printing",
    "terms_explained_where_first_used",
    "name_asked_once_complete_before_handbook",
    "handbook_written_unasked",
]


def facts(**over):
    base = {
        "format": "brawl",
        "deck_colours": [],
        "offers": [],
        "confirmations": [],
        "basic_split_confirmed": True,
        "review_type_counts": [],
        "criterion_change_recorded_with_reason": None,
        "card_removed_without_player_word": [],
        "dismissed_finding_raised_again": None,
        "saved_categories": [],
        "deck_counts_stated": [],
        **{k: FACT_NULL for k in [*checks.EXTRA_FACTS, *READER_FACTS_ADDED]},
    }
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


def state_files(state):
    """A state's deck folders as workspace files: each folder maps to (deck, ledger lines),
    a deck that is a str is saved as it is, so it need not parse, and None leaves a file out."""
    files = {}
    for folder, (deck, lines) in state.items():
        if deck is not None:
            files[f"{folder}/deck.json"] = deck
        if lines is not None:
            files[f"{folder}/LEDGER.md"] = "".join(line + "\n" for line in lines)
    return files


def put(root, files):
    """Saves `files`, by path under `root`: a dict as JSON, bytes as they are, anything else as text."""
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(json.dumps(content, indent=2) if isinstance(content, dict) else content)


def fake_run(messages, trace, deck=None, start=None, brief="x", workspace=None, states=None, start_state=None):
    """A run folder on disk as run.py leaves it, read by checks.Run.

    `states` are the deck folders as the runner records them after each exchange, in
    exchange order, under `after/<exchange>/`; without them the run has no `after/`, as
    every run before the record began. `start_state` is recorded as `after/start`.
    `workspace` maps a path in the run's workspace to its content, saved as `put` saves
    it; left out, the workspace holds the last state. `deck`, when given, is what the
    run's deck() returns whatever the workspace holds.
    """
    path = pathlib.Path(tempfile.mkdtemp(dir=runs_root()))
    ws = path / "workspace"
    ws.mkdir()
    (path / "run.json").write_text(
        json.dumps(
            {
                "brief": brief,
                "start": "start" if start else None,
                "ends": None,
                "ended": "player ended",
                "exchanges": len(states or [None]),
                "deckwright_cost_usd": 0,
            }
        )
    )
    (path / "conversation.jsonl").write_text("".join(json.dumps(m) + "\n" for m in messages))
    (path / "trace.jsonl").write_text("".join(json.dumps(e).replace(WORKSPACE, str(ws)) + "\n" for e in trace))
    if workspace is None and states:
        workspace = state_files(states[-1])
    put(ws, workspace or {})
    for exchange, state in enumerate(states or []):
        put(path / "after" / str(exchange), state_files(state))
    if start_state is not None:
        put(path / "after" / "start", state_files(start_state))
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
    return [
        {
            "exchange": exchange,
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "id": call_id, "name": name, "input": given}]},
        },
        {"exchange": exchange, "type": "user", "message": {"content": [result]}},
    ]


def write(rel, content, exchange=0, refused=False):
    text = content if isinstance(content, str) else json.dumps(content, indent=2)
    return tool_call(
        "Write",
        {"file_path": f"{WORKSPACE}/{rel}", "content": text},
        exchange,
        answer=f"File created successfully at: {WORKSPACE}/{rel}",
        refused=refused,
    )


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
    answer = (
        "publish 429: daily publish limit for your plan reached (200)"
        if refused
        else f"Published {page} at {link} (Version {version}, version id v{version}-{made})"
    )
    return tool_call("Artifact", given, exchange, answer=answer, refused=refused)


PACK = "python3 /plugins/deckwright/skills/deckwright/page/pack.py brawl-rats"
KNOWN = {
    "Wick, the Whorled Mind": card("Wick, the Whorled Mind", "Legendary Creature — Rat Warlock", "{1}{B}", "B"),
    "Rat Colony": card("Rat Colony", "Creature — Rat", "{1}{B}", "B"),
    "Infernal Grasp": card("Infernal Grasp", "Instant", "{1}{B}", "B"),
    "Feed the Swarm": card("Feed the Swarm", "Sorcery", "{1}{B}", "B"),
    "Swamp": card("Swamp", "Basic Land — Swamp", "", "B"),
}


def scryfall_id(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def deck_card(name, count=1, category="Token makers", layout="normal"):
    copy = {"mana_cost": "", "mana_value": 2, "type_line": "", "text": "", "rarity": "common", "taken": "2026-11-12"}
    if layout:
        copy["layout"] = layout
    return {
        "scryfall_id": scryfall_id(name),
        "name": name,
        "count": count,
        "category": category,
        "tags": [],
        "checked": True,
        "bends": None,
        "why": "Makes Rats.",
        "copy": copy,
    }


def deck_json(cards=None, fmt="brawl", name=None, theme="Rats", **more):
    cards = (
        cards
        if cards is not None
        else [deck_card("Wick, the Whorled Mind", category="Commander"), deck_card("Rat Colony")]
    )
    deck = {
        "version": 2,
        "format": fmt,
        "criteria": [{"kind": "format", "text": "Brawl on Arena"}, {"kind": "theme", "text": theme}],
        "categories": [],
        "cards": cards,
        "maybeboard": [],
        "tokens": [],
        "approved": False,
        **more,
    }
    if name:
        deck["name"] = name
    return deck


def complete_deck(name=None, **more):
    """A Brawl deck of 100 cards: the commander, 64 Rat Colony and 35 Swamps."""
    return deck_json(
        [
            deck_card("Wick, the Whorled Mind", category="Commander"),
            deck_card("Rat Colony", 64),
            deck_card("Swamp", 35, category="Lands"),
        ],
        name=name,
        **more,
    )


def offered(name, suggested=False, **marks):
    c = {
        "scryfall_id": scryfall_id(name),
        "name": name,
        "reason": f"{name} does the job.",
        "copy": {"mana_cost": "{1}{B}", "type_line": "Instant", "text": ""},
        **marks,
    }
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
    return offer(
        *[
            group(h, [next(names) for _ in range(size)], total, suggested)
            for h, size, total in zip(headings, sizes, totals)
        ]
    )


def decks_in(run):
    """Every deck.json the run's workspace holds, or held after an exchange."""
    found = []
    for path in [*(run.path / "workspace").rglob("deck.json"), *(run.path / "after").rglob("deck.json")]:
        try:
            deck = json.loads(path.read_text())
        except ValueError:
            continue
        if isinstance(deck, dict):
            found.append(deck)
    return found


def named_cards(cards):
    return [c for c in cards or [] if isinstance(c, dict) and isinstance(c.get("name"), str)]


def cache_for(run, printings=None):
    """Card facts for every card the run names, so no check reaches Scryfall. A
    printing is kept under its API path, `/cards/<scryfall id>`; `printings` adds or
    replaces printings by Scryfall id."""
    cache = {}
    for deck in decks_in(run):
        groups = [g for g in (deck.get("offer") or {}).get("groups") or [] if isinstance(g, dict)]
        for c in named_cards(
            [
                *(deck.get("cards") or []),
                *(deck.get("maybeboard") or []),
                *[c for g in groups for c in g.get("cards") or []],
            ]
        ):
            cache[c["name"]] = KNOWN.get(c["name"]) or card(c["name"], "Creature — Rat", "{B}", "B")
            sid = c.get("scryfall_id", "")
            cache[f"/cards/{sid}"] = {"id": sid, "name": c["name"], "games": ["arena", "paper"], "promo_types": []}
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


def test_c1_is_not_applicable_to_a_brief_that_ends_before_any_pick():
    r = fake_run(
        [{"role": "player", "text": "go"}, {"role": "deckwright", "text": "Here is the template."}],
        [],
        workspace=deck_folder(deck_json([])),
    )
    r.summary = {**r.summary, "ends": "template"}
    status, evidence = verdict(r, "C1")
    assert status == "n/a", f"the brief stops at the template, so no card was there to pick: {(status, evidence)}"


def test_c4_does_not_count_a_refused_publish():
    trace = [
        {
            "exchange": 0,
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "id": "t1", "name": "Artifact", "input": {"file_path": "index.html"}}]
            },
        },
        {
            "exchange": 0,
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "is_error": True,
                        "content": "publish 429: daily publish limit for your plan reached (200)",
                    }
                ]
            },
        },
    ]
    r = fake_run([{"role": "player", "text": "I'll take Sol Ring"}, {"role": "deckwright", "text": "added"}], trace)
    assert r.saves_by_exchange().get(0, 0) == 0, "a refused publish was counted as the pick's save"


def test_c3_needs_the_whole_name():
    trace = [
        {
            "exchange": 0,
            "type": "user",
            "message": {"content": [{"type": "tool_result", "content": "Usage: curl [options...] <url>"}]},
        }
    ]
    r = fake_run([{"role": "player", "text": "hi"}, {"role": "deckwright", "text": "Try Opt"}], trace)
    seen = r.tool_results_before(0).lower()
    assert not checks.named_in("Opt", seen), "Opt counts as looked up because 'options' was in a curl usage line"
    assert checks.named_in("Opt", '{"name": "opt"}')


def test_c3_counts_only_lookups_in_the_same_conversation():
    trace = [
        {
            "conversation": 1,
            "exchange": 0,
            "type": "user",
            "message": {"content": [{"type": "tool_result", "content": '{"name": "Lightning Helix"}'}]},
        },
        {"conversation": 2, "exchange": 1, "type": "assistant", "message": {"content": []}},
    ]
    messages = [
        {"role": "player", "conversation": 1, "text": "a"},
        {"role": "deckwright", "conversation": 1, "text": "b"},
        {"role": "player", "conversation": 2, "text": "c"},
        {"role": "deckwright", "conversation": 2, "text": "Lightning Helix"},
    ]
    r = fake_run(messages, trace)
    seen = r.tool_results_before(checks.message_to_exchange(r, 3)).lower()
    assert "lightning helix" not in seen, "AC22 says 'earlier in that conversation'; conversation 1's lookup counted"


def test_c6_compares_basics_of_a_colour_with_no_pips():
    cache = {
        "Llanowar Elves": card("Llanowar Elves", "Creature — Elf Druid", "{G}", "G"),
        "Shock": card("Shock", "Instant", "{R}", "R"),
        "Forest": card("Forest", "Basic Land — Forest", "", "G"),
        "Mountain": card("Mountain", "Basic Land — Mountain", "", "R"),
        "Plains": card("Plains", "Basic Land — Plains", "", "W"),
    }
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
    cache = {
        "Bonecrusher Giant // Stomp": card(
            "Bonecrusher Giant // Stomp", "Creature — Giant // Instant — Adventure", "{2}{R} // {1}{R}", "R"
        )
    }
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
    asked = [
        name for name in ladder_facts if name in checks.READER_SCHEMA["properties"] or name in checks.READER_PROMPT
    ]
    assert not asked, f"the reader is still asked for: {asked}"


def test_c5_accepts_a_count_without_the_commander():
    cache = {
        "Vren, the Relentless": card("Vren, the Relentless", "Legendary Creature — Rat Rogue", "{2}{U}{B}", "UB"),
        "Rat Colony": card("Rat Colony", "Creature — Rat", "{1}{B}", "B"),
    }
    r = fake_run([], [])
    r.final_list = lambda: (Counter({"Vren, the Relentless": 1, "Rat Colony": 10}), "Vren, the Relentless")
    for said in (10, 11):
        r.read = lambda: facts(review_type_counts=[{"message": 1, "card_type": "Creature", "count": said}])  # noqa: B023
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

    shared = {
        "CLAUDE_MEMORY_STORES": '[{"path": "/v1/code/memory/shared"}]',
        "CLAUDE_COWORK_MEMORY_PATH_OVERRIDE": "/shared/memory",
    }
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
    shared = {
        "CLAUDE_MEMORY_STORES": '[{"path": "/v1/code/memory/shared"}]',
        "CLAUDE_COWORK_MEMORY_PATH_OVERRIDE": "/shared/memory",
    }

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
    return [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": call_id,
                        "name": "Artifact",
                        "input": {"file_path": "index.html", "action": action},
                    }
                ]
            },
        },
        {"type": "user", "message": {"content": [answer]}},
    ]


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
            summaries = list(
                runner.play_round([pathlib.Path(tmp) / "a.md"], "bare", 3, round_dir, 2, 5, runner.PublishBudget(10))
            )
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
            list(
                runner.play_round(
                    [pathlib.Path(tmp) / "a.md"], "bare", 1, stopped.parent, 2, 5, runner.PublishBudget(10)
                )
            )
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
            with mock.patch.object(
                sys, "argv", ["run.py", "a.md", "--arm", "skill", "--runs", "2", "--resume", "20261111T120000"]
            ):
                runner.main()
            with (
                mock.patch.object(sys, "argv", ["run.py", "a.md", "--arm", "skill", "--resume", "20250101T000000"]),
                mock.patch.object(sys, "stderr"),
            ):
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

    shared = {
        "CLAUDE_MEMORY_STORES": '[{"path": "/v1/code/memory/shared"}]',
        "CLAUDE_COWORK_MEMORY_PATH_OVERRIDE": "/shared/memory",
    }
    with (
        tempfile.TemporaryDirectory() as tmp,
        mock.patch.dict(os.environ, shared),
        mock.patch.object(subprocess, "Popen", Claude),
    ):
        r = fake_run([{"role": "player", "text": "hi"}], [])
        r.path = pathlib.Path(tmp)
        checks.Run.read(r)
        judge.ask("one conversation", "another")
    assert len(starts) == 2, starts
    for who, env in zip(("reader", "judge"), starts):
        assert env is not None, f"the {who} ran in the parent's environment, shared memory and all"
        assert "CLAUDE_MEMORY_STORES" not in env, f"the {who} can reach the project's memory store"
        assert env.get("CLAUDE_COWORK_MEMORY_PATH_OVERRIDE") not in (None, "/shared/memory"), (
            f"the {who} was shown the project's memory folder"
        )


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
    assert status != "SystemExit(0) out of run_tests", (
        "a test calling sys.exit(0) ended the run, so CI goes green on the tests it never ran"
    )
    assert status == 1, f"a test called sys.exit(0) and the exit status is {status}"
    assert any(line.startswith("FAIL test_exits") for line in said), (
        f"the exiting test is not reported as failed: {said}"
    )
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
        f"{name} lacks {', '.join(sorted(missing))}" for name, missing in sorted(lacking.items())
    )


# ---------- the deck kept as a folder in the workspace ----------

LEDGER_LINE = "- 2026-11-12 · in · Rat Colony · Makes a Rat every turn."
GRASP_LINE = "- 2026-11-12 · in · Infernal Grasp · Kills anything."
NO_RECORD = "no record of the deck folder after each exchange"
WICK = deck_card("Wick, the Whorled Mind", category="Commander")


def ledger(*lines):
    return ["# Ledger", *lines]


def deck_folder(deck=None, folder="brawl-rats", **more):
    return {f"{folder}/deck.json": deck or deck_json(), f"{folder}/LEDGER.md": f"# Ledger\n{LEDGER_LINE}\n", **more}


PICKED = [
    {"role": "player", "text": "Rats, with Wick"},
    {"role": "deckwright", "text": "Wick leads. Token makers next?"},
    {"role": "player", "text": "I'll take Rat Colony"},
    {"role": "deckwright", "text": "Rat Colony is in. Removal next?"},
]
PICK_FACTS = {"confirmations": [{"message": 2, "cards": ["Rat Colony"]}]}
BEFORE_PICK = {"brawl-rats": (deck_json([WICK]), ledger())}
AFTER_PICK = {"brawl-rats": (deck_json(), ledger(LEDGER_LINE))}


def picked(after=AFTER_PICK, trace=()):
    """PICKED in a run whose folder held `after` once Rat Colony was picked, in exchange 1."""
    return fake_run(PICKED, list(trace), states=[BEFORE_PICK, after])


def test_final_list_reads_the_deck_from_the_workspace_when_nothing_was_published():
    r = fake_run([], [], workspace=deck_folder())
    cards, commander = r.final_list()
    assert cards == Counter({"Wick, the Whorled Mind": 1, "Rat Colony": 1}), (
        f"the workspace's deck.json was not read: {cards}"
    )
    assert commander == "Wick, the Whorled Mind", commander


def test_final_list_reads_the_deck_folder_the_run_last_changed():
    other = deck_json([deck_card("Infernal Grasp")], name="Another deck")
    states = [
        {"brawl-rats": (other, ledger())},
        {"brawl-rats": (other, ledger()), "brawl-rats-2": (deck_json(), ledger(LEDGER_LINE))},
    ]
    path = fake_run([], [], states=states).path
    # The other deck is the newer on disk, so only the record shows which one the run changed last.
    os.utime(path / "workspace" / "brawl-rats" / "deck.json", (2_000_000_000, 2_000_000_000))
    cards, _ = checks.Run(path).final_list()
    assert "Rat Colony" in cards and "Infernal Grasp" not in cards, f"read the folder the run did not change: {cards}"


def test_final_list_skips_a_card_that_is_no_card_or_has_no_name():
    deck = {
        "cards": [
            "Sol Ring",
            {"count": 1, "category": "Ramp"},
            {"name": None, "count": 1},
            {"name": "Rat Colony", "count": 1, "category": "Token makers"},
        ]
    }
    r = fake_run([], [], deck=deck)
    try:
        cards, _ = checks.Run.final_list(r)
    except Exception as e:
        raise AssertionError(f"one card that is not a card stops the checks of every run: {e!r}")
    assert cards == Counter({"Rat Colony": 1}), cards


def test_c8_passes_a_complete_deck_kept_only_in_the_workspace():
    r = fake_run([], [], workspace=deck_folder(complete_deck()))
    status, evidence = verdict(r, "C8")
    assert status == "pass", f"a 100-card deck in the workspace, never published: {evidence}"


def test_c12_finds_the_page_in_the_workspace_folder_without_a_publish():
    sid = scryfall_id("Rat Colony")
    r = fake_run(
        [],
        [],
        workspace=deck_folder(
            complete_deck(),
            **{"brawl-rats/index.html": "<title>Deck</title>", f"brawl-rats/cards/{sid}.jpg": b"\xff\xd8\xff"},
        ),
    )
    _, evidence = verdict(r, "C12")
    missing = [part for part in ("no page", "no deck.json", "no LEDGER.md", "no card images") if part in evidence]
    assert not missing, f"the folder holds the page and C12 says it is missing: {evidence}"


def test_states_are_the_deck_folders_after_each_exchange_in_exchange_order():
    states = [{"brawl-rats": (deck_json(name=f"Deck {n}"), ledger(f"- line {n}"))} for n in range(11)]
    states[3] = {"brawl-rats": ("{not json", ledger("- line 3"))}
    r = fake_run([], [], states=states)
    assert len(r.states) == 11, f"11 exchanges recorded, {len(r.states)} states read"
    deck, lines = r.states[10]["brawl-rats"]
    assert deck["name"] == "Deck 10", f"after/10 was read as state 10 by the order of its name: {deck['name']}"
    assert lines == ["# Ledger", "- line 10"], lines
    assert r.states[3]["brawl-rats"][0] is None, "a deck.json that does not parse is read as something"


def test_a_save_is_a_change_to_deck_json_not_a_publish():
    first = deck_json()
    approved = deck_json(approved=True)
    popped = deck_json([WICK], approved=True)
    states = [
        {"brawl-rats": (first, ledger())},
        {"brawl-rats": (first, ledger())},
        {"brawl-rats": (approved, ledger())},
        {"brawl-rats": (approved, ledger())},
        {"brawl-rats": (popped, ledger())},
        {"brawl-rats": (popped, ledger())},
        {"brawl-rats": (popped, ledger(LEDGER_LINE))},
        {"brawl-rats": (popped, ledger(LEDGER_LINE)), "brawl-tokens": (deck_json(), ledger())},
    ]
    count = (
        "python3 -c \"import json,sys; d=json.load(open('brawl-rats/deck.json')); "
        "sys.stdout.write(str(len(d['cards'])))\""
    )
    trace = (
        publish(1)
        + bash("cat brawl-rats/deck.json", 3)
        + bash(count, 3, answer="1")
        + write("brawl-rats/deck.json", deck_json(), 5, refused=True)
    )
    saves = fake_run([], trace, states=states).saves_by_exchange()
    counted = {e for e in range(len(states)) if saves.get(e)}
    assert counted == {0, 2, 4, 7}, (
        f"saves counted in exchanges {sorted(counted)}; a save is a deck.json that changed "
        "or a deck folder that is new (0, 2, 4, 7), not a publish, a read, a refused "
        "write or a change to the ledger alone"
    )


def test_a_run_from_a_start_saves_only_what_changes_the_start():
    start = deck_json()
    states = [
        {"deck": (start, ledger(LEDGER_LINE))},
        {"deck": (deck_json([*start["cards"], deck_card("Infernal Grasp")]), ledger(LEDGER_LINE, GRASP_LINE))},
    ]
    r = fake_run([], [], start=start, start_state={"deck": (start, ledger(LEDGER_LINE))}, states=states)
    saves = r.saves_by_exchange()
    assert not saves.get(0), "the start, left as it was copied in, was counted as a new deck folder saved"
    assert saves.get(1), "a card added to the start was not counted as a save"


def test_c4_counts_a_pick_saved_to_disk_without_a_publish():
    status, evidence = verdict(picked(), "C4", facts(**PICK_FACTS))
    assert status == "pass", f"the pick was in deck.json after its exchange: {evidence}"


def test_c4_fails_a_pick_whose_exchange_changed_only_the_ledger():
    r = picked(after={"brawl-rats": (deck_json([WICK]), ledger(LEDGER_LINE))})
    status, evidence = verdict(r, "C4", facts(**PICK_FACTS))
    assert status == "fail", f"deck.json was unchanged, and C4 says the pick was saved: {(status, evidence)}"


def test_c4_does_not_fail_a_pick_in_an_exchange_the_runner_never_recorded():
    # The run died in exchange 1, a timeout say: the player's pick is logged and the turn never ended.
    r = fake_run(PICKED[:3], [], states=[BEFORE_PICK])
    status, evidence = verdict(r, "C4", facts(**PICK_FACTS))
    assert status != "fail", f"a turn that never ended was judged as not saving: {(status, evidence)}"


def test_c4_does_not_count_a_deck_json_left_unparseable_as_a_save():
    broken = '{"version": 2, "cards": ['
    r = picked(after={"brawl-rats": (broken, ledger(LEDGER_LINE))})
    status, evidence = verdict(r, "C4", facts(**PICK_FACTS))
    assert status == "fail", f"a pick whose exchange broke deck.json counted as saved: {(status, evidence)}"


def test_c4_is_not_applicable_to_a_run_with_no_record_of_its_folder():
    r = fake_run(PICKED, [], workspace=deck_folder())
    status, evidence = verdict(r, "C4", facts(**PICK_FACTS))
    assert (status, NO_RECORD in evidence) == ("n/a", True), (status, evidence)


REVIEWED = [
    {"role": "player", "text": "Review the deck"},
    {"role": "deckwright", "text": "The deck has 10 creatures."},
    {"role": "player", "text": "Add five more Rat Colony"},
    {"role": "deckwright", "text": "Added."},
]


def reviewed_then_grown(record=True):
    """REVIEWED in a run whose deck held Wick and 10 Rat Colony after the review's
    exchange, 0, and 15 Rat Colony after exchange 1; `record` False keeps only the end."""
    at_review = deck_json([WICK, deck_card("Rat Colony", 10)])
    grown = deck_json([WICK, deck_card("Rat Colony", 15)])
    if not record:
        return fake_run(REVIEWED, [], workspace=deck_folder(grown))
    return fake_run(
        REVIEWED,
        [],
        states=[{"brawl-rats": (at_review, ledger(LEDGER_LINE))}, {"brawl-rats": (grown, ledger(LEDGER_LINE))}],
    )


def review_facts(count):
    return facts(review_type_counts=[{"message": 1, "card_type": "Creature", "count": count}])


def test_c5_passes_a_review_true_of_the_deck_at_that_review():
    status, evidence = verdict(reviewed_then_grown(), "C5", review_facts(10))
    assert status == "pass", f"10 creatures when reviewed; 5 were added after: {(status, evidence)}"
    assert "(against the deck at that review)" in evidence, evidence


def test_c5_fails_a_review_true_only_of_the_final_list():
    status, evidence = verdict(reviewed_then_grown(), "C5", review_facts(15))
    assert status == "fail", f"15 creatures said when the deck held 10: {(status, evidence)}"
    assert "said 15, is 10 to 11" in evidence and "(against the deck at that review)" in evidence, evidence


def test_c5_compares_with_the_final_list_in_a_run_with_no_record_of_its_folder():
    status, evidence = verdict(reviewed_then_grown(record=False), "C5", review_facts(15))
    assert status == "pass", f"without a record the final list is the deck: {(status, evidence)}"
    assert "(against the final list)" in evidence, evidence


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
    r = fake_run(
        [], [], workspace={rel: text for folder in folders for rel, text in deck_folder(folder=folder).items()}
    )
    for folder in folders:
        os.utime(r.path / "workspace" / folder / "deck.json", (1_700_000_000, 1_700_000_000))
    chosen = checks.Run(r.path).folder.name
    assert chosen == "brawl-tokens", f"four decks saved in the same instant, and the listing's order chose {chosen}"


# ---------- the runner records the deck folders after each exchange ----------


def play_recorded(turns, start=None):
    """Play a run offline whose Deckwright turns are `turns`, each called with the
    workspace to change it and returning the turn's events; `start` is the files of a
    start the brief names. Returns the run's folder."""
    tmp = pathlib.Path(tempfile.mkdtemp(dir=runs_root()))
    brief = tmp / "b.md"
    brief.write_text("## Opening\n\nHi\n\n## Player\n\nYou want a deck.\n" + ("\n## Start\n\nrats\n" if start else ""))
    put(tmp / "starts" / "rats", start or {})
    turn_after_turn = iter(turns)
    replies = iter(["ok"] * (len(turns) - 1) + [runner.END])
    real = runner.deckwright_turn, runner.stand_in_turn, runner.STARTS_DIR
    runner.deckwright_turn = lambda message, session, first, arm, cwd, memory: next(turn_after_turn)(cwd)
    runner.stand_in_turn = lambda *a: {"type": "result", "result": next(replies)}
    runner.STARTS_DIR = tmp / "starts"
    try:
        runner.run(brief, "skill", tmp / "out", 10)
    finally:
        runner.deckwright_turn, runner.stand_in_turn, runner.STARTS_DIR = real
    return tmp / "out"


def recorded(folder):
    return {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}


SAID = [{"type": "result", "result": "Saved. Next?"}]


def test_the_runner_records_every_deck_json_and_ledger_after_each_exchange_and_nothing_else():
    def first(ws):
        put(
            ws,
            {
                **deck_folder(deck_json()),
                "brawl-rats/index.html": "<html></html>",
                "brawl-rats/cards/a.jpg": b"\xff\xd8\xff",
                "brawl-rats.html": "<html></html>",
                "notes.md": "x",
                "older/decks/brawl-elves/deck.json": deck_json(theme="Elves"),
                ".claude/brawl-x/deck.json": deck_json(),
            },
        )
        return SAID

    def second(ws):
        (ws / "brawl-rats").rename(ws / "brawl-the-whorled-swarm")
        put(ws, {"brawl-the-whorled-swarm/deck.json": complete_deck(name="The Whorled Swarm")})
        return SAID

    out = play_recorded([first, second])
    assert {p.name for p in (out / "after").iterdir()} == {"0", "1"}, sorted((out / "after").iterdir())
    kept = ["older/decks/brawl-elves/deck.json"]
    assert recorded(out / "after" / "0") == {"brawl-rats/deck.json", "brawl-rats/LEDGER.md", *kept}, recorded(
        out / "after" / "0"
    )
    assert recorded(out / "after" / "1") == {
        "brawl-the-whorled-swarm/deck.json",
        "brawl-the-whorled-swarm/LEDGER.md",
        *kept,
    }, recorded(out / "after" / "1")
    assert "name" not in json.loads((out / "after" / "0" / "brawl-rats" / "deck.json").read_text()), (
        "after/0 holds the deck as a later exchange left it"
    )
    assert len(checks.Run(out).states) == 2, "the checks do not read the runner's record as one state an exchange"


def test_the_runner_records_the_start_as_copied_in():
    start = {"deck.json": deck_json(), "LEDGER.md": f"# Ledger\n{LEDGER_LINE}\n"}

    def adds_a_card(ws):
        put(ws, {"deck/deck.json": deck_json([WICK, deck_card("Rat Colony"), deck_card("Infernal Grasp")])})
        return SAID

    out = play_recorded([adds_a_card], start=start)
    assert recorded(out / "after" / "start") == {"deck/deck.json", "deck/LEDGER.md"}, recorded(out / "after" / "start")
    assert json.loads((out / "after" / "start" / "deck" / "deck.json").read_text()) == start["deck.json"], (
        "after/start is not the start as it was copied in"
    )
    assert "Infernal Grasp" in (out / "after" / "0" / "deck" / "deck.json").read_text(), (
        "after/0 is not the deck after it"
    )


def test_the_runner_records_an_exchange_that_leaves_no_deck_folder_as_empty():
    def first(ws):
        put(ws, deck_folder(deck_json()))
        return SAID

    def second(ws):
        shutil.rmtree(ws / "brawl-rats")
        return SAID

    def third(ws):
        put(ws, deck_folder(deck_json(), folder="brawl-rats-2"))
        return SAID

    out = play_recorded([first, second, third])
    assert (out / "after" / "1").is_dir(), (
        f"the exchange that removed the folder has no after/1: {recorded(out / 'after')}"
    )
    assert recorded(out / "after" / "1") == set(), recorded(out / "after" / "1")
    states = checks.Run(out).states
    assert states[1] == {}, f"the exchange that removed the folder reads as holding one: {sorted(states[1])}"


def test_the_runner_records_the_workspace_of_an_exchange_whose_turn_raised():
    def first(ws):
        put(ws, deck_folder(deck_json()))
        return SAID

    def times_out(ws):
        put(ws, {"brawl-rats/deck.json": deck_json([WICK, deck_card("Rat Colony"), deck_card("Infernal Grasp")])})
        raise TimeoutError

    out = play_recorded([first, times_out])
    assert json.loads((out / "run.json").read_text())["ended"] == "runner error: TimeoutError"
    saved = out / "after" / "1" / "brawl-rats" / "deck.json"
    assert saved.is_file(), f"the turn that raised left no after/1: {recorded(out / 'after')}"
    assert "Infernal Grasp" in saved.read_text(), "after/1 is not the deck as the turn that raised left it"
    traced = [json.loads(line) for line in (out / "trace.jsonl").read_text().splitlines()]
    assert [e["exchange"] for e in traced] == [0], f"the trace of exchange 0 was not kept: {traced}"


# ---------- S1: a save writes the folder; a publish only on asking for a link ----------


def test_s1_passes_a_pick_added_to_deck_json_and_ledger_with_no_publish():
    status, evidence = verdict(picked(), "S1", facts(**PICK_FACTS))
    assert status == "pass", evidence


def test_s1_fails_a_publish_the_player_never_asked_for():
    status, evidence = verdict(picked(trace=publish(1)), "S1", facts(**PICK_FACTS))
    assert status == "fail", f"published with no link asked for: {(status, evidence)}"
    assert "publish" in evidence.lower(), f"the evidence does not name the publish: {evidence}"


def test_s1_fails_a_pick_that_was_only_published():
    status, evidence = verdict(picked(after=BEFORE_PICK, trace=publish(1)), "S1", facts(**PICK_FACTS))
    assert status == "fail", f"the pick never reached deck.json: {(status, evidence)}"
    assert "Rat Colony" in evidence or "deck.json" in evidence, (
        f"the evidence does not name the unsaved pick: {evidence}"
    )


def test_s1_fails_a_pick_added_to_deck_json_but_not_to_the_ledger():
    status, evidence = verdict(picked(after={"brawl-rats": (deck_json(), ledger())}), "S1", facts(**PICK_FACTS))
    assert status == "fail", f"the pick has no ledger line: {(status, evidence)}"
    assert "LEDGER.md" in evidence, f"the evidence does not name the ledger: {evidence}"


def test_s1_fails_a_pick_whose_new_ledger_line_names_another_card():
    status, evidence = verdict(
        picked(after={"brawl-rats": (deck_json(), ledger(GRASP_LINE))}), "S1", facts(**PICK_FACTS)
    )
    assert status == "fail", f"the ledger gained a line, and not for Rat Colony: {(status, evidence)}"
    assert "LEDGER.md" in evidence, f"the evidence does not name the ledger: {evidence}"


def test_s1_counts_a_pick_of_a_card_already_in_the_deck_by_its_count():
    messages = [
        {"role": "player", "text": "Rats, three Rat Colony"},
        {"role": "deckwright", "text": "Three are in."},
        {"role": "player", "text": "Make it four"},
        {"role": "deckwright", "text": "Four now."},
    ]
    three = {"brawl-rats": (deck_json([deck_card("Rat Colony", 3)], fmt="standard"), ledger(LEDGER_LINE))}
    four = {"brawl-rats": (deck_json([deck_card("Rat Colony", 4)], fmt="standard"), ledger(LEDGER_LINE, LEDGER_LINE))}
    f = facts(format="standard", **PICK_FACTS)
    status, evidence = verdict(fake_run(messages, [], states=[three, four]), "S1", f)
    assert status == "pass", f"a fourth copy is a pick saved: {evidence}"
    still_three = {"brawl-rats": (three["brawl-rats"][0], ledger(LEDGER_LINE, LEDGER_LINE))}
    status, evidence = verdict(fake_run(messages, [], states=[three, still_three]), "S1", f)
    assert status == "fail", f"the count stayed at three: {(status, evidence)}"


def test_s1_fails_an_unsaved_pick_in_either_confirmation_of_one_message():
    # The reader may split one message's picks into two entries.
    f = facts(confirmations=[{"message": 2, "cards": ["Infernal Grasp"]}, {"message": 2, "cards": ["Rat Colony"]}])
    status, evidence = verdict(picked(), "S1", f)
    assert status == "fail", f"Infernal Grasp was never added, and S1 passed: {(status, evidence)}"


def test_s1_is_not_applicable_to_a_run_with_no_record_of_its_folder():
    status, evidence = verdict(fake_run(PICKED, [], workspace=deck_folder()), "S1", facts(**PICK_FACTS))
    assert (status, NO_RECORD in evidence) == ("n/a", True), (status, evidence)


def test_s1_fails_an_unasked_publish_in_a_run_with_no_record_of_its_folder():
    status, evidence = verdict(fake_run(PICKED, publish(1), workspace=deck_folder()), "S1", facts(**PICK_FACTS))
    assert status == "fail", f"publishes are read from the trace, which every run has: {(status, evidence)}"
    assert "publish" in evidence.lower(), f"the evidence does not name the publish: {evidence}"


LINK_ASKED = [
    {"role": "player", "text": "Rats with Wick; I'll take Rat Colony"},
    {"role": "deckwright", "text": "Rat Colony is in. Removal next?"},
    {"role": "player", "text": "Can I have a link to the deck?"},
    {"role": "deckwright", "text": "Here it is: https://claude.ai/artifact/aaa"},
    {"role": "player", "text": "Add Infernal Grasp, and update the link"},
    {"role": "deckwright", "text": "Infernal Grasp is in; the same link shows it."},
]
LINK_FACTS = {"confirmations": [{"message": 0, "cards": ["Rat Colony"]}, {"message": 4, "cards": ["Infernal Grasp"]}]}
LINK_STATES = [
    AFTER_PICK,
    AFTER_PICK,
    {
        "brawl-rats": (
            deck_json([WICK, deck_card("Rat Colony"), deck_card("Infernal Grasp")]),
            ledger(LEDGER_LINE, GRASP_LINE),
        )
    },
]


def test_s1_passes_publishes_to_one_artifact_once_the_player_asks_for_a_link():
    trace = publish(1, made="aaa") + publish(2, url="https://claude.ai/artifact/aaa")
    status, evidence = verdict(fake_run(LINK_ASKED, trace, states=LINK_STATES), "S1", facts(**LINK_FACTS))
    assert status == "pass", evidence


def test_s1_passes_a_refused_publish_when_the_build_goes_on():
    status, evidence = verdict(
        fake_run(LINK_ASKED, publish(1, refused=True), states=LINK_STATES), "S1", facts(**LINK_FACTS)
    )
    assert status == "pass", f"the publish failed and the next pick was saved: {evidence}"


def test_s1_fails_a_second_artifact_for_the_same_deck():
    trace = publish(1, made="aaa", code_link=True) + publish(2, made="bbb", code_link=True)
    status, evidence = verdict(fake_run(LINK_ASKED, trace, states=LINK_STATES), "S1", facts(**LINK_FACTS))
    assert status == "fail", f"the deck went to two artifacts: {(status, evidence)}"
    assert "bbb" in evidence, f"the evidence does not name the second artifact: {evidence}"


# ---------- S2: a round is shown as the packed file ----------

ROUND = [
    {"role": "player", "text": "Removal next"},
    {
        "role": "deckwright",
        "text": "Two removal spells are on offer; open brawl-rats.html to see them: "
        "1 Infernal Grasp, 2 Feed the Swarm.",
    },
]
ROUND_FACTS = {"offers": [{"message": 1, "cards": ["Infernal Grasp", "Feed the Swarm"]}]}
ON_OFFER = deck_json(offer=offer(group(None, ["Infernal Grasp", "Feed the Swarm"])))


def shown_round(reply=None, after=ON_OFFER, packed=True, more_calls=(), record=True):
    """The round of ROUND in a run whose folder held `after` once the round was shown;
    `record` False leaves the run with no record of its folder."""
    messages = [ROUND[0], {**ROUND[1], "text": reply or ROUND[1]["text"]}]
    trace = bash(PACK, 0, answer=f"{WORKSPACE}/brawl-rats.html") if packed else []
    trace += list(more_calls)
    states = [{"brawl-rats": (after, ledger(LEDGER_LINE))}] if record else None
    return fake_run(
        messages, trace, states=states, workspace=deck_folder(after, **{"brawl-rats.html": "<html></html>"})
    )


def test_s2_passes_a_round_saved_as_offer_packed_and_named():
    status, evidence = verdict(shown_round(), "S2", facts(**ROUND_FACTS))
    assert status == "pass", evidence


def test_s2_fails_a_round_never_packed():
    status, evidence = verdict(shown_round(packed=False), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"pack.py never ran for the round: {(status, evidence)}"
    assert "pack.py" in evidence, f"the evidence does not name pack.py: {evidence}"


def test_s2_fails_a_round_whose_pack_failed():
    failed = bash(PACK, 0, answer=f"Exit code 1\npack.py: no deck.json in {WORKSPACE}/brawl-rats")
    status, evidence = verdict(shown_round(packed=False, more_calls=failed), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"pack.py failed, and the round counted as packed: {(status, evidence)}"


def test_s2_fails_a_round_whose_folder_holds_no_offer_after_it():
    status, evidence = verdict(shown_round(after=deck_json()), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"deck.json held no offer after the round: {(status, evidence)}"
    assert "offer" in evidence, f"the evidence does not name the missing offer: {evidence}"


def test_s2_fails_a_round_whose_offer_holds_no_cards():
    passed = []
    for empty in (None, {}, offer(), offer(group(None, []))):
        status, evidence = verdict(shown_round(after=deck_json(offer=empty)), "S2", facts(**ROUND_FACTS))
        if status != "fail" or "offer" not in evidence:
            passed.append((empty, status))
    assert not passed, f"an offer with no cards counts as putting the round on offer: {passed}"


def round_then(reply, cards):
    """ROUND written and packed in exchange 0, then a reply in exchange 1 that the reader
    saw offer `cards`, packed again with deck.json still holding ROUND's offer."""
    messages = [*ROUND, {"role": "player", "text": "Next?"}, {"role": "deckwright", "text": reply}]
    trace = bash(PACK, 0, answer=f"{WORKSPACE}/brawl-rats.html") + bash(PACK, 1, answer=f"{WORKSPACE}/brawl-rats.html")
    state = {"brawl-rats": (ON_OFFER, ledger(LEDGER_LINE))}
    r = fake_run(messages, trace, states=[state, state])
    return r, facts(offers=[*ROUND_FACTS["offers"], {"message": 3, "cards": cards}])


def test_s2_fails_a_new_round_left_unwritten_while_the_last_rounds_offer_stays():
    r, f = round_then(
        "Card draw on offer; open brawl-rats.html: Night's Whisper, Sign in Blood.",
        ["Night's Whisper", "Sign in Blood"],
    )
    status, evidence = verdict(r, "S2", f)
    assert status == "fail", f"the card draw round was never written to deck.json: {(status, evidence)}"


def test_s2_passes_a_round_shown_again_unchanged():
    r, f = round_then(
        "Still on offer in brawl-rats.html: Infernal Grasp, Feed the Swarm.", ["Infernal Grasp", "Feed the Swarm"]
    )
    status, evidence = verdict(r, "S2", f)
    assert status == "pass", f"the same round, shown again from the same offer: {(status, evidence)}"


def test_s2_passes_an_offer_holding_half_the_cards_shown_one_by_a_face():
    after = deck_json(offer=offer(group(None, ["Fell the Profane // Fell Mire", "Infernal Grasp"])))
    reply = "On offer in brawl-rats.html: Fell the Profane, Night's Whisper."
    f = facts(offers=[{"message": 1, "cards": ["Fell the Profane", "Night's Whisper"]}])
    status, evidence = verdict(shown_round(reply, after=after), "S2", f)
    assert status == "pass", f"one of the two cards shown is on offer, by its first face: {(status, evidence)}"


def test_s2_fails_a_round_whose_reply_does_not_name_the_packed_file():
    reply = "Two removal spells: 1 Infernal Grasp, 2 Feed the Swarm."
    status, evidence = verdict(shown_round(reply), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"the player was never given the packed file: {(status, evidence)}"
    assert "brawl-rats.html" in evidence or "packed" in evidence, (
        f"the evidence does not name the packed file: {evidence}"
    )


def test_s2_fails_a_card_name_linked_to_scryfall():
    reply = (
        "On offer in brawl-rats.html: 1 [Infernal Grasp](https://scryfall.com/card/2xm/107/infernal-grasp), "
        "2 Feed the Swarm."
    )
    status, evidence = verdict(shown_round(reply), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"a card name links to Scryfall (#29): {(status, evidence)}"
    assert "scryfall.com" in evidence, f"the evidence does not name the link: {evidence}"


def test_s2_fails_a_card_picture_shown_alone():
    sid = scryfall_id("Infernal Grasp")
    reply = f"On offer in brawl-rats.html: 1 Infernal Grasp ![Infernal Grasp](brawl-rats/cards/{sid}.jpg), 2 Feed the Swarm."
    status, evidence = verdict(shown_round(reply), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"a card picture went to the chat alone (#29): {(status, evidence)}"
    assert f"{sid}.jpg" in evidence or "Infernal Grasp" in evidence, (
        f"the evidence does not name the picture: {evidence}"
    )


def test_s2_fails_a_card_picture_in_an_img_tag():
    sid = scryfall_id("Infernal Grasp")
    reply = f'On offer in brawl-rats.html: 1 Infernal Grasp <img src="brawl-rats/cards/{sid}.jpg">, 2 Feed the Swarm.'
    status, evidence = verdict(shown_round(reply), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"a card picture went to the chat as an <img>: {(status, evidence)}"
    assert f"{sid}.jpg" in evidence, f"the evidence does not name the picture: {evidence}"


def test_s2_fails_any_scryfall_url_in_a_reply():
    urls = [
        "https://api.scryfall.com/cards/named?exact=Infernal%20Grasp",
        "api.scryfall.com/cards/2xm/107",
        "https://scryfall.com/search?q=infernal+grasp",
        "https://svgs.scryfall.io/card-symbols/B.svg",
    ]
    passed = []
    for url in urls:
        reply = f"On offer in brawl-rats.html: 1 Infernal Grasp ({url}), 2 Feed the Swarm."
        status, evidence = verdict(shown_round(reply), "S2", facts(**ROUND_FACTS))
        if status != "fail" or url not in evidence:
            passed.append((url, status))
    assert not passed, f"Scryfall URLs in a reply that S2 does not fail on by name: {passed}"


def test_s2_passes_a_mention_of_the_site_which_is_no_link():
    reply = ROUND[1]["text"] + " I looked them up on Scryfall.com."
    status, evidence = verdict(shown_round(reply), "S2", facts(**ROUND_FACTS))
    assert status == "pass", f"naming the site is no link: {(status, evidence)}"


def test_s2_leaves_a_file_sent_into_chat_to_the_runner_which_disallows_it():
    sent = tool_call("SendUserFile", {"files": [f"{WORKSPACE}/brawl-rats/cards/{scryfall_id('Infernal Grasp')}.jpg"]})
    assert "SendUserFile" in runner.DECKWRIGHT_DISALLOWED, "the runner lets Deckwright send a file into the chat"
    status, evidence = verdict(shown_round(more_calls=sent), "S2", facts(**ROUND_FACTS))
    assert status == "pass", f"S2 still judges a SendUserFile call, which no run can make: {(status, evidence)}"


def saved_and_replied(reply, packed=True):
    """PICKED, packed in both exchanges, its first reply naming the packed file and the
    second, after the pick is saved, `reply`; the reader saw no card offered."""
    messages = [
        PICKED[0],
        {"role": "deckwright", "text": "Wick leads; open brawl-rats.html. Token makers next?"},
        PICKED[2],
        {"role": "deckwright", "text": reply},
    ]
    trace = bash(PACK, 0, answer=f"{WORKSPACE}/brawl-rats.html")
    if packed:
        trace += bash(PACK, 1, answer=f"{WORKSPACE}/brawl-rats.html")
    return fake_run(messages, trace + publish(1), states=[BEFORE_PICK, AFTER_PICK])


def test_s2_passes_every_save_whose_reply_names_the_packed_file():
    r = saved_and_replied("Rat Colony is in; open brawl-rats.html, or https://claude.ai/artifact/aaa. Removal next?")
    status, evidence = verdict(r, "S2", facts(**PICK_FACTS))
    assert status == "pass", f"both saves were packed and named in their replies: {(status, evidence)}"


def test_s2_fails_a_save_whose_reply_gives_only_the_link():
    # From the round of 2026-11-13: link-mid-build's exchange 2 saved, and its reply gave only the artifact link.
    r = saved_and_replied("Rat Colony is in. Here is the link: https://claude.ai/artifact/aaa")
    status, evidence = verdict(r, "S2", facts(**PICK_FACTS))
    assert status == "fail", f"the save's reply never named the packed file: {(status, evidence)}"
    assert "exchange 1" in evidence and "brawl-rats.html" in evidence, (
        f"the evidence does not name the exchange and the file: {evidence}"
    )


def test_s2_fails_a_save_never_packed():
    r = saved_and_replied("Rat Colony is in. Removal next?", packed=False)
    status, evidence = verdict(r, "S2", facts(**PICK_FACTS))
    assert status == "fail", f"the save of exchange 1 was never packed for the player: {(status, evidence)}"
    assert "exchange 1" in evidence, f"the evidence does not name the exchange: {evidence}"


def test_s2_is_not_applicable_to_a_run_with_no_record_of_its_folder():
    status, evidence = verdict(shown_round(record=False), "S2", facts(**ROUND_FACTS))
    assert (status, NO_RECORD in evidence) == ("n/a", True), (status, evidence)


def test_s2_fails_a_scryfall_url_in_a_run_with_no_record_of_its_folder():
    reply = "On offer in brawl-rats.html: 1 Infernal Grasp (https://scryfall.com/search?q=grasp), 2 Feed the Swarm."
    status, evidence = verdict(shown_round(reply, record=False), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"the replies are in every run: {(status, evidence)}"
    assert "scryfall.com" in evidence, f"the evidence does not name the link: {evidence}"


PACKED_THEN_LISTED = f"{WORKSPACE}/brawl-rats.html\ncards\ndeck.json\nindex.html\nLEDGER.md"


def test_s2_passes_a_reply_naming_the_packed_file_though_a_later_step_lists_index_html():
    # From the round of 2026-11-13: pack.py printed the packed file, and an `ls` later in the chain printed index.html.
    chained = bash(f"{PACK} && cp brawl-rats.html out/ ; ls brawl-rats", 0, answer=PACKED_THEN_LISTED)
    status, evidence = verdict(shown_round(packed=False, more_calls=chained), "S2", facts(**ROUND_FACTS))
    assert status == "pass", f"the reply names brawl-rats.html, the file pack.py printed: {(status, evidence)}"


def test_s2_fails_a_reply_naming_index_html_for_the_packed_file():
    chained = bash(f"{PACK} && cp brawl-rats.html out/ ; ls brawl-rats", 0, answer=PACKED_THEN_LISTED)
    reply = ROUND[1]["text"].replace("brawl-rats.html", "index.html")
    status, evidence = verdict(shown_round(reply, packed=False, more_calls=chained), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"the packed file is brawl-rats.html, and the reply names index.html: {(status, evidence)}"
    assert "brawl-rats.html" in evidence, f"the evidence does not name the packed file: {evidence}"


def test_s2_takes_the_last_printed_page_other_than_index_html_when_pack_py_is_given_no_folder():
    unnamed = bash(
        "python3 /plugins/deckwright/skills/deckwright/page/pack.py; ls brawl-rats", 0, answer=PACKED_THEN_LISTED
    )
    status, evidence = verdict(shown_round(packed=False, more_calls=unnamed), "S2", facts(**ROUND_FACTS))
    assert status == "pass", f"brawl-rats.html is the last page printed that is not index.html: {(status, evidence)}"


def swap(name, out):
    """A review swap as the maybeboard holds it: `name` in for `out`."""
    return {
        "scryfall_id": scryfall_id(name),
        "name": name,
        "kind": "swap",
        "out": out,
        "why": f"{name} answers more than {out}.",
        "bends": None,
    }


SWAPS_SAVED = deck_json(maybeboard=[swap("Infernal Grasp", "Rat Colony"), swap("Feed the Swarm", "Rat Colony")])
SWAP_REPLY = (
    "Two swaps are on the maybeboard; open brawl-rats.html: Infernal Grasp in for Rat Colony, "
    "Feed the Swarm in for Rat Colony."
)


def test_s2_passes_review_swaps_saved_on_the_maybeboard():
    status, evidence = verdict(shown_round(SWAP_REPLY, after=SWAPS_SAVED), "S2", facts(**ROUND_FACTS))
    assert status == "pass", (
        f"the swaps the review offered are on the maybeboard, which holds them: {(status, evidence)}"
    )


def test_s2_fails_review_swaps_the_maybeboard_held_before_the_exchange():
    messages = [
        ROUND[0],
        {"role": "deckwright", "text": SWAP_REPLY},
        {"role": "player", "text": "Other swaps?"},
        {
            "role": "deckwright",
            "text": "Two more; open brawl-rats.html: Night's Whisper in for Rat Colony, "
            "Sign in Blood in for Rat Colony.",
        },
    ]
    trace = bash(PACK, 0, answer=f"{WORKSPACE}/brawl-rats.html") + bash(PACK, 1, answer=f"{WORKSPACE}/brawl-rats.html")
    state = {"brawl-rats": (SWAPS_SAVED, ledger(LEDGER_LINE))}
    f = facts(offers=[*ROUND_FACTS["offers"], {"message": 3, "cards": ["Night's Whisper", "Sign in Blood"]}])
    status, evidence = verdict(fake_run(messages, trace, states=[state, state]), "S2", f)
    assert status == "fail", (
        f"exchange 1's swaps were never saved, and the maybeboard gained none: {(status, evidence)}"
    )
    assert "exchange 1" in evidence and "exchange 0" not in evidence, evidence


def test_s2_fails_review_swaps_saved_on_the_maybeboard_not_as_swaps():
    plain = [
        {k: v for k, v in swap(n, "Rat Colony").items() if k not in ("kind", "out")}
        for n in ("Infernal Grasp", "Feed the Swarm")
    ]
    status, evidence = verdict(shown_round(SWAP_REPLY, after=deck_json(maybeboard=plain)), "S2", facts(**ROUND_FACTS))
    assert status == "fail", f"the maybeboard gained cards, and no swap: {(status, evidence)}"


# ---------- S3: a round shows every step of the ladder ----------

CATEGORIES = [{"name": "Commander", "target": 1}, {"name": "Removal", "target": 8}, {"name": "Payoffs", "target": 8}]


def on_offer(offer_now=None):
    """A deck of the template's categories with `offer_now` on offer."""
    return deck_json(offer=offer_now, categories=CATEGORIES) if offer_now else deck_json(categories=CATEGORIES)


def offered_then_decided(offer_now):
    """A run whose round was on offer after exchange 0 and gone once decided in exchange 1."""
    return fake_run(
        [],
        [],
        states=[
            {"brawl-rats": (on_offer(offer_now), ledger(LEDGER_LINE))},
            {"brawl-rats": (on_offer(), ledger(LEDGER_LINE))},
        ],
    )


def ladder_round(
    offer_now, holds=True, evidence="Rats that remove (6), Cards that reward Rats (3), Other removal (40)"
):
    r = fake_run([], [], states=[{"brawl-rats": (on_offer(offer_now), ledger(LEDGER_LINE))}])
    return r, facts(ladder_steps_with_counts=fact(holds, evidence))


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


def test_s3_does_not_judge_a_headed_round_without_a_creature_type():
    two = offer(group("Found by otag:removal", ["Infernal Grasp"]), group("Found by o:destroy", ["Feed the Swarm"]))
    r, f = ladder_round(two, holds=None, evidence="")
    status, evidence = verdict(r, "S3", f)
    assert status == "n/a", f"no creature type was wanted, so no ladder: {(status, evidence)}"


def test_s3_does_not_judge_a_commander_offer_as_a_ladder():
    commanders = offer(group("Rat commanders", ["Wick, the Whorled Mind", "Rat Colony"]), category="Commander")
    r, f = ladder_round(commanders, evidence="every round showed three steps")
    status, evidence = verdict(r, "S3", f)
    assert status == "pass", f"a commander offer is no category's round: {(status, evidence)}"


def after_a_round(earlier, offer_now, evidence):
    """A run whose folder held `earlier` on offer after exchange 0 and `offer_now` after exchange 1."""
    r = fake_run(
        [],
        [],
        states=[
            {"brawl-rats": (on_offer(earlier), ledger(LEDGER_LINE))},
            {"brawl-rats": (on_offer(offer_now), ledger(LEDGER_LINE))},
        ],
    )
    return r, facts(ladder_steps_with_counts=fact(True, evidence))


def test_s3_passes_a_further_round_of_one_step_with_its_heading_and_count():
    said = "three steps in the first round; then more Rats that remove on the player's word"
    one_step = offer(group("Rats that remove", [f"Rat {n}" for n in range(1, 6)], total=14, suggested=("Rat 1",)))
    r, f = after_a_round(ladder(), one_step, said)
    status, evidence = verdict(r, "S3", f)
    assert status == "pass", f"a further round of one step, shown on the player's word: {evidence}"
    r, f = after_a_round(ladder(), offer(group("Rats that remove", [f"Rat {n}" for n in range(1, 6)])), said)
    status, evidence = verdict(r, "S3", f)
    assert status == "fail", f"a round of one step must still state its full count: {(status, evidence)}"


def test_s3_fails_a_round_of_one_step_with_no_earlier_three_step_round_of_its_category():
    one_step = offer(group("Rats that remove", [f"Rat {n}" for n in range(1, 9)], total=8, suggested=("Rat 1",)))
    r, f = ladder_round(one_step, evidence="...")
    status, evidence = verdict(r, "S3", f)
    assert status == "fail", f"a first round of one step stood for the ladder: {(status, evidence)}"
    r, f = after_a_round({**ladder(), "category": "Payoffs"}, one_step, "...")
    status, evidence = verdict(r, "S3", f)
    assert status == "fail", f"the three-step round before it was of Payoffs, not Removal: {(status, evidence)}"


def test_s3_judges_a_round_gone_from_the_deck_by_the_end():
    f = facts(ladder_steps_with_counts=fact(True, "three steps, each with its count"))
    status, evidence = verdict(offered_then_decided(ladder(sizes=(5, 5), totals=(6, 3))), "S3", f)
    assert status == "fail", f"the round of two steps was on offer after exchange 0: {(status, evidence)}"


def test_s3_is_not_applicable_to_a_run_with_no_record_of_its_folder():
    r = fake_run([], [], workspace=deck_folder(on_offer(ladder(sizes=(5, 5), totals=(6, 3)))))
    status, evidence = verdict(r, "S3", facts(ladder_steps_with_counts=fact(True, "three steps")))
    assert (status, NO_RECORD in evidence) == ("n/a", True), (status, evidence)


def test_s3_passes_a_round_of_six_to_fourteen_cards():
    for sizes in ((2, 2, 2), (5, 5, 4)):
        r, f = ladder_round(ladder(sizes=sizes))
        status, evidence = verdict(r, "S3", f)
        assert status == "pass", f"{sum(sizes)} cards is about ten: {(status, evidence)}"


def test_s3_fails_a_round_of_five_cards():
    r, f = ladder_round(ladder(sizes=(2, 2, 1)))
    status, evidence = verdict(r, "S3", f)
    assert status == "fail", f"5 cards on offer in one round: {(status, evidence)}"
    assert "5" in evidence, f"the evidence does not give the round's size: {evidence}"


def test_s3_passes_a_round_shrinking_as_picks_come_off():
    r, f = after_a_round(ladder(), ladder(sizes=(2, 1, 1)), "three steps, each with its count")
    status, evidence = verdict(r, "S3", f)
    assert status == "pass", f"every card of the 4 left was in the round of 10 before it: {(status, evidence)}"


def test_s3_judges_the_size_of_a_round_with_a_card_the_one_before_did_not_offer():
    grown = ladder(sizes=(2, 1, 1))
    grown["groups"][2]["cards"] = [offered("Infernal Grasp")]
    r, f = after_a_round(ladder(), grown, "three steps, each with its count")
    status, evidence = verdict(r, "S3", f)
    assert status == "fail", f"Infernal Grasp is new, so the round of 4 is a new round: {(status, evidence)}"
    assert "4" in evidence, f"the evidence does not give the round's size: {evidence}"


def test_s3_does_not_judge_the_size_of_the_lands_round():
    lands = {**ladder(sizes=(8, 8, 8)), "category": "Lands"}
    deck = deck_json(offer=lands, categories=[*CATEGORIES, {"name": "Lands", "target": 35}])
    r = fake_run([], [], states=[{"brawl-rats": (deck, ledger(LEDGER_LINE))}])
    status, evidence = verdict(r, "S3", facts(ladder_steps_with_counts=fact(True, "three steps, each with its count")))
    assert status == "pass", f"the Lands round of 24 is not held to about ten: {(status, evidence)}"


def test_the_examples_offer_is_a_ladder_s3_passes():
    repo = pathlib.Path(__file__).resolve().parent.parent
    example = json.loads((repo / "plugins/deckwright/skills/deckwright/page/deck.example.json").read_text())
    r = fake_run([], [], states=[{"brawl-rats": (example, ledger(LEDGER_LINE))}])
    status, evidence = verdict(r, "S3", facts(ladder_steps_with_counts=fact(True, "three steps, each with its count")))
    assert status == "pass", f"the example the skill copies offers a round S3 fails: {evidence}"


# ---------- S4: a round marks the tutor's picks ----------


def marked_round_facts(marked=True, taken=True):
    return facts(
        suggestions_marked=fact(marked, "Suggested: 1 and 3"),
        you_pick_takes_the_suggested=fact(taken, "Player: you pick. Tutor: taking 1 and 3"),
    )


def test_s4_passes_marked_suggestions_taken_on_you_pick():
    r, _ = ladder_round(ladder())
    status, evidence = verdict(r, "S4", marked_round_facts())
    assert status == "pass", evidence


def test_s4_fails_you_pick_answered_with_a_new_suggestion():
    # The first real build: "go with your suggestion", answered "I hadn't given a suggestion for this one yet" (#41).
    f = facts(
        suggestions_marked=fact(True, "Suggested: 1 and 3"),
        you_pick_takes_the_suggested=fact(False, "I hadn't given a suggestion for this one yet, so here it is."),
    )
    r, _ = ladder_round(ladder())
    status, evidence = verdict(r, "S4", f)
    assert status == "fail", (status, evidence)
    assert "hadn't given a suggestion" in evidence, f"the evidence does not quote the reply: {evidence}"


def test_s4_fails_a_saved_round_with_no_suggested_card():
    r, _ = ladder_round(ladder(suggested=()))
    status, evidence = verdict(r, "S4", marked_round_facts())
    assert status == "fail", f"the round on offer marks no card suggested: {(status, evidence)}"
    assert "Removal" in evidence, f"the evidence does not name the round: {evidence}"


def test_s4_is_not_applicable_when_no_round_was_asked_for():
    r, _ = ladder_round(None)
    status, evidence = verdict(r, "S4", facts())
    assert status == "n/a", (status, evidence)


def test_s4_asks_no_suggested_mark_or_reason_of_a_commander_offer():
    commanders = offer(group(None, ["Wick, the Whorled Mind", "Marrow-Gnawer"]), category="Commander")
    for c in checks.offered_cards(commanders):
        del c["reason"]
    r, _ = ladder_round(commanders)
    status, evidence = verdict(r, "S4", facts())
    assert status != "fail", f"a commander offer is not a category's round, and fails S4 for marking none: {evidence}"


def test_s4_fails_a_card_of_a_round_on_offer_without_a_reason():
    failed = []
    for unreasoned in ({"reason": ""}, {"reason": None}, None):
        round_ = ladder()
        card_ = round_["groups"][1]["cards"][0]
        if unreasoned is None:
            del card_["reason"]
        else:
            card_.update(unreasoned)
        r, _ = ladder_round(round_)
        status, evidence = verdict(r, "S4", marked_round_facts())
        if status != "fail" or card_["name"] not in evidence:
            failed.append((unreasoned, status, evidence))
    assert not failed, f"a card on offer with no reason, and S4 does not fail it by name: {failed}"


def test_s4_fails_a_reply_the_reader_saw_mark_nothing():
    f = facts(
        suggestions_marked=fact(False, "Here are ten removal spells; which do you want?"),
        you_pick_takes_the_suggested=FACT_NULL,
    )
    r, _ = ladder_round(ladder())
    status, evidence = verdict(r, "S4", f)
    assert status == "fail", f"the reply marked no card, though the saved round does: {(status, evidence)}"
    assert "which do you want" in evidence, f"the evidence does not quote the reply: {evidence}"


def reader_entry(name):
    """The reader prompt's entry for the fact `name`, its lines joined."""
    entry = checks.READER_PROMPT.split(f"- {name}:", 1)[1].split("\n- ", 1)[0]
    return " ".join(entry.split())


def test_s4_asks_the_reader_only_whether_the_reply_marks_cards():
    assert "suggestions_marked" in checks.READER_SCHEMA["properties"], "the reader is not asked for suggestions_marked"
    gone = [
        n
        for n in ("suggestions_marked_with_reasons",)
        if n in checks.READER_SCHEMA["properties"] or n in checks.READER_PROMPT
    ]
    assert not gone, f"the reader is still asked for: {gone}"
    assert "reason" not in reader_entry("suggestions_marked"), (
        f"the reasons are the saved round's, and the reader still judges them: {reader_entry('suggestions_marked')}"
    )


def test_s4_asks_the_reader_whether_you_pick_takes_the_marked_cards_in_the_decided_words():
    wanted = (
        "when the player, after a round with marked cards, leaves the choice to the assistant ('you pick', "
        "'go with your suggestions', 'yes, all of those'), does the assistant take exactly the marked cards of "
        "that round? 'Just fill in the rest' asks for the remaining rounds with marks and is not itself leaving "
        "the choice; judge the answer that follows those rounds. null if the player never did."
    )
    said = reader_entry("you_pick_takes_the_suggested")
    assert said == wanted, f"the reader is asked: {said}"


def test_s4_judges_a_round_gone_from_the_deck_by_the_end():
    status, evidence = verdict(offered_then_decided(ladder(suggested=())), "S4", marked_round_facts())
    assert status == "fail", f"the round marking no card was on offer after exchange 0: {(status, evidence)}"
    assert "Removal" in evidence, f"the evidence does not name the round: {evidence}"


def test_s4_is_not_applicable_to_a_run_with_no_record_of_its_folder():
    r = fake_run([], [], workspace=deck_folder(on_offer(ladder(suggested=()))))
    status, evidence = verdict(r, "S4", marked_round_facts())
    assert (status, NO_RECORD in evidence) == ("n/a", True), (status, evidence)


# ---------- S5: crossover printings are marked and named as printed ----------

ASHCOAT = "Ashcoat of the Shadow Swarm"
ASHCOAT_PRINTED = "Splinter of the Shadows"


def crossover_printing(name, flavor_name=None, faces=None):
    printing = {"id": scryfall_id(name), "name": name, "games": ["arena"], "promo_types": ["universesbeyond"]}
    if flavor_name:
        printing["flavor_name"] = flavor_name
    if faces:
        printing["card_faces"] = faces
    return printing


ASHCOAT_PRINTING = {scryfall_id(ASHCOAT): crossover_printing(ASHCOAT, ASHCOAT_PRINTED)}


def crossover_offer(*marked):
    shown = offer(group(None, ["Infernal Grasp"]), category="Payoffs")
    shown["groups"][0]["cards"] += marked
    return shown


def crossover_round(*marked, holds=True, said="Any limits, for example sets, or crossover cards?"):
    r = fake_run([], [], states=[{"brawl-rats": (on_offer(crossover_offer(*marked)), ledger(LEDGER_LINE))}])
    return r, facts(limits_question_names_crossover=fact(holds, said))


def test_s5_passes_a_crossover_printing_marked_with_its_printed_name():
    r, f = crossover_round(offered(ASHCOAT, crossover=True, printed_name=ASHCOAT_PRINTED))
    status, evidence = verdict(r, "S5", f, ASHCOAT_PRINTING)
    assert status == "pass", evidence


def test_s5_passes_a_two_faced_crossover_named_by_its_first_face():
    name = "Rat Front // Rat Back"
    printing = crossover_printing(
        name, faces=[{"name": "Rat Front", "flavor_name": "Shredder's Rat"}, {"name": "Rat Back"}]
    )
    r, f = crossover_round(offered(name, crossover=True, printed_name="Shredder's Rat"))
    status, evidence = verdict(r, "S5", f, {scryfall_id(name): printing})
    assert status == "pass", f"a two-faced card's printed name is on its first face: {evidence}"


def test_s5_fails_a_crossover_printing_offered_unmarked():
    # The first real build: Ashcoat was shown as Splinter of the Shadows, unmarked (#42).
    r, f = crossover_round(offered(ASHCOAT))
    status, evidence = verdict(r, "S5", f, ASHCOAT_PRINTING)
    assert status == "fail", (status, evidence)
    assert ASHCOAT in evidence, f"the evidence does not name the card: {evidence}"


def test_s5_fails_a_printed_name_that_is_not_the_printings_flavor_name():
    r, f = crossover_round(offered(ASHCOAT, crossover=True, printed_name=ASHCOAT))
    status, evidence = verdict(r, "S5", f, ASHCOAT_PRINTING)
    assert status == "fail", f"Arena prints it as Splinter of the Shadows: {(status, evidence)}"
    assert ASHCOAT in evidence, f"the evidence does not name the card: {evidence}"


def test_s5_fails_a_limits_question_that_leaves_out_crossover_cards():
    r, f = crossover_round(holds=False, said="Any limits on sets or cards to avoid?")
    status, evidence = verdict(r, "S5", f)
    assert status == "fail", (status, evidence)
    assert "cards to avoid" in evidence, f"the evidence does not quote the question: {evidence}"


def test_s5_fails_a_crossover_printing_arena_does_not_print():
    paper_only = {**crossover_printing(ASHCOAT, ASHCOAT_PRINTED), "games": ["paper"]}
    r, f = crossover_round(offered(ASHCOAT, crossover=True, printed_name=ASHCOAT_PRINTED))
    status, evidence = verdict(r, "S5", f, {scryfall_id(ASHCOAT): paper_only})
    assert status == "fail", f"the page would show a printing Arena never prints: {(status, evidence)}"
    assert ASHCOAT in evidence, f"the evidence does not name the card: {evidence}"


def test_s5_judges_a_round_gone_from_the_deck_by_the_end():
    f = facts(limits_question_names_crossover=fact(True, "e.g. crossover cards"))
    status, evidence = verdict(offered_then_decided(crossover_offer(offered(ASHCOAT))), "S5", f, ASHCOAT_PRINTING)
    assert status == "fail", f"Ashcoat was on offer unmarked after exchange 0: {(status, evidence)}"
    assert ASHCOAT in evidence, f"the evidence does not name the card: {evidence}"


def commander_in_the_deck(**marks):
    """A run whose last state holds Ashcoat as the commander, with `marks` on its card."""
    deck = deck_json([{**deck_card(ASHCOAT, category="Commander"), **marks}, deck_card("Rat Colony")])
    return fake_run([], [], states=[{"brawl-rats": (deck, ledger(LEDGER_LINE))}])


def test_s5_does_not_judge_the_marks_of_a_card_in_the_deck():
    # The page shows no mark on a deck card, and the skill asks for none.
    r = commander_in_the_deck()
    f = facts(limits_question_names_crossover=fact(True, "e.g. crossover cards"))
    status, evidence = verdict(r, "S5", f, ASHCOAT_PRINTING)
    assert status != "fail", f"no crossover card was on offer, only one in the deck: {(status, evidence)}"


def test_s5_is_not_applicable_to_a_run_with_no_record_of_its_folder():
    r = fake_run([], [], workspace=deck_folder(on_offer(crossover_offer(offered(ASHCOAT)))))
    f = facts(limits_question_names_crossover=fact(True, "e.g. crossover cards"))
    status, evidence = verdict(r, "S5", f, ASHCOAT_PRINTING)
    assert (status, NO_RECORD in evidence) == ("n/a", True), (status, evidence)


# ---------- S6 to S11: what the reader reads ----------


def reader_verdict(key, fact_name, holds, said, fmt="brawl", workspace=None):
    r = fake_run([], [], workspace=workspace or deck_folder())
    return verdict(r, key, facts(format=fmt, **{fact_name: fact(holds, said)}))


def test_s6_passes_a_commander_chosen_before_colours():
    status, evidence = reader_verdict("S6", "commander_before_colours", True, "Which commander? ... Wick sets black")
    assert status == "pass", evidence


def test_s6_fails_colours_asked_before_the_commander_in_brawl():
    # The first real build: "which colours do you want the deck to be?", answered "we decide on the commander first" (#43).
    status, evidence = reader_verdict(
        "S6", "commander_before_colours", False, "which colours do you want the deck to be?"
    )
    assert status == "fail", (status, evidence)
    assert "which colours" in evidence, evidence


def test_s6_is_not_applicable_in_standard():
    status, evidence = reader_verdict("S6", "commander_before_colours", None, "", fmt="standard")
    assert status == "n/a", f"Standard has no commander: {(status, evidence)}"


def test_s7_passes_a_set_count_that_says_any_printing_counts():
    status, evidence = reader_verdict(
        "S7", "set_count_says_any_printing", True, "7 Rats with a Bloomburrow printing, counting reprints"
    )
    assert status == "pass", evidence


def test_s7_fails_a_set_count_read_from_one_printing():
    # The first real build missed Lightshell Duo, "filed under a later reprint" (#44).
    status, evidence = reader_verdict("S7", "set_count_says_any_printing", False, "all six from Bloomburrow")
    assert status == "fail", (status, evidence)
    assert "all six from Bloomburrow" in evidence, evidence


def test_s7_is_not_applicable_without_a_set_criterion():
    status, evidence = reader_verdict("S7", "set_count_says_any_printing", None, "")
    assert status == "n/a", (status, evidence)


# As standard-set-limit-template saved it in the round of 2026-11-13, as deck.example.json's
# limit is saved: a set is a criterion of kind `limit`, and no criterion kind names a set.
SET_LIMIT = {"kind": "limit", "text": "Only cards with a printing in Edge of Eternities (e:eoe)"}


def test_s7_judges_a_set_limit_saved_as_a_limit_by_the_reader_alone():
    deck = deck_json(criteria=[{"kind": "format", "text": "Standard on Arena"}, SET_LIMIT], fmt="standard")
    status, evidence = reader_verdict(
        "S7",
        "set_count_says_any_printing",
        False,
        "all six from Edge of Eternities",
        fmt="standard",
        workspace=deck_folder(deck, "standard-spacecraft"),
    )
    assert status == "fail", f"no criterion has kind set, and S7 left the reader's no unjudged: {(status, evidence)}"
    status, evidence = reader_verdict(
        "S7",
        "set_count_says_any_printing",
        True,
        "counts any printing in e:eoe",
        fmt="standard",
        workspace=deck_folder(deck, "standard-spacecraft"),
    )
    assert status == "pass", (status, evidence)


def test_s7_asks_the_reader_about_set_counts_in_the_decided_words():
    wanted = (
        "whenever the assistant counts cards from a set the player named as a limit, does it say a card counts "
        "when any of its printings is in that set? Counts of crossover printings, types or the whole pool are "
        "not set counts. null if no set was named or no such count was made."
    )
    said = reader_entry("set_count_says_any_printing")
    assert said == wanted, f"the reader is asked: {said}"


def test_s9_passes_terms_explained_where_first_used():
    status, evidence = reader_verdict(
        "S9", "terms_explained_where_first_used", True, "Recursion (bringing cards back from the graveyard)"
    )
    assert status == "pass", evidence


def test_s9_fails_a_category_name_left_unexplained():
    # The first real build: "Recursion" was accepted in the template; five categories later, "what is recursion?" (#46).
    status, evidence = reader_verdict("S9", "terms_explained_where_first_used", False, "Template: ... Recursion 8")
    assert status == "fail", (status, evidence)
    assert "Recursion" in evidence, evidence


def test_s9_tells_the_reader_what_counts_as_explained_and_as_a_game_term_in_the_decided_words():
    wanted = (
        "A term counts as explained if its own sentence or the one just before says what it does. Search and "
        "tool words (a Scryfall tag) are not game terms. Evergreen keywords (flying, lifelink, vigilance) are "
        "game terms."
    )
    said = reader_entry("terms_explained_where_first_used")
    assert said.endswith(wanted), f"the reader is asked: {said}"


def test_s11_passes_a_complete_deck_with_handbook_and_scenes_unasked():
    deck = complete_deck(
        name="The Whorled Swarm",
        handbook=[{"title": "How it wins", "blocks": []}],
        scenes=[{"title": "Every kill is a Rat", "steps": []}],
    )
    status, evidence = reader_verdict(
        "S11",
        "handbook_written_unasked",
        True,
        "Here is the handbook and two scenes.",
        workspace=deck_folder(deck, "brawl-the-whorled-swarm"),
    )
    assert status == "pass", evidence


def test_s11_fails_a_handbook_asked_about():
    # The first real build: "Do you want the handbook, or is the deck done?" (#48).
    deck = complete_deck(
        name="The Whorled Swarm",
        handbook=[{"title": "How it wins", "blocks": []}],
        scenes=[{"title": "Every kill is a Rat", "steps": []}],
    )
    status, evidence = reader_verdict(
        "S11",
        "handbook_written_unasked",
        False,
        "Do you want the handbook, or is the deck done?",
        workspace=deck_folder(deck, "brawl-the-whorled-swarm"),
    )
    assert status == "fail", (status, evidence)
    assert "Do you want the handbook" in evidence, evidence


def test_s11_fails_a_complete_deck_saved_without_a_handbook():
    status, evidence = reader_verdict(
        "S11",
        "handbook_written_unasked",
        True,
        "",
        workspace=deck_folder(complete_deck(name="The Whorled Swarm"), "brawl-the-whorled-swarm"),
    )
    assert status == "fail", f"a complete deck.json has no handbook and no scenes: {(status, evidence)}"
    assert "handbook" in evidence, f"the evidence does not name what is missing: {evidence}"


def test_s11_is_not_applicable_to_an_unfinished_deck():
    status, evidence = reader_verdict("S11", "handbook_written_unasked", None, "")
    assert status == "n/a", f"a deck of two cards is not complete: {(status, evidence)}"


# ---------- S8: every number about the deck comes from a script ----------

COUNTED = [{"role": "player", "text": "How many Rats now?"}, {"role": "deckwright", "text": "The deck has 31 Rats."}]
COUNT_FACTS = {"deck_counts_stated": [{"message": 1, "said": "31 Rats"}]}
COUNT_SCRIPT = (
    "python3 -c \"import json; d = json.load(open('brawl-rats/deck.json')); "
    "print(sum(c['count'] for c in d['cards'] if 'Rat' in c['copy']['type_line']))\""
)


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
    status, evidence = verdict(
        r, "S8", facts(deck_counts_stated=[{"message": 1, "said": "30 Rats"}, {"message": 3, "said": "31 Rats"}])
    )
    assert status == "fail", f"31 Rats was said in exchange 1 and counted in exchange 0: {(status, evidence)}"
    assert "31 Rats" in evidence and "30 Rats" not in evidence, evidence


def test_s8_fails_a_count_read_off_deck_json_by_eye():
    r = fake_run(COUNTED, bash("cat brawl-rats/deck.json", 0), workspace=deck_folder())
    status, evidence = verdict(r, "S8", facts(**COUNT_FACTS))
    assert status == "fail", f"cat is not a script: {(status, evidence)}"


def test_s8_fails_a_count_whose_exchange_ran_only_the_save_script():
    save = (
        "python3 - <<'EOF'\nimport json\nd = json.load(open('brawl-rats/deck.json'))\n"
        "d['cards'].append({'name': 'Rat Colony', 'count': 1})\njson.dump(d, open('brawl-rats/deck.json', 'w'))\nEOF"
    )
    r = fake_run(COUNTED, bash(save, 0), workspace=deck_folder())
    status, evidence = verdict(r, "S8", facts(**COUNT_FACTS))
    assert status == "fail", f"the only script saved deck.json and printed no count: {(status, evidence)}"
    assert "31 Rats" in evidence, f"the evidence does not quote the count: {evidence}"


def test_s8_fails_a_count_its_script_did_not_print():
    r = fake_run(COUNTED, bash(COUNT_SCRIPT, 0, answer="30"), workspace=deck_folder())
    status, evidence = verdict(r, "S8", facts(**COUNT_FACTS))
    assert status == "fail", f"the script printed 30 and the reply says 31 Rats: {(status, evidence)}"
    assert "31 Rats" in evidence, f"the evidence does not quote the count: {evidence}"


def test_s8_fails_a_count_its_script_printed_only_inside_a_file_name():
    script = (
        "python3 -c \"import json; d = json.load(open('brawl-rats/deck.json')); "
        "json.dump(d, open('brawl-rats/backup-31.json', 'w')); print('saved brawl-rats/backup-31.json')\""
    )
    r = fake_run(COUNTED, bash(script, 0, answer="saved brawl-rats/backup-31.json"), workspace=deck_folder())
    status, evidence = verdict(r, "S8", facts(**COUNT_FACTS))
    assert status == "fail", f"31 is part of a file name, not a count printed: {(status, evidence)}"
    assert "31 Rats" in evidence, f"the evidence does not quote the count: {evidence}"


def test_s8_fails_a_count_found_only_in_a_traceback():
    script = "python3 -c \"import json; d=json.load(open('brawl-rats/deck.json')); print(len(d['cards'])+x)\""
    crashed = (
        'Exit code 1\nTraceback (most recent call last):\n  File "<string>", line 1, in <module>\n'
        "NameError: name 'x' is not defined"
    )
    messages = [COUNTED[0], {"role": "deckwright", "text": "The deck has 1 card."}]
    r = fake_run(messages, bash(script, 0, answer=crashed), workspace=deck_folder())
    status, evidence = verdict(r, "S8", facts(deck_counts_stated=[{"message": 1, "said": "1 card in the deck"}]))
    assert status == "fail", (
        f"the script crashed, and its traceback's line 1 counted as printing 1: {(status, evidence)}"
    )


def test_s8_passes_a_count_printed_by_a_command_that_failed_at_a_later_step():
    # From the round of 2026-11-13: the shell reports a chain whose last step failed as an
    # error, and its first steps had run and printed.
    chain = "python3 pick.py brawl-rats/deck.json && python3 count.py brawl-rats/deck.json && python3 left.py"
    ran = tool_call("Bash", {"command": chain}, 0, answer="Exit code 1\npicked\n31\nTraceback: left.py", refused=True)
    status, evidence = verdict(fake_run(COUNTED, ran, workspace=deck_folder()), "S8", facts(**COUNT_FACTS))
    assert status == "pass", f"a command that exits 1 ran, and printed 31: {(status, evidence)}"


def test_s8_fails_a_count_no_output_holds_though_others_do():
    said = "the 65 nonland cards"
    messages = [COUNTED[0], {"role": "deckwright", "text": f"There are {said}."}]
    output = "curve {1: 4, 2: 26, 3: 13, 4: 11, 5: 7, 6: 4} avg 3.05 <=2 30"
    r = fake_run(messages, bash(COUNT_SCRIPT, 0, answer=output), workspace=deck_folder())
    status, evidence = verdict(r, "S8", facts(deck_counts_stated=[{"message": 1, "said": said}]))
    assert status == "fail", f"no 65 in what the script printed: {(status, evidence)}"


def test_s8_passes_a_count_of_zero_printed_as_a_missing_key():
    said = "Self-mill has 0 cards"
    messages = [COUNTED[0], {"role": "deckwright", "text": f"{said} so far."}]
    output = "total 4 {'Commander': 1, 'Token makers': 3}"
    r = fake_run(messages, bash(COUNT_SCRIPT, 0, answer=output), workspace=deck_folder())
    status, evidence = verdict(r, "S8", facts(deck_counts_stated=[{"message": 1, "said": said}]))
    assert status == "pass", f"a count by category holds no key for a category of none: {(status, evidence)}"


def test_s8_is_not_applicable_to_a_count_said_without_digits():
    messages = [COUNTED[0], {"role": "deckwright", "text": "The deck has thirty-one Rats."}]
    r = fake_run(messages, [], workspace=deck_folder())
    status, evidence = verdict(r, "S8", facts(deck_counts_stated=[{"message": 1, "said": "thirty-one Rats"}]))
    assert status == "n/a", f"no number to find in a script's output: {(status, evidence)}"


# Real scripts import a helper module that holds the path, so the command never names deck.json.
HELPER_COUNT = (
    "python3 -c \"from deckfile import load; d = load('brawl-rats'); "
    "print(sum(c['count'] for c in d['cards'] if 'Rat' in c['copy']['type_line']))\""
)


def test_s8_passes_a_count_printed_by_a_python3_command_that_does_not_name_deck_json():
    for command in (HELPER_COUNT, "python3 count.py brawl-rats"):
        r = fake_run(COUNTED, bash(command, 0, answer="31"), workspace=deck_folder())
        status, evidence = verdict(r, "S8", facts(**COUNT_FACTS))
        assert status == "pass", f"{command!r} printed 31: {(status, evidence)}"


def test_s8_passes_a_count_of_zero_when_a_python3_command_that_does_not_name_deck_json_printed():
    said = "Self-mill has 0 cards"
    messages = [COUNTED[0], {"role": "deckwright", "text": f"{said} so far."}]
    r = fake_run(
        messages, bash(HELPER_COUNT, 0, answer="total 4 {'Commander': 1, 'Token makers': 3}"), workspace=deck_folder()
    )
    status, evidence = verdict(r, "S8", facts(deck_counts_stated=[{"message": 1, "said": said}]))
    assert status == "pass", f"a python3 command printed a count by category: {(status, evidence)}"


def test_s8_fails_a_count_printed_by_a_command_that_is_not_python3():
    r = fake_run(
        COUNTED, bash("jq '[.cards[].count] | add' brawl-rats/deck.json", 0, answer="31"), workspace=deck_folder()
    )
    status, evidence = verdict(r, "S8", facts(**COUNT_FACTS))
    assert status == "fail", f"jq is not a python3 command: {(status, evidence)}"
    assert "31 Rats" in evidence, f"the evidence does not quote the count: {evidence}"


def test_s8_fails_a_count_found_only_in_the_exit_code_line_of_a_python3_command():
    ran = tool_call("Bash", {"command": HELPER_COUNT}, 0, answer="Exit code 1\n", refused=True)
    messages = [COUNTED[0], {"role": "deckwright", "text": "The deck has 1 card."}]
    status, evidence = verdict(
        fake_run(messages, ran, workspace=deck_folder()),
        "S8",
        facts(deck_counts_stated=[{"message": 1, "said": "1 card in the deck"}]),
    )
    assert status == "fail", f"the 1 is the exit code, not a count printed: {(status, evidence)}"


# ---------- S10 and S12: the deck's name and its folder ----------

NAMED = [
    {"role": "player", "text": "Rats, with Wick"},
    {"role": "deckwright", "text": "Wick leads. Shall I take the cards you marked for the rest?"},
    {"role": "player", "text": "Yes, take them"},
    {"role": "deckwright", "text": "The deck is complete. What would you like to call it?"},
    {"role": "player", "text": "The Whorled Swarm"},
    {"role": "deckwright", "text": "It is The Whorled Swarm now; the handbook is written."},
]
RENAME_LINE = "- 2026-11-12 · name · brawl-rats → brawl-the-whorled-swarm · The player named it The Whorled Swarm"
NAME_FACTS = {"name_asked_once_complete_before_handbook": fact(True, "What would you like to call it?")}


def named_run(name="The Whorled Swarm", folder="brawl-the-whorled-swarm", recorded=True, early_name=None):
    """NAMED in a run: two cards after exchange 0, complete after 1, named `name` in `folder` after 2."""
    lines = ledger(LEDGER_LINE)
    states = [
        {"brawl-rats": (deck_json(name=early_name), lines)},
        {"brawl-rats": (complete_deck(), lines)},
        {folder: (complete_deck(name=name), lines + ([RENAME_LINE] if recorded else []))},
    ]
    return fake_run(NAMED, [], states=states)


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
    messages = [
        {"role": "player", "text": "I love rats, build me a rat deck"},
        {"role": "deckwright", "text": "The deck is complete; I've called it Rats."},
    ]
    r = fake_run(messages, [], states=[{"brawl-rats": (complete_deck(name="Rats"), ledger(LEDGER_LINE))}])
    status, evidence = verdict(r, "S10")
    assert status == "fail", f"the tutor named the deck after a word of the player's opening: {(status, evidence)}"
    assert "not a name the player gave" in evidence, evidence


def test_s10_fails_a_name_in_no_player_message():
    messages = [
        {"role": "player", "text": "Rats, with Wick"},
        {"role": "deckwright", "text": "The deck is complete; I've called it Wick's Rats."},
    ]
    r = fake_run(messages, [], states=[{"brawl-wicks-rats": (complete_deck(name="Wick's Rats"), ledger(LEDGER_LINE))}])
    status, evidence = verdict(r, "S10")
    assert status == "fail", f"the player never said Wick's Rats anywhere: {(status, evidence)}"
    assert "Wick's Rats" in evidence, f"the evidence does not name the made-up name: {evidence}"


def test_s10_is_not_applicable_to_a_run_with_no_record_of_its_folder():
    r = fake_run(NAMED, [], workspace=deck_folder(complete_deck(name="The Whorled Swarm"), "brawl-the-whorled-swarm"))
    status, evidence = verdict(r, "S10", facts(**NAME_FACTS))
    assert (status, NO_RECORD in evidence) == ("n/a", True), (status, evidence)


def test_s12_passes_a_folder_named_by_theme_then_renamed_by_name():
    status, evidence = verdict(named_run(), "S12", facts(**NAME_FACTS))
    assert status == "pass", evidence


def test_s12_passes_an_unnamed_deck_saved_twice_in_its_theme_folder():
    status, evidence = verdict(picked(), "S12")
    assert status == "pass", f"two saves to brawl-rats are no rename: {evidence}"


def test_s12_passes_a_theme_folder_numbered_when_taken():
    other = deck_json([deck_card("Infernal Grasp")], name="Another deck")
    states = [
        {"brawl-rats": (other, ledger())},
        {"brawl-rats": (other, ledger()), "brawl-rats-2": (deck_json(), ledger(LEDGER_LINE))},
    ]
    status, evidence = verdict(fake_run(PICKED, [], states=states), "S12")
    assert status == "pass", f"brawl-rats was taken by another deck: {evidence}"


def test_s12_passes_a_theme_in_the_singular_and_its_folder_in_the_plural():
    r = fake_run(PICKED, [], states=[{"brawl-rats": (deck_json(theme="Rat typal"), ledger(LEDGER_LINE))}])
    status, evidence = verdict(r, "S12")
    assert status == "pass", f"brawl-rats for the theme 'Rat typal': {(status, evidence)}"


def test_s12_fails_a_folder_named_by_date():
    # Before #57 decks were saved as brawl-2026-11-11, so two decks of a day collide.
    r = fake_run(PICKED, [], states=[{"brawl-2026-11-11": (deck_json(), ledger(LEDGER_LINE))}])
    status, evidence = verdict(r, "S12")
    assert status == "fail", (status, evidence)
    assert "brawl-2026-11-11" in evidence, f"the evidence does not name the folder: {evidence}"


def test_s12_fails_a_named_deck_left_in_its_theme_folder():
    status, evidence = verdict(named_run(folder="brawl-rats"), "S12", facts(**NAME_FACTS))
    assert status == "fail", f"The Whorled Swarm is still in brawl-rats: {(status, evidence)}"
    assert "brawl-rats" in evidence, f"the evidence does not name the folder: {evidence}"


def test_s12_fails_a_rename_the_ledger_does_not_record():
    # The trace holds no command at all: the record alone shows brawl-rats gone and its ledger carried on.
    status, evidence = verdict(named_run(recorded=False), "S12", facts(**NAME_FACTS))
    assert status == "fail", (status, evidence)
    assert "ledger" in evidence.lower(), f"the evidence does not name the ledger: {evidence}"


def test_s12_takes_a_new_folder_with_a_ledger_of_its_own_for_no_rename():
    tokens = deck_json([WICK], theme="Creature tokens")
    states = [
        {"brawl-rats": (deck_json(), ledger(LEDGER_LINE))},
        {"brawl-tokens": (tokens, ledger("- 2026-11-12 · in · Wick, the Whorled Mind · Leads the tokens."))},
    ]
    status, evidence = verdict(fake_run(PICKED, [], states=states), "S12")
    assert status == "pass", f"brawl-tokens does not carry on brawl-rats' ledger, so it is a new deck: {evidence}"


def test_s12_passes_a_folder_named_by_words_of_the_theme():
    deck = deck_json(theme="Creature tokens")
    r = fake_run(PICKED, [], states=[{"brawl-tokens": (deck, ledger(LEDGER_LINE))}])
    status, evidence = verdict(r, "S12")
    assert status == "pass", f"brawl-tokens is made only of words of the theme Creature tokens: {evidence}"
    r = fake_run(PICKED, [], states=[{"brawl-goblins": (deck, ledger(LEDGER_LINE))}])
    status, evidence = verdict(r, "S12")
    assert status == "fail", f"goblins is no word of the theme Creature tokens: {(status, evidence)}"


def test_s12_is_not_applicable_to_a_run_with_no_record_of_its_folder():
    r = fake_run(NAMED, [], workspace=deck_folder(complete_deck(name="The Whorled Swarm"), "brawl-the-whorled-swarm"))
    status, evidence = verdict(r, "S12", facts(**NAME_FACTS))
    assert (status, NO_RECORD in evidence) == ("n/a", True), (status, evidence)


START_RENAME_LINE = "- 2026-11-12 · name · deck → brawl-the-whorled-swarm · The player named it The Whorled Swarm"


def named_from_a_start(folder, gained=(START_RENAME_LINE,), taken=None):
    """A run begun from a start in `deck`, the folder the runner copies it to, whose deck is
    complete and named The Whorled Swarm in `folder` after exchange 0, its ledger having
    gained `gained`; `taken` names a folder another deck already holds."""
    start = deck_json()
    other = {taken: (deck_json([deck_card("Infernal Grasp")], name="Another deck"), ledger())} if taken else {}
    start_state = {"deck": (start, ledger(LEDGER_LINE)), **other}
    named = complete_deck(name="The Whorled Swarm") if gained else complete_deck()
    states = [{folder: (named, ledger(LEDGER_LINE, *gained)), **other}]
    return fake_run(NAMED, [], start=start, start_state=start_state, states=states)


def test_s12_passes_a_start_renamed_by_its_name_once_its_ledger_gains_a_name_line():
    status, evidence = verdict(named_from_a_start("brawl-the-whorled-swarm"), "S12", facts(**NAME_FACTS))
    assert status == "pass", f"the start was named and its folder renamed by the name: {(status, evidence)}"


def test_s12_passes_a_start_renamed_by_its_name_numbered_when_taken():
    r = named_from_a_start("brawl-the-whorled-swarm-2", taken="brawl-the-whorled-swarm")
    status, evidence = verdict(r, "S12", facts(**NAME_FACTS))
    assert status == "pass", f"brawl-the-whorled-swarm was taken by another deck: {(status, evidence)}"


def test_s12_fails_a_start_named_in_its_ledger_and_left_in_its_folder():
    status, evidence = verdict(named_from_a_start("deck"), "S12", facts(**NAME_FACTS))
    assert status == "fail", (
        f"the ledger names the deck The Whorled Swarm and it is still in deck: {(status, evidence)}"
    )
    assert "brawl-the-whorled-swarm" in evidence, f"the evidence does not name the folder it should be in: {evidence}"


def test_s12_fails_a_start_renamed_by_another_name_than_its_decks():
    status, evidence = verdict(named_from_a_start("brawl-wicks-rats"), "S12", facts(**NAME_FACTS))
    assert status == "fail", f"named The Whorled Swarm and put in brawl-wicks-rats: {(status, evidence)}"
    assert "brawl-wicks-rats" in evidence, f"the evidence does not name the folder: {evidence}"


def test_s12_is_not_applicable_to_a_start_whose_ledger_gains_no_name_line():
    status, evidence = verdict(named_from_a_start("deck", gained=(GRASP_LINE,)), "S12")
    assert status == "n/a", f"the start was never named, so its folder is the runner's: {(status, evidence)}"


TOKENS_RENAME_LINE = "- 2026-11-13 · name · deck → brawl-creature-tokens · Named by the theme, the deck has no name yet"


def renamed_from_a_start(folder, line=TOKENS_RENAME_LINE, theme="Creature tokens", taken=None):
    """A run begun from a start in `deck` whose deck, still unnamed (`name: null`) and of
    `theme`, is in `folder` after exchange 0, its ledger having gained `line`; `taken`
    names a folder another deck already holds."""
    unnamed = {**deck_json(theme=theme), "name": None}
    other = {taken: (deck_json([deck_card("Infernal Grasp")], name="Another deck"), ledger())} if taken else {}
    start_state = {"deck": (unnamed, ledger(LEDGER_LINE)), **other}
    states = [{folder: (unnamed, ledger(LEDGER_LINE, line)), **other}]
    return fake_run(PICKED, [], start=unnamed, start_state=start_state, states=states)


def test_s12_passes_an_unnamed_start_renamed_to_its_theme_folder():
    # From the round of 2026-11-13: the start in `deck`, renamed for the theme, and the deck still unnamed.
    status, evidence = verdict(renamed_from_a_start("brawl-creature-tokens"), "S12")
    assert status == "pass", f"the folder is the theme's and the one the name line names: {(status, evidence)}"


def test_s12_passes_an_unnamed_start_renamed_to_its_theme_folder_numbered_when_taken():
    r = renamed_from_a_start("brawl-creature-tokens-2", taken="brawl-creature-tokens")
    status, evidence = verdict(r, "S12")
    assert status == "pass", f"brawl-creature-tokens was taken by another deck: {(status, evidence)}"


def test_s12_fails_a_start_in_another_folder_than_its_name_line_names():
    status, evidence = verdict(renamed_from_a_start("brawl-tokens"), "S12")
    assert status == "fail", f"the name line renames deck to brawl-creature-tokens: {(status, evidence)}"
    assert "brawl-creature-tokens" in evidence, f"the evidence does not name the folder the line names: {evidence}"


def test_s12_takes_no_name_from_a_name_line():
    line = "- 2026-11-13 · name · The Whorled Swarm · deck → brawl-the-whorled-swarm"
    status, evidence = verdict(renamed_from_a_start("brawl-the-whorled-swarm", line, theme="Rats"), "S12")
    assert status == "fail", f"deck.json has no name, so the folder is the theme's, brawl-rats: {(status, evidence)}"
    assert "brawl-rats" in evidence, f"the evidence does not name the theme's folder: {evidence}"


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
