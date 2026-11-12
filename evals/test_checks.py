"""Tests for the checks and the runner that need no model and no Scryfall.

    python3 evals/test_checks.py

Each one was found red by the pre-PR review of 2026-11-11 and fixed.
"""

from __future__ import annotations

import os
import pathlib
import socket
import sys
import traceback
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import checks  # noqa: E402
import headless  # noqa: E402
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
        none_run = run_tests({})
    assert one_fails == 1, f"a failing test left the exit status at {one_fails}, so CI goes green"
    assert none_fail == 0, f"every test passed and the exit status is {none_fail}"
    assert none_run == 1, f"no test ran and the exit status is {none_run}, so CI goes green on nothing"


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
    text = workflow.read_text()
    assert "secrets." not in text, "the workflow reads a secret, so it can hold a key that starts Claude"
    assert "claude" not in text.lower(), "the workflow names Claude"


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

    # Through a proxy the only host a connection names is the proxy's, and these tests need none.
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
        except Exception as e:
            failed += 1
            print("FAIL", name, "--", e if isinstance(e, AssertionError) else traceback.format_exc(limit=1))
    if not tests:
        print("no tests found")
        return 1
    print(f"{failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    block_the_network()
    sys.exit(run_tests({name: fn for name, fn in list(globals().items()) if name.startswith("test_")}))
