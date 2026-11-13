"""Run Deckwright against a stand-in player and keep everything the checks read.

A run is one whole conversation. Deckwright is Claude Code headless on Opus 5.5
in a workspace of its own; the stand-in player is a second model that only
sees Deckwright's replies, as a player in chat would. The bare arm gets nothing
but the brief's opening line; the skill arm also loads the plugin.

    python3 evals/run.py evals/briefs/brawl-rats.md --arm bare --runs 3
    python3 evals/run.py evals/briefs/brawl-rats.md --arm bare --runs 3 --resume <stamp>
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import os
import pathlib
import re
import shutil
import threading
import uuid

import checks
import headless

DECKWRIGHT_MODEL = "claude-opus-5-5"
STAND_IN_MODEL = "claude-sonnet-5-5"
PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "deckwright"
STARTS_DIR = pathlib.Path(__file__).resolve().parent / "starts"
RUNS_DIR = pathlib.Path(__file__).resolve().parent / "runs"
END = "<<END>>"
NEW_CONVERSATION = "<<NEW_CONVERSATION>>"
# The account may publish 200 pages a day, reset at midnight UTC. 2026-11-11's rounds,
# which published at every save, used the lot, which stopped publishing in every
# thread on the account; 150 leaves the owner 50.
DEFAULT_PUBLISH_BUDGET = 150
STOPPED_BY_BUDGET = "publish budget"

# File and lookup tools Deckwright needs, granted up front because a headless run
# cannot stop to ask; a compound shell command needs every part allowed. Files never go into the person's chat (decided
# 2026-11-10): a run's picture cards would land there.
DECKWRIGHT_ALLOWED = ["Read", "Write", "Edit", "Glob", "Grep", "Artifact", "WebFetch",
                      "Bash(curl:*)", "Bash(mkdir:*)", "Bash(ls:*)", "Bash(python3:*)",
                      "Bash(cp:*)", "Bash(cd:*)", "Bash(mv:*)"]
DECKWRIGHT_DISALLOWED = ["SendUserFile", "PushNotification", "ScheduleWakeup", "CronCreate"]

STAND_IN_RULES = f"""You are playing a Magic: The Gathering player who is building a deck in a
chat with a deck-building assistant. Your brief below says who you are and what
you want. Reply as that player only: short, natural chat messages, one reply per
turn, never the assistant's side. You cannot see pictures; the assistant's text is
all you get. Answer what you are asked. Do not suggest cards the brief does not
give you; choose among what you are shown. Never look anything up.

