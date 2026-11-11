"""The counted checks, read off a run's conversation, trace and files.

    python3 evals/checks.py evals/runs/<stamp>/*

Each check reads outcomes, never wording. Where an outcome sits in free text (which
cards the player confirmed, what a review counted) a reader model extracts it as
data once per run, and code decides C1 to C8 and C12. C9 to C11 are the reader's
yes or no on a stated fact, with quoted evidence. Card facts come from Scryfall.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

import headless

READER_MODEL = "claude-sonnet-5-5"
CACHE = pathlib.Path(__file__).resolve().parent / "runs" / "scryfall-cache.json"
BASICS = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}
ARENA_LINE = re.compile(r"^\s*(\d+)\s+(.+?)(?:\s+\([A-Z0-9]{2,6}\)\s+\S+)?\s*$")
TYPES = ["Creature", "Land", "Instant", "Sorcery", "Artifact", "Enchantment", "Planeswalker"]

FACT = {"type": "object", "properties": {"holds": {"type": ["boolean", "null"]}, "evidence": {"type": "string"}},
        "required": ["holds", "evidence"]}
EXTRA_FACTS = ["one_question_per_intent_message", "remaining_stated_after_each_answer", "no_card_search_before_criteria",
               "type_shown_before_broader", "broader_count_stated_and_waited", "narrowing_said",
               "nonbasics_offered_as_choices", "tagless_job_warned", "no_step_unasked", "departures_confirmed",
               "no_strength_or_price_question"]

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
        **dict.fromkeys(EXTRA_FACTS, FACT),
        "saved_categories": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "target": {"type": ["integer", "null"]}},
            "required": ["name", "target"]}},
    },
    "required": ["format", "deck_colours", "offers", "confirmations", "basic_split_confirmed",
                 "review_type_counts", "criterion_change_recorded_with_reason",
                 "card_removed_without_player_word", "dismissed_finding_raised_again",
                 *EXTRA_FACTS, "saved_categories"],
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

Each of the following is a fact with `holds` (true, false, or null when the
situation never came up) and a short quoted `evidence`:
- one_question_per_intent_message: while settling what the deck should be (format,
  theme, colours, limits), does every assistant message ask at most one question?
- remaining_stated_after_each_answer: after each of those answers, and before the
  commander is chosen, does the assistant say how many options the player's limits
  leave and which limit narrows them most?
- no_card_search_before_criteria: does the assistant hold off offering deck cards
  (other than commanders) until format, theme, colours and limits are settled?
- type_shown_before_broader: with a creature type wanted, are cards of that type
  offered before cards outside it in each group?
- broader_count_stated_and_waited: does the assistant say how many cards a broader
  step would add, and broaden only after the player says so?
- narrowing_said: does every shortlist say how it was narrowed from the search?
- nonbasics_offered_as_choices: are nonbasic lands offered for the player to pick,
  rather than chosen by the assistant?
- tagless_job_warned: when a group of cards had no ready-made search, did the
  assistant say its search may miss cards? null if never relevant.
- no_step_unasked: does the assistant only take steps the player asked for (no
  moving to the next group, adding cards, or rewriting the plan unasked)?
- departures_confirmed: when a group ends above or below its planned size, or the
  land count changes, did the assistant say so, give a reason, and get the
  player's yes? null if it never happened.
- no_strength_or_price_question: while settling what the deck should be, does the
  assistant hold off asking how strong, competitive or casual the deck should be, or
  about budget, price or wildcards? null if no such settling happened.
- saved_categories: the card groups the SAVED FILES record, each with its planned
  number of cards (null when none is recorded). Empty if the files hold none.

{transcript}
"""


def scryfall_get(path: str, pause: float) -> dict | None:
    """One Scryfall request; None when the card is not found.

    Scryfall allows two searches or name lookups a second, and a 429 locks the
    caller out for 30 seconds: wait it out, since retrying at once risks a ban.
    """
    request = urllib.request.Request("https://api.scryfall.com" + path,
                                     headers={"User-Agent": "deckwright-evals/0.1", "Accept": "application/json"})
    for attempt in range(5):
        time.sleep(pause)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code != 429:
                raise
            time.sleep(61)
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Scryfall unreachable for {path}")


