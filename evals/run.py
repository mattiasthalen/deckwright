"""Run Deckwright against a stand-in player and keep everything the checks read.

A run is one whole conversation. Deckwright is Claude Code headless on Opus 5.5
in a workspace of its own; the stand-in player is a second model that only
sees Deckwright's replies, as a player in chat would. The bare arm gets nothing
but the brief's opening line; the skill arm also loads the plugin.

    uv run evals/run.py briefs/brawl-rats.md --arm bare --runs 3
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
import subprocess
import uuid

DECKWRIGHT_MODEL = "claude-opus-5-5"
STAND_IN_MODEL = "claude-sonnet-5-5"
PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "deckwright"
STARTS_DIR = pathlib.Path(__file__).resolve().parent / "starts"
RUNS_DIR = pathlib.Path(__file__).resolve().parent / "runs"
END = "<<END>>"
NEW_CONVERSATION = "<<NEW_CONVERSATION>>"

# What a project thread lets Deckwright do, granted up front because a headless
# run cannot stop to ask. Files never go into the person's chat (decided
# 2026-11-10): a run's picture cards would land there.
DECKWRIGHT_ALLOWED = ["Read", "Write", "Edit", "Glob", "Grep", "Artifact", "WebFetch",
                      "Bash(curl:*)", "Bash(mkdir:*)", "Bash(ls:*)", "Bash(python3:*)"]
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


def read_brief(path: pathlib.Path) -> tuple[str, str, str | None]:
    """A brief holds `## Opening` (the player's first message), `## Player`, and may
    name a `## Start`: a half-built deck under `starts/` that the run begins from."""
    text = path.read_text()
    section = lambda name: re.search(rf"## {name}\n+(.+?)\s*(?=\n## |\Z)", text, re.S)
    start = section("Start")
    return section("Opening").group(1).strip(), section("Player").group(1).strip(), start and start.group(1).strip()


def isolated_env(memory: pathlib.Path) -> dict:
    """The parent's environment minus the project's shared memory.

    A run inherits the cloud session's memory store, and the bare runs of
    2026-11-10 wrote stand-in decks into it as the owner's and read them back in
    later runs. Each run gets an empty memory folder of its own instead.
    """
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_MEMORY_STORES"}
    env["CLAUDE_COWORK_MEMORY_PATH_OVERRIDE"] = str(memory)
    return env


def claude(args: list[str], prompt: str, cwd: pathlib.Path) -> list[dict]:
    """One headless turn; returns its stream-json events."""
    memory = cwd.parent / "memory"
    memory.mkdir(exist_ok=True)
    proc = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", *args],
        cwd=cwd,
        env=isolated_env(memory),
        capture_output=True,
        text=True,
        timeout=3600,
    )
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


def deckwright_turn(message: str, session: str, first: bool, arm: str, cwd: pathlib.Path) -> list[dict]:
    args = ["--model", DECKWRIGHT_MODEL, "--allowedTools", *DECKWRIGHT_ALLOWED,
            "--disallowedTools", *DECKWRIGHT_DISALLOWED]
    args += ["--session-id", session] if first else ["--resume", session]
    if arm == "skill":
        args += ["--plugin-dir", str(PLUGIN_DIR)]
    return claude(args, message, cwd)


def stand_in_turn(message: str, session: str, first: bool, player: str, cwd: pathlib.Path) -> str:
    args = ["--model", STAND_IN_MODEL, "--tools", "", "--system-prompt", STAND_IN_RULES + "\n## Your brief\n\n" + player]
    args += ["--session-id", session] if first else ["--resume", session]
    return (result_of(claude(args, message, cwd)).get("result") or "").strip()


def run(brief: pathlib.Path, arm: str, out: pathlib.Path, max_exchanges: int) -> dict:
    """Play one conversation to its end and write it under `out`."""
    workspace = out / "workspace"
    workspace.mkdir(parents=True)
    stand_in_cwd = out / "stand-in"
    stand_in_cwd.mkdir()
    opening, player, start = read_brief(brief)
    if start:
        shutil.copytree(STARTS_DIR / start, workspace / "deck", ignore=shutil.ignore_patterns("*.py"))
    conversation = out / "conversation.jsonl"
    trace = out / "trace.jsonl"
    stand_in_session = str(uuid.uuid4())
    deckwright_session, conversation_no, cost = str(uuid.uuid4()), 1, 0.0
    message, first_deckwright, first_stand_in, ended = opening, True, True, "turn cap"

    def log(path: pathlib.Path, record: dict) -> None:
        with path.open("a") as f:
            f.write(json.dumps(record) + "\n")

    for exchange in range(max_exchanges):
        log(conversation, {"role": "player", "conversation": conversation_no, "text": message})
        events = deckwright_turn(message, deckwright_session, first_deckwright, arm, workspace)
        first_deckwright = False
        for event in events:
            log(trace, {"conversation": conversation_no, "exchange": exchange, **event})
        result = result_of(events)
        cost += sum(e.get("total_cost_usd") or 0.0 for e in events if e.get("type") == "result")
        reply = (result.get("result") or "").strip()
        log(conversation, {"role": "deckwright", "conversation": conversation_no, "text": reply,
                           "error": bool(result.get("is_error"))})
        if result.get("is_error"):
            ended = "deckwright error"
            break
        message = stand_in_turn(reply, stand_in_session, first_stand_in, player, stand_in_cwd)
        first_stand_in = False
        if message.startswith(END):
            ended = "player ended"
            break
        if message.startswith(NEW_CONVERSATION):
            message = message[len(NEW_CONVERSATION):].strip()
            deckwright_session, conversation_no, first_deckwright = str(uuid.uuid4()), conversation_no + 1, True
    summary = {"brief": brief.stem, "arm": arm, "start": start, "ended": ended, "exchanges": exchange + 1,
               "deckwright_cost_usd": round(cost, 2)}
    (out / "run.json").write_text(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("briefs", nargs="+", type=pathlib.Path)
    parser.add_argument("--arm", choices=["bare", "skill"], required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("-j", "--jobs", type=int, default=6)
    parser.add_argument("--max-exchanges", type=int, default=120)
    args = parser.parse_args()
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
    jobs = [(b, RUNS_DIR / stamp / f"{b.stem}--{args.arm}--{n}") for b in args.briefs for n in range(1, args.runs + 1)]
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        for summary in pool.map(lambda job: run(job[0], args.arm, job[1], args.max_exchanges), jobs):
            print(json.dumps(summary))


if __name__ == "__main__":
    (RUNS_DIR / "tmp").mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TMPDIR", str(RUNS_DIR / "tmp"))
    main()
