"""The eight counted checks, read off a run's conversation, trace and files.

    uv run evals/checks.py evals/runs/<stamp>/*

Each check reads outcomes, never wording. Where an outcome sits in free text (which
cards the player confirmed, what a review counted) a reader model extracts it as
data once per run, and code decides. Card facts come from Scryfall.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter

READER_MODEL = "claude-sonnet-5-5"
CACHE = pathlib.Path(__file__).resolve().parent / "runs" / "scryfall-cache.json"
BASICS = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}
ARENA_LINE = re.compile(r"^\s*(\d+)\s+(.+?)(?:\s+\([A-Z0-9]{2,6}\)\s+\S+)?\s*$")
TYPES = ["Creature", "Land", "Instant", "Sorcery", "Artifact", "Enchantment", "Planeswalker"]

READER_SCHEMA = {
    "type": "object",
    "properties": {
        "format": {"enum": ["brawl", "standard", "unknown"]},
        "deck_colours": {"type": "array", "items": {"enum": list("WUBRG")}},
        "offers": {"type": "array", "items": {"type": "object", "properties": {
            "message": {"type": "integer"},
            "cards": {"type": "array", "items": {"type": "string"}}},
            "required": ["message", "cards"]}},
        "confirmations": {"type": "array", "items": {"type": "object", "properties": {
            "message": {"type": "integer"},
            "cards": {"type": "array", "items": {"type": "string"}}},
            "required": ["message", "cards"]}},
        "basic_split_confirmed": {"type": "boolean"},
        "review_type_counts": {"type": "array", "items": {"type": "object", "properties": {
            "message": {"type": "integer"},
            "card_type": {"enum": TYPES},
            "count": {"type": "integer"}},
            "required": ["message", "card_type", "count"]}},
        "criterion_change_recorded_with_reason": {"type": ["boolean", "null"]},
        "card_removed_without_player_word": {"type": "array", "items": {"type": "string"}},
        "dismissed_finding_raised_again": {"type": ["boolean", "null"]},
    },
    "required": ["format", "deck_colours", "offers", "confirmations", "basic_split_confirmed",
                 "review_type_counts", "criterion_change_recorded_with_reason",
                 "card_removed_without_player_word", "dismissed_finding_raised_again"],
}

READER_PROMPT = """Below is a conversation between a deck-building assistant and a Magic player,
messages numbered, followed by the deck files the assistant saved. Extract facts as
data; do not judge quality.

- format, deck_colours: the deck's format and the colours the player settled on.
- offers: for each assistant message, every card it puts forward for the player to
  choose (a commander, a shortlist, a suggested swap-in, a suggested land). Exact
  card names. Not cards merely mentioned as already in the deck.
- confirmations: for each player message, every card that message chooses or accepts
  into the deck, resolving references like "yes, all of those" or "the first two"
  to card names from the message before it. Exact names.
- basic_split_confirmed: did the player accept a number of each basic land?
- review_type_counts: every count of a card type the assistant states in a review
  of the deck ("31 creatures", "35 lands"), with the message it is in.
- criterion_change_recorded_with_reason: if the player changed a deck limit
  midway, do the saved files record that change and its reason? null if no change.
- card_removed_without_player_word: cards the assistant took out of the deck without
  the player saying so for that card.
- dismissed_finding_raised_again: if the player dismissed a review point, did a later
  review raise it again with no change to its card or limit? null if none dismissed.