def spells(name: str, real: str) -> bool:
    """`name` spells the card `real`: the same name, a face of it, or the start of a
    face of a two-faced card ("Riverglide" for Riverglide Pathway // Lavaglide Pathway).
    Commas and apostrophes are ignored."""
    plain = lambda text: re.sub(r"[,']", "", text).strip()
    parts = {plain(part).lower() for g in faces(real) for part in g.split(",")}  # "Lord Skitter, Sewer King"
    return any(plain(f) == plain(g) or ("//" in real and plain(g).startswith(plain(f))) or plain(f) in parts
               for f in faces(name) for g in faces(real))


def scryfall(name: str, cache: dict) -> dict | None:
    # An entry a looser rule stored under a name that does not spell it is not that card.
    if cache.get(name) and not spells(name, cache[name]["name"]):
        del cache[name]
    if name not in cache:
        card = scryfall_get("/cards/named?exact=" + urllib.parse.quote(name), 0.5)
        if card is None:
            # A two-faced card may be spelled by one face or with a shortened face;
            # fuzzy finds those, and is kept only when a face really matches.
            near = scryfall_get("/cards/named?fuzzy=" + urllib.parse.quote(name), 0.5)
            if near and spells(name, near["name"]):
                card = near
        if card is None:
            cache[name] = None
        else:
            cache[name] = {k: card.get(k) for k in ("name", "type_line", "mana_cost", "color_identity", "legalities")}
            if not card.get("mana_cost") and card.get("card_faces"):
                cache[name]["mana_cost"] = card["card_faces"][0].get("mana_cost", "")
            # `games` belongs to one printing; a card is on Arena if any printing is.
            exact = card["name"].replace('"', '\\"')
            found = scryfall_get("/cards/search?q=" + urllib.parse.quote(f'!"{exact}" game:arena'), 0.6)
            cache[name]["on_arena"] = bool(found and found.get("total_cards"))
    return cache[name]


def tool_uses(trace: list[dict]):
    """Every tool call: (exchange, conversation, name, input, refused)."""
    errors = {block.get("tool_use_id") for event in trace if event.get("type") == "user"
              for block in event.get("message", {}).get("content", [])
              if isinstance(block, dict) and block.get("type") == "tool_result" and (
                  block.get("is_error") or "publish 429" in str(block.get("content"))[:300])}
    for event in trace:
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                yield (event.get("exchange", 0), event.get("conversation", 1), block.get("name"),
                       block.get("input", {}), block.get("id") in errors)


def saves_by_exchange(trace: list[dict]) -> Counter:
    """Publishes the Artifact tool accepted, by exchange."""
    saves = Counter()
    for exchange, _, name, given, refused in tool_uses(trace):
        if name == "Artifact" and given.get("action", "publish") == "publish" and not refused:
            saves[exchange] += 1
    return saves