When your brief says the conversation breaks off, reply with exactly
{NEW_CONVERSATION} on the first line and, on the next lines, the message you would
open the new conversation with. When the deck is done and you have approved it,
or your brief says you stop, reply with exactly {END} and nothing else.
"""


def read_brief(path: pathlib.Path) -> tuple[str, str, str | None, str | None]:
    """A brief holds `## Opening` (the player's first message) and `## Player`. It may
    name a `## Start`, a half-built deck under `starts/` the run begins from, and an
    `## Ends`, the step the player stops at before the deck is full."""
    text = path.read_text()

    def section(name: str) -> str | None:
        found = re.search(rf"## {name}\n+(.+?)\s*(?=\n## |\Z)", text, re.S)
        return found and found.group(1).strip()
    return section("Opening"), section("Player"), section("Start"), section("Ends")


def claude(args: list[str], prompt: str, cwd: pathlib.Path, memory: pathlib.Path) -> list[dict]:
    """One headless turn; returns its stream-json events."""
    proc = headless.claude(["--output-format", "stream-json", "--verbose", *args], prompt, memory,
                           cwd=cwd, timeout=3600)
    events = []
    for line in proc.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not any(e.get("type") == "result" for e in events):
        events.append({"type": "result", "is_error": True, "result": proc.stderr[-2000:]})
    return events


def result_of(events: list[dict]) -> dict:
    return next(e for e in reversed(events) if e.get("type") == "result")


def deckwright_turn(message: str, session: str, first: bool, arm: str, cwd: pathlib.Path,
                    memory: pathlib.Path) -> list[dict]:
    args = ["--model", DECKWRIGHT_MODEL, "--allowedTools", *DECKWRIGHT_ALLOWED,
            "--disallowedTools", *DECKWRIGHT_DISALLOWED]
    args += ["--session-id", session] if first else ["--resume", session]
    if arm == "skill":
        args += ["--plugin-dir", str(PLUGIN_DIR)]
    return claude(args, message, cwd, memory)


def stand_in_turn(message: str, session: str, first: bool, player: str, cwd: pathlib.Path) -> dict:
    args = ["--model", STAND_IN_MODEL, "--tools", "", "--system-prompt", STAND_IN_RULES + "\n## Your brief\n\n" + player]
    args += ["--session-id", session] if first else ["--resume", session]
    return result_of(claude(args, message, cwd, cwd.parent / "memory" / "stand-in"))


def record_deck_folders(workspace: pathlib.Path, into: pathlib.Path) -> None:
    """Copy every `deck.json` and `LEDGER.md` in the workspace into `into`, at the same
    relative paths: the checks read the deck folders as each exchange left them.
    Claude Code's own `.claude` folder is not a deck's."""
    for path in [*workspace.rglob("deck.json"), *workspace.rglob("LEDGER.md")]:
        relative = path.relative_to(workspace)
        if ".claude" in relative.parts or not path.is_file():
            continue
        (into / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, into / relative)


class PublishBudget:
    """The publishes a round may make, shared by its runs, which play in threads at once.

    The account's limit is per UTC day, so with a `ledger` folder every accepted
    publish is also recorded in a file for the day, and every start of the runner that
    day, side by side or later, counts against the same budget.
    """

    def __init__(self, publishes: int, ledger: pathlib.Path | None = None):
        self.publishes, self.ledger, self.published, self.lock = publishes, ledger, 0, threading.Lock()

    def count(self, events: list[dict]) -> None:
        """Add the publishes one Deckwright turn made that the Artifact tool accepted."""
        accepted = sum(checks.publishes_by_exchange(events).values())
        with self.lock:
            self.published += accepted
            if self.ledger and accepted:
                self.ledger.mkdir(parents=True, exist_ok=True)
                with self._today().open("a") as f:
                    f.write("publish\n" * accepted)

    def used_up(self) -> bool:
        with self.lock:
            if not self.ledger:
                return self.published >= self.publishes
            today = self._today()
            return (len(today.read_text().splitlines()) if today.exists() else 0) >= self.publishes

    def _today(self) -> pathlib.Path:
        # Worked out on each call: a round can run past midnight UTC.
        return self.ledger / datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")


def run(brief: pathlib.Path, arm: str, out: pathlib.Path, max_exchanges: int,
        budget: PublishBudget | None = None) -> dict:
    """Play one conversation to its end and write it under `out`.

    `run.json` is written however the run ends, so a run that dies still counts.
    Without a `budget` the run is a round of one. The run stops after the exchange in
    which the round's budget is used up; turns in flight in other runs may still
    publish a few past it.
    """
    budget = budget or PublishBudget(DEFAULT_PUBLISH_BUDGET)
    workspace, stand_in_cwd = out / "workspace", out / "stand-in"
    opening, player, start, ends = read_brief(brief)
    conversation = out / "conversation.jsonl"
    trace = out / "trace.jsonl"
    stand_in_session = str(uuid.uuid4())
    deckwright_session, conversation_no = str(uuid.uuid4()), 1
    cost_by_conversation: dict[int, float] = {}
    message, first_deckwright, first_stand_in, ended, exchange = opening, True, True, "turn cap", 0

    def log(path: pathlib.Path, record: dict) -> None:
        with path.open("a") as f:
            f.write(json.dumps(record) + "\n")

    out.mkdir(parents=True, exist_ok=True)
    try:
        workspace.mkdir()
        stand_in_cwd.mkdir()
        if start:
            shutil.copytree(STARTS_DIR / start, workspace / "deck", ignore=shutil.ignore_patterns("*.py"))
            # The checks read the start as the run began, not as starts/ is later.
            shutil.copytree(STARTS_DIR / start, out / "start", ignore=shutil.ignore_patterns("*.py"))
            record_deck_folders(workspace, out / "after" / "start")
        for exchange in range(max_exchanges):
            log(conversation, {"role": "player", "conversation": conversation_no, "text": message})
            # Each conversation remembers nothing of the one before: a resumed deck comes from its page.
            memory = out / "memory" / f"deckwright-{conversation_no}"
            events = deckwright_turn(message, deckwright_session, first_deckwright, arm, workspace, memory)
            first_deckwright = False
            record_deck_folders(workspace, out / "after" / str(exchange))
            budget.count(events)
            for event in events:
                log(trace, {"conversation": conversation_no, "exchange": exchange, **event})
            result = result_of(events)
            # A resumed session reports its whole running total, not this turn's.
            totals = [e["total_cost_usd"] for e in events
                      if e.get("type") == "result" and e.get("total_cost_usd") is not None]
            if totals:
                cost_by_conversation[conversation_no] = max(totals)
            reply = (result.get("result") or "").strip()
            log(conversation, {"role": "deckwright", "conversation": conversation_no, "text": reply,
                               "error": bool(result.get("is_error"))})
            if result.get("is_error"):
                ended = "deckwright error"
                break
            answer = stand_in_turn(reply, stand_in_session, first_stand_in, player, stand_in_cwd)
            first_stand_in = False
            if answer.get("is_error"):
                ended = "stand-in error"
                break
            message = (answer.get("result") or "").strip()
            if message.startswith(END):
                ended = "player ended"
                break
            if message.startswith(NEW_CONVERSATION):
                message = message[len(NEW_CONVERSATION):].strip()
                deckwright_session, conversation_no, first_deckwright = str(uuid.uuid4()), conversation_no + 1, True
            if budget.used_up():
                ended = STOPPED_BY_BUDGET
                break
    except Exception as error:  # a timeout or a crash still leaves the run on record
        ended = f"runner error: {type(error).__name__}"
    summary = {"brief": brief.stem, "arm": arm, "start": start, "ends": ends, "ended": ended,
               "exchanges": exchange + 1, "deckwright_cost_usd": round(sum(cost_by_conversation.values()), 2)}
    (out / "run.json").write_text(json.dumps(summary, indent=2))
    return summary


def finished(out: pathlib.Path) -> bool:
    """The run wrote its `run.json` and the publish budget did not stop it short."""
    try:
        return json.loads((out / "run.json").read_text()).get("ended") != STOPPED_BY_BUDGET
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return False


def play_round(briefs: list[pathlib.Path], arm: str, runs: int, round_dir: pathlib.Path, jobs: int,
               max_exchanges: int, budget: PublishBudget):
    """Play the round's runs, yielding their summaries in order.

    A finished run is skipped. Any other run folder, cut off mid-run or stopped by the
    budget, is cleared, so the run plays again from its start. Once the
    budget is used up no further run starts: a run not started gets no folder and an
    unfinished one keeps what it has, so `--resume` plays both.
    """
    def play(brief: pathlib.Path, out: pathlib.Path) -> dict:
        if budget.used_up():
            return {"brief": brief.stem, "arm": arm, "ended": f"not started: {STOPPED_BY_BUDGET}"}
        if out.exists():
            shutil.rmtree(out)
        return run(brief, arm, out, max_exchanges, budget)

    unfinished = [(b, round_dir / f"{b.stem}--{arm}--{n}") for b in briefs for n in range(1, runs + 1)]
    unfinished = [(b, out) for b, out in unfinished if not finished(out)]
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        yield from pool.map(lambda job: play(*job), unfinished)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("briefs", nargs="+", type=pathlib.Path)
    parser.add_argument("--arm", choices=["bare", "skill"], required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("-j", "--jobs", type=int, default=3)
    parser.add_argument("--max-exchanges", type=int, default=120)
    parser.add_argument("--publish-budget", type=int, default=DEFAULT_PUBLISH_BUDGET)
    parser.add_argument("--resume", metavar="STAMP", help="play the unfinished runs of the round in runs/STAMP")
    args = parser.parse_args()
    if args.resume:
        round_dir = RUNS_DIR / args.resume
        if not round_dir.is_dir():
            parser.error(f"no round to resume at {round_dir}")
    else:
        round_dir = RUNS_DIR / datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
    budget = PublishBudget(args.publish_budget, RUNS_DIR / "publishes")
    for summary in play_round(args.briefs, args.arm, args.runs, round_dir, args.jobs, args.max_exchanges, budget):
        print(json.dumps(summary))


if __name__ == "__main__":
    (RUNS_DIR / "tmp").mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TMPDIR", str(RUNS_DIR / "tmp"))
    main()