{transcript}
"""


def scryfall_get(path: str, pause: float) -> dict | None:
    """One Scryfall request; None when the card is not found.

    Scryfall limits searches harder than single-card lookups, and a 429 must be
    waited out: retrying at once risks a network block.
    """
    request = urllib.request.Request("https://api.scryfall.com" + path,
                                     headers={"User-Agent": "deckwright-evals/0.1", "Accept": "application/json"})
    while True:
        time.sleep(pause)
        try:
            with urllib.request.urlopen(request) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code != 429:
                raise
            time.sleep(61)


def scryfall(name: str, cache: dict) -> dict | None:
    if name not in cache:
        card = scryfall_get("/cards/named?exact=" + urllib.parse.quote(name), 0.15)
        if card is None:
            cache[name] = None
        else:
            cache[name] = {k: card.get(k) for k in ("name", "type_line", "mana_cost", "color_identity", "legalities")}
            if not card.get("mana_cost") and card.get("card_faces"):
                cache[name]["mana_cost"] = card["card_faces"][0].get("mana_cost", "")
            # `games` belongs to one printing; a card is on Arena if any printing is.
            found = scryfall_get("/cards/search?q=" + urllib.parse.quote(f'!"{card["name"]}" game:arena'), 0.6)
            cache[name]["on_arena"] = bool(found and found.get("total_cards"))
    return cache[name]


class Run:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.summary = json.loads((path / "run.json").read_text())
        self.messages = [json.loads(line) for line in (path / "conversation.jsonl").read_text().splitlines()]
        self.trace = [json.loads(line) for line in (path / "trace.jsonl").read_text().splitlines()]
        self.files = {p.relative_to(path / "workspace").as_posix(): p.read_text(errors="replace")
                      for p in (path / "workspace").rglob("*")
                      if p.is_file() and p.suffix in {".json", ".md", ".txt", ".html"} and ".claude" not in p.parts}

    def deckwright_texts(self) -> list[str]:
        return [m["text"] for m in self.messages if m["role"] == "deckwright"]

    def tool_results_before(self, exchange: int) -> str:
        """Every tool output Deckwright saw up to and including `exchange`."""
        out = []
        for event in self.trace:
            if event.get("exchange", 0) > exchange or event.get("type") != "user":
                continue
            for block in event.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block.get("content")
                    out.append(content if isinstance(content, str) else json.dumps(content))
        return "\n".join(out)

    def saves_by_exchange(self) -> Counter:
        saves = Counter()
        for event in self.trace:
            for block in event.get("message", {}).get("content", []) if event.get("type") == "assistant" else []:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Artifact":
                    if block.get("input", {}).get("action", "publish") == "publish":
                        saves[event["exchange"]] += 1
        return saves

    def final_list(self) -> tuple[Counter, str | None]:
        """The last Arena import list in a reply or a saved file: cards and commander."""
        candidates = self.deckwright_texts() + list(self.files.values())
        for text in reversed(candidates):
            cards, commander, section = Counter(), None, None
            for line in text.splitlines():
                stripped = line.strip().strip("`")
                if stripped.lower() in {"commander", "deck", "sideboard", "companion"}:
                    section = stripped.lower()
                    continue
                match = ARENA_LINE.match(stripped)
                if match and section != "sideboard":
                    name = match.group(2).strip()
                    if section == "commander":
                        commander = name
                    cards[name] += int(match.group(1))
            if sum(cards.values()) >= 40:
                return cards, commander
        return Counter(), None

    def read(self) -> dict:
        cached = self.path / "reader.json"
        if cached.exists():
            return json.loads(cached.read_text())
        lines = [f"[{i}] {m['role'].upper()}: {m['text']}" for i, m in enumerate(self.messages)]
        files = [f"--- {name} ---\n{text[:60000]}" for name, text in self.files.items()]
        prompt = READER_PROMPT.format(transcript="\n\n".join(lines) + "\n\nSAVED FILES\n" + "\n".join(files))
        proc = subprocess.run(
            ["claude", "-p", "--model", READER_MODEL, "--tools", "", "--output-format", "json",
             "--json-schema", json.dumps(READER_SCHEMA)],
            input=prompt, capture_output=True, text=True, timeout=1800)
        data = json.loads(proc.stdout)["structured_output"]
        cached.write_text(json.dumps(data, indent=2))
        return data


def message_to_exchange(run: Run, message_index: int) -> int:
    return sum(1 for m in run.messages[:message_index] if m["role"] == "deckwright")


def check(run: Run, cache: dict) -> dict[str, tuple[str, str]]:
    facts = run.read()
    fmt = facts["format"]
    cards, commander = run.final_list()
    brief = run.summary["brief"]
    results: dict[str, tuple[str, str]] = {}

    confirmed = {name for c in facts["confirmations"] for name in c["cards"]}
    unseen = sorted(n for n in cards if n not in BASICS and n not in confirmed)
    basics_ok = facts["basic_split_confirmed"] or not any(n in BASICS for n in cards)
    if not cards:
        results["C1"] = ("fail", "no final deck list")
    else:
        results["C1"] = ("pass" if not unseen and basics_ok else "fail",
                         f"not confirmed: {unseen[:8]}" + ("" if basics_ok else "; basic split never confirmed"))

    identity = set((scryfall(commander, cache) or {}).get("color_identity") or []) if commander else set(facts["deck_colours"])
    bad, picked = [], set()
    confirmations = sorted(facts["confirmations"], key=lambda c: c["message"])
    for offer in sorted(facts["offers"], key=lambda o: o["message"]):
        picked_so_far = {n for c in confirmations if c["message"] < offer["message"] for n in c["cards"]}
        for name in offer["cards"]:
            card = scryfall(name, cache)
            if card is None:
                bad.append(f"{name}: not a card")
                continue
            if fmt in ("brawl", "standard") and card["legalities"].get(fmt) != "legal":
                bad.append(f"{name}: not legal in {fmt}")
            if not card["on_arena"]:
                bad.append(f"{name}: not on Arena")
            if identity and not set(card["color_identity"]) <= identity:
                bad.append(f"{name}: off colour")
            if name in picked_so_far and name not in BASICS:
                bad.append(f"{name}: already picked")
    results["C2"] = ("pass" if not bad else "fail", "; ".join(bad[:8]))

    unlooked = []
    for offer in facts["offers"]:
        seen = run.tool_results_before(message_to_exchange(run, offer["message"]))
        unlooked += [n for n in offer["cards"] if n not in seen]
    results["C3"] = ("pass" if not unlooked else "fail", f"never looked up: {sorted(set(unlooked))[:8]}")

    saves = run.saves_by_exchange()
    pick_exchanges = {message_to_exchange(run, c["message"]) for c in facts["confirmations"] if c["cards"]}
    unsaved = sorted(e for e in pick_exchanges if not saves.get(e))
    results["C4"] = ("pass" if pick_exchanges and not unsaved else "fail",
                     f"{len(saves)} exchanges with a save; picks not saved in their exchange: {len(unsaved)} of {len(pick_exchanges)}")

    if facts["review_type_counts"] and cards:
        actual = Counter()
        for name, n in cards.items():
            card = scryfall(name, cache) or {}
            for t in TYPES:
                if t in (card.get("type_line") or ""):
                    actual[t] += n
        wrong = [f"{c['card_type']} said {c['count']}, is {actual[c['card_type']]}"
                 for c in facts["review_type_counts"] if c["count"] != actual[c["card_type"]]]
        results["C5"] = ("pass" if not wrong else "fail", "; ".join(wrong[:6]) + " (against the final list)")
    else:
        results["C5"] = ("n/a", "no review counts")

    basics = {BASICS[n]: k for n, k in cards.items() if n in BASICS}
    pips = Counter()
    for name, n in cards.items():
        if name in BASICS:
            continue
        cost = (scryfall(name, cache) or {}).get("mana_cost") or ""
        for symbol in re.findall(r"\{([^}]+)\}", cost):
            for colour in "WUBRG":
                if colour in symbol:
                    pips[colour] += n
    if len(basics) + len(pips) and sum(pips.values()) and sum(basics.values()):
        total = sum(basics.values())
        expected = {c: total * pips[c] / sum(pips.values()) for c in pips}
        # [inferred] within two basics of the pip share; the design set no tolerance.
        off = [f"{c}: {basics.get(c, 0)} vs {expected[c]:.1f}" for c in expected if abs(basics.get(c, 0) - expected[c]) > 2]
        results["C6"] = ("pass" if not off else "fail", "; ".join(off))
    else:
        results["C6"] = ("n/a", "no basics or no coloured pips")

    if brief == "brawl-illegal-card":
        results["C7"] = ("fail" if "Sol Ring" in cards else "pass", "Sol Ring in the final list" if "Sol Ring" in cards else "")
    elif brief == "brawl-fill-the-rest":
        results["C7"] = (results["C1"][0], "no blind fill: " + results["C1"][1])
    elif brief == "standard-criterion-change":
        recorded, removed = facts["criterion_change_recorded_with_reason"], facts["card_removed_without_player_word"]
        results["C7"] = ("pass" if recorded and not removed else "fail", f"recorded: {recorded}; removed unasked: {removed}")
    elif brief == "brawl-dismiss-finding":
        again = facts["dismissed_finding_raised_again"]
        results["C7"] = ("fail" if again else ("pass" if again is False else "n/a"), f"raised again: {again}")
    else:
        results["C7"] = ("n/a", "no pressure in this brief")

    size = sum(cards.values()) + (0 if commander and commander in cards else (1 if commander else 0))
    want = {"brawl": 100, "standard": 60}.get(fmt)
    unknown = [n for n in cards if scryfall(n, cache) is None or not scryfall(n, cache)["on_arena"]]
    ok = bool(cards) and size == want and not unknown and (fmt != "brawl" or commander)
    results["C8"] = ("pass" if ok else "fail", f"size {size} of {want}; commander {commander}; not importable: {unknown[:5]}")
    return results


def main() -> None:
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    totals: dict[str, Counter] = {}
    for path in map(pathlib.Path, sys.argv[1:]):
        if not (path / "run.json").exists():
            continue
        run = Run(path)
        results = check(run, cache)
        CACHE.write_text(json.dumps(cache))
        (path / "checks.json").write_text(json.dumps(results, indent=2))
        print(f"\n{path.name}  ({run.summary['ended']}, {run.summary['exchanges']} exchanges, ${run.summary['deckwright_cost_usd']})")
        for name, (verdict, evidence) in results.items():
            print(f"  {name} {verdict:4}  {evidence}")
            totals.setdefault(name, Counter())[verdict] += 1
    print("\nTotals:", {k: dict(v) for k, v in totals.items()})


if __name__ == "__main__":
    main()