class Run:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.summary = json.loads((path / "run.json").read_text())
        self.messages = [json.loads(line) for line in (path / "conversation.jsonl").read_text().splitlines()]
        self.trace = [json.loads(line) for line in (path / "trace.jsonl").read_text().splitlines()]
        self.files = {p.relative_to(path / "workspace").as_posix(): p.read_text(errors="replace")
                      for p in (path / "workspace").rglob("*")
                      if p.is_file() and p.suffix in {".json", ".md", ".txt", ".html"} and ".claude" not in p.parts}
        self.published = self.last_published()
        # The start as the run began: runs copy it in; older runs predate the copy.
        start = path / "start" / "deck.json"
        self.start = json.loads(start.read_text()) if start.exists() else None

    def tool_uses(self):
        return tool_uses(self.trace)

    def last_published(self) -> dict[str, pathlib.Path]:
        """The page's files as the publishes left them, by published path, read from disk now.

        A page's files may sit outside the workspace (the session scratchpad), and
        relative sources resolve against the workspace.
        """
        files: dict[str, pathlib.Path] = {}
        for _, _, name, given, refused in self.tool_uses():
                if name != "Artifact" or refused:
                    continue
                if given.get("action", "publish") != "publish" or not str(given.get("file_path", "")).endswith(".html"):
                    continue
                workspace = self.path / "workspace"
                page = workspace / given["file_path"]
                # A relative source resolves against `root` or the session's working
                # directory, which a `cd` may have moved; try the likely ones.
                bases = [workspace / given["root"]] if given.get("root") else [workspace, page.parent]

                def resolve(source: str) -> pathlib.Path:
                    return next((b / source for b in bases if (b / source).exists()), bases[0] / source)

                sources = {"index.html": page}
                listed = given.get("files") or {}
                if isinstance(listed, list):  # the list form publishes each file at its own spelling
                    listed = {(item if isinstance(item, str) else item.get("path")): (item if isinstance(item, str) else item.get("path"))
                              for item in listed if isinstance(item, str) or isinstance(item, dict)}
                for published, source in listed.items():
                    if isinstance(source, dict):
                        source = source.get("from")
                    if isinstance(source, str):
                        sources[published] = resolve(source)
                # A publish adds or replaces files and keeps the rest, as the artifact does.
                files.update(sources)
        return {k: v for k, v in files.items() if v.exists()}

    def deck(self) -> dict | None:
        source = self.published.get("deck.json")
        try:
            return json.loads(source.read_text()) if source else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def foreign_paths(self) -> list[str]:
        """Tool calls that reached outside the run: another run's files, memory, or a
        page in the account's gallery this run did not publish."""
        own = str(self.path.resolve())
        scratch = f"{self.path.parent.name}-{self.path.name}-workspace"  # the run's session scratchpad
        results = [json.dumps(e.get("message", {}).get("content", [])) for e in self.trace if e.get("type") == "user"]
        mine = {url for text in results if "Published" in text
                for url in re.findall(r"claude\.ai/(?:code/)?artifact/[\w-]+", text)}
        hits = []
        for _, _, name, given, _ in self.tool_uses():
            text = json.dumps(given)
            reaches_out = "/evals/runs/" in text or "/claude/memory/" in text
            if reaches_out and own not in text and scratch not in text:
                hits.append(text[:120])
            # Listing the gallery shows titles only; reading another page is reaching out.
            if name == "Artifact" and given.get("action") in ("read", "delete") and given.get("url"):
                if not any(m in given["url"] for m in mine):
                    hits.append(f"Artifact {given['action']} {given['url']}")
        return hits

    def deckwright_texts(self) -> list[str]:
        return [m["text"] for m in self.messages if m["role"] == "deckwright"]

    def tool_results_before(self, exchange: int) -> str:
        """Every tool output Deckwright saw in this conversation up to and including `exchange`."""
        conversation = next((e.get("conversation", 1) for e in self.trace if e.get("exchange") == exchange), 1)
        out = []
        for event in self.trace:
            if event.get("exchange", 0) > exchange or event.get("type") != "user":
                continue
            if event.get("conversation", 1) != conversation:
                continue
            for block in event.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block.get("content")
                    out.append(content if isinstance(content, str) else json.dumps(content))
        return "\n".join(out)

    def saves_by_exchange(self) -> Counter:
        return saves_by_exchange(self.trace)

    def final_list(self) -> tuple[Counter, str | None]:
        """The deck as last published, else the last Arena import list in a reply or a
        saved file: cards and commander."""
        deck = self.deck()
        if deck and deck.get("cards"):
            cards = Counter()
            for card in deck["cards"]:
                cards[card["name"]] += int(card.get("count", 1))
            cards = +cards  # a card at count 0 was taken out
            commander = next((c["name"] for c in deck["cards"] if str(c.get("category", "")).lower() == "commander"), None)
            return cards, commander
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
        saved = dict(self.files)
        for name in ("deck.json", "LEDGER.md"):
            if name in self.published:
                saved[f"published {name}"] = self.published[name].read_text(errors="replace")
        files = [f"--- {name} ---\n{text[:60000]}" for name, text in saved.items()]
        prompt = READER_PROMPT.format(transcript="\n\n".join(lines) + "\n\nSAVED FILES\n" + "\n".join(files))
        proc = headless.claude(["--model", READER_MODEL, "--tools", "", "--output-format", "json",
                                "--json-schema", json.dumps(READER_SCHEMA)], prompt, timeout=1800)
        try:
            data = json.loads(proc.stdout)["structured_output"]
        except (json.JSONDecodeError, KeyError) as error:
            raise RuntimeError(f"the reader gave no structured output for {self.path.name}") from error
        cached.write_text(json.dumps(data, indent=2))
        return data


def faces(name: str) -> set[str]:
    """A card's name and each face's, lowercased: the reader and Arena spell a
    two-faced card in full, by its front face, or with a shortened face."""
    parts = [part.strip().lower() for part in name.split("//")]
    return {name.strip().lower(), *[p for p in parts if p]}


def start_cards(run: Run) -> set[str]:
    """The cards of the half-built deck a run began from: chosen before the run, so
    confirmed and already picked."""
    return {c["name"] for c in run.start["cards"]} if run.start else set()


