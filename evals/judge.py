"""The blind judge: which of two conversations for the same brief taught better.

    python3 evals/judge.py --bare evals/runs/<stamp> [...] --skill evals/runs/<stamp> [...]

Runs are paired by brief and run number. The judge sees the two conversations as
A and B with nothing saying which had the skill, answers fixed questions, then
answers them again with the order swapped. The skill wins a question only when it
is picked both times; the judge never decides a counted check. It is a different
model from the one tested.
"""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter

import headless
from checks import Run

JUDGE_MODEL = "claude-sonnet-5-5"
QUESTIONS = {
    "why_offered": "Which assistant explained better why each card was offered?",
    "compared": "Which assistant compared the cards it offered with each other and with cards already chosen?",
    "tied_to_wants": "Which assistant tied its reasons to what this player said they wanted?",
    "terms": "Which assistant explained each Magic term once when it first came up and kept using the same word for it after?",
    "player_knows_more": "After which conversation does the player know more about their deck: how it plays and why each card is there?",
    "page_explains": "Which assistant left a saved deck (page or files) that explains the deck better on its own?",
}
SCHEMA = {
    "type": "object",
    "properties": {
        key: {
            "type": "object",
            "properties": {"winner": {"enum": ["A", "B", "tie"]}, "why": {"type": "string"}},
            "required": ["winner", "why"],
        }
        for key in QUESTIONS
    },
    "required": list(QUESTIONS),
}
PROMPT = """Two assistants each helped a player build a Magic: The Gathering deck for
Arena from the same brief. Read both conversations and what each one saved, then
answer each question with A, B or tie and one sentence of evidence. Judge teaching,
not deck strength. Length is not quality.

{questions}

=== CONVERSATION A ===
{a}

=== CONVERSATION B ===
{b}
"""
LIMIT = 150_000


def transcript(path: pathlib.Path) -> str:
    run = Run(path)
    text = "\n\n".join(f"{m['role'].upper()}: {m['text']}" for m in run.messages)
    text = text[-LIMIT:] if len(text) > LIMIT else text
    saved = [
        f"--- saved {name} ---\n" + run.published[name].read_text(errors="replace")[:40_000]
        for name in ("deck.json", "LEDGER.md")
        if name in run.published
    ]
    saved += [
        f"--- saved {name} ---\n{body[:40_000]}"
        for name, body in run.files.items()
        if name.endswith((".md", ".txt", ".json")) and not saved
    ]
    return text + "\n\nSAVED\n" + ("\n".join(saved) or "(nothing saved)")


def ask(a: str, b: str) -> dict:
    questions = "\n".join(f"- {key}: {q}" for key, q in QUESTIONS.items())
    proc = headless.claude(
        ["--model", JUDGE_MODEL, "--tools", "", "--output-format", "json", "--json-schema", json.dumps(SCHEMA)],
        PROMPT.format(questions=questions, a=a, b=b),
        timeout=1800,
    )
    return json.loads(proc.stdout)["structured_output"]


def runs_by_key(stamps: list[pathlib.Path]) -> dict[tuple[str, str], pathlib.Path]:
    found = {}
    for stamp in stamps:
        for run in stamp.iterdir():
            if (run / "run.json").exists():
                brief, _, n = run.name.split("--")
                if (brief, n) in found:
                    raise SystemExit(f"two runs pair as {brief} {n}: {found[(brief, n)]} and {run}")
                found[(brief, n)] = run
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bare", nargs="+", type=pathlib.Path, required=True)
    parser.add_argument("--skill", nargs="+", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("evals/runs/judge.json"))
    args = parser.parse_args()
    bare, skill = runs_by_key(args.bare), runs_by_key(args.skill)
    results = json.loads(args.out.read_text()) if args.out.exists() else {}
    for key in sorted(bare.keys() & skill.keys()):
        # Keyed by both runs, so a new round is judged afresh against the same bare runs.
        name = f"{bare[key]}|{skill[key]}"
        if name not in results:
            b, s = transcript(bare[key]), transcript(skill[key])
            first, second = ask(s, b), ask(b, s)  # the skill is A, then B
            results[name] = {
                q: {
                    "skill_first": first[q],
                    "skill_second": second[q],
                    "verdict": "skill"
                    if first[q]["winner"] == "A" and second[q]["winner"] == "B"
                    else "bare"
                    if first[q]["winner"] == "B" and second[q]["winner"] == "A"
                    else "split",
                }
                for q in QUESTIONS
            }
            args.out.write_text(json.dumps(results, indent=2))
        print("--".join(key), {q: v["verdict"] for q, v in results[name].items()})
    totals = {q: Counter(results[name][q]["verdict"] for name in results) for q in QUESTIONS}
    print("Totals:", {q: dict(c) for q, c in totals.items()})


if __name__ == "__main__":
    main()