def named_in(name: str, text: str) -> bool:
    """A card name stands in the text as a whole name, not inside another word."""
    return any(re.search(r"(?<![\w'])" + re.escape(face) + r"(?![\w'])", text) for face in faces(name))


def message_to_exchange(run: Run, message_index: int) -> int:
    return sum(1 for m in run.messages[:message_index] if m["role"] == "deckwright")


def check(run: Run, cache: dict) -> dict[str, tuple[str, str]]:
    facts = run.read()
    fmt = facts["format"]
    cards, commander = run.final_list()
    brief = run.summary["brief"]
    results: dict[str, tuple[str, str]] = {}

    started = start_cards(run)
    confirmed = {face for name in started | {n for c in facts["confirmations"] for n in c["cards"]} for face in faces(name)}
    unseen = sorted(n for n in cards if n not in BASICS and not faces(n) & confirmed)
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
        picked_so_far = {face for n in started | {n for c in confirmations if c["message"] < offer["message"] for n in c["cards"]}
                         for face in faces(n)}
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
            # A Standard card is offered again for more copies; a Brawl card never.
            if fmt == "brawl" and faces(name) & picked_so_far and name not in BASICS:
                bad.append(f"{name}: already picked")
    results["C2"] = ("pass" if not bad else "fail", "; ".join(bad[:8]))

    unlooked = []
    for offer in facts["offers"]:
        seen = run.tool_results_before(message_to_exchange(run, offer["message"]))
        seen = seen.lower()
        unlooked += [n for n in offer["cards"] if not named_in(n, seen)]
    results["C3"] = ("pass" if not unlooked else "fail", f"never looked up: {sorted(set(unlooked))[:8]}")

    saves = run.saves_by_exchange()
    pick_exchanges = {message_to_exchange(run, c["message"]) for c in facts["confirmations"] if c["cards"]}
    unsaved = sorted(e for e in pick_exchanges if not saves.get(e))
    results["C4"] = (("n/a" if not pick_exchanges else "pass" if not unsaved else "fail"),
                     f"{len(saves)} exchanges with a save; picks not saved in their exchange: {len(unsaved)} of {len(pick_exchanges)}")

    if facts["review_type_counts"] and cards:
        # A two-faced card may be counted by its front face or by every face: a
        # review is right anywhere between the two counts.
        # A Brawl review may count the commander or only the 99, so either is right.
        front, any_face = Counter(), Counter()
        for name, n in cards.items():
            type_line = type_line_of(name, cache)
            for t in TYPES:
                front[t] += n * (t in type_line.split(" // ")[0]) * (name != commander)
                any_face[t] += n * (t in type_line)

        def counted(t: str) -> str:
            return str(front[t]) if front[t] == any_face[t] else f"{front[t]} to {any_face[t]}"
        wrong = [f"{c['card_type']} said {c['count']}, is {counted(c['card_type'])}"
                 for c in facts["review_type_counts"] if not front[c["card_type"]] <= c["count"] <= any_face[c["card_type"]]]
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
    if sum(pips.values()) and sum(basics.values()):
        total = sum(basics.values())
        expected = {c: total * pips[c] / sum(pips.values()) for c in set(pips) | set(basics)}
        # [inferred] within two basics of the pip share; the design set no tolerance.
        off = [f"{c}: {basics.get(c, 0)} vs {expected[c]:.1f}" for c in sorted(expected)
               if abs(basics.get(c, 0) - expected[c]) > 2]
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

    size = sum(cards.values()) + int(bool(commander) and commander not in cards)
    want = {"brawl": 100, "standard": 60}.get(fmt)
    unknown = [n for n in cards if not (scryfall(n, cache) or {}).get("on_arena")]
    ok = bool(cards) and size == want and not unknown and (fmt != "brawl" or commander)
    if run.summary.get("ends"):
        results["C8"] = ("n/a", f"the brief ends at the {run.summary['ends']}")
    else:
        results["C8"] = ("pass" if ok else "fail", f"size {size} of {want}; commander {commander}; not importable: {unknown[:5]}")
    def fact(name: str) -> bool | None:
        return facts.get(name, {"holds": None})["holds"]

    def combine(names: list[str]) -> tuple[str, str]:
        failed = [f"{n}: {facts[n]['evidence'][:90]}" for n in names if fact(n) is False]
        exercised = any(fact(n) is not None for n in names)
        return ("fail" if failed else "pass" if exercised else "n/a"), "; ".join(failed)

    # Checks added after the bare round of 2026-11-10, one per group of criteria
    # the bare runs failed (decided: a check only where a bare run fails).
    results["C9"] = (("n/a", "began from a half-built deck: no intent interview") if started else
                     combine(["one_question_per_intent_message", "remaining_stated_after_each_answer",
                              "no_card_search_before_criteria", "no_strength_or_price_question"]))
    results["C10"] = combine(["type_shown_before_broader", "broader_count_stated_and_waited", "narrowing_said",
                              "nonbasics_offered_as_choices", "tagless_job_warned"])
    results["C11"] = combine(["no_step_unasked", "departures_confirmed"])
    results["C12"] = page_shape(run, facts, fmt, cards, cache)
    return results


def type_line_of(name: str, cache: dict) -> str:
    return (scryfall(name, cache) or {}).get("type_line") or ""


def singulars(word: str) -> set[str]:
    """The forms a plural creature type may come from: elves → elf, zombies → zombie,
    faeries → faerie, foxes → fox, rats → rat."""
    forms = {word, word[:-1], word[:-2]}
    if word.endswith("ves"):
        forms |= {word[:-3] + "f", word[:-3] + "fe"}
    if word.endswith("ies"):
        forms.add(word[:-3] + "y")
    return {form for form in forms if len(form) > 1}


def page_shape(run: Run, facts: dict, fmt: str, cards: Counter, cache: dict) -> tuple[str, str]:
    """The deck is a published page of plain files in the template's shape."""
    problems = []
    if "index.html" not in run.published:
        problems.append("no page published")
    for name in ("deck.json", "LEDGER.md"):
        if name not in run.published:
            problems.append(f"no {name} published")
    if not any(k.startswith("cards/") and k.endswith(".jpg") for k in run.published):
        problems.append("no card images published")
    # A two-faced spell with a land back is a spell: a land counts by its front face.
    lands = sum(n for name, n in cards.items() if "Land" in type_line_of(name, cache).split(" // ")[0])
    want_lands = {"brawl": 35, "standard": 24}.get(fmt)
    if want_lands and lands != want_lands and not run.summary.get("ends"):
        problems.append(f"{lands} lands, template says {want_lands}")
    # A target off the template is a departure, which C11 judges; the shape is the number of jobs.
    categories = [c for c in facts["saved_categories"] if c["name"].lower() not in ("commander", "lands", "land")]
    shape = {"brawl": (8, 8), "standard": (9, 4)}.get(fmt)
    if shape and len(categories) != shape[0]:
        problems.append(f"{len(categories)} categories {[c['name'] for c in categories][:10]}, template has {shape[0]}")
    creature_types = {kind.lower() for name in cards for face in type_line_of(name, cache).split(" // ")
                      if "Creature" in face and "—" in face for kind in face.split("—")[1].split()}
    # Categories a half-built start already had were not Deckwright's to name.
    inherited = {c["name"] for c in run.start["categories"]} if run.start else set()
    typal = [c["name"] for c in categories if c["name"] not in inherited
             and any(singulars(word) & creature_types for word in c["name"].lower().replace("-", " ").split())]
    if typal:
        problems.append(f"creature-type categories: {typal}")
    return ("pass" if not problems else "fail", "; ".join(problems))


def main() -> None:
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    totals: dict[str, Counter] = {}
    for path in map(pathlib.Path, sys.argv[1:]):
        if not (path / "run.json").exists():
            print(f"\n{path.name}  DIED: no run.json, so the run never finished")
            totals.setdefault("died", Counter())["runs"] += 1
            continue
        run = Run(path)
        results = check(run, cache)
        CACHE.write_text(json.dumps(cache))
        (path / "checks.json").write_text(json.dumps(results, indent=2))
        print(f"\n{path.name}  ({run.summary['ended']}, {run.summary['exchanges']} exchanges, ${run.summary['deckwright_cost_usd']})")
        if foreign := run.foreign_paths():
            print(f"  CONTAMINATED: reached outside its run: {foreign[:3]}")
        for name, (verdict, evidence) in results.items():
            print(f"  {name} {verdict:4}  {evidence}")
            totals.setdefault(name, Counter())[verdict] += 1
    print("\nTotals:", {k: dict(v) for k, v in totals.items()})


if __name__ == "__main__":
    main()
