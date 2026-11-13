"""The counted checks, read off a run's conversation, trace and files.

    python3 evals/checks.py evals/runs/<stamp>/*

Each check reads outcomes, never wording. Where an outcome sits in free text (which
cards the player confirmed, what a review counted) a reader model extracts it as
data once per run, and code decides C1 to C8 and C12. C9 to C11 are the reader's
yes or no on a stated fact, with quoted evidence. S1 to S13 are the skill's
close-out criteria, decided from the trace and the deck folder where they can be,
and by the reader's facts where only the conversation says. Card facts come from
Scryfall.

The deck is read from its folder in the run's workspace (ADR-0011): the folder of
the last `deck.json` the trace wrote, else the one the workspace holds. A save is
a write of `deck.json`, not a publish.
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
               "no_strength_or_price_question", "ladder_steps_with_counts", "suggestions_marked_with_reasons",
               "you_pick_takes_the_suggested", "limits_question_names_crossover", "commander_before_colours",
               "set_count_says_any_printing", "terms_explained_where_first_used",
               "name_asked_once_complete_before_handbook", "handbook_written_unasked"]

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
        "deck_counts_stated": {"type": "array", "items": {"type": "object", "properties": {
            "message": {"type": "integer"}, "said": {"type": "string"}},
            "required": ["message", "said"]}},
    },
    "required": ["format", "deck_colours", "offers", "confirmations", "basic_split_confirmed",
                 "review_type_counts", "criterion_change_recorded_with_reason",
                 "card_removed_without_player_word", "dismissed_finding_raised_again",
                 *EXTRA_FACTS, "saved_categories", "deck_counts_stated"],
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
- ladder_steps_with_counts: with a creature type wanted, does every set of cards
  offered for a group show three steps under their own headings (cards of the type
  that do the job, cards that reward the type and do the job, the strongest cards
  for the job), each with how many cards that step holds in all? null if no
  creature type was wanted.
- suggestions_marked_with_reasons: does every set of cards offered for a group mark
  the ones the assistant would take, each with a reason? null if none was offered.
- you_pick_takes_the_suggested: when the player leaves a choice to the assistant
  ("you pick", "go with your suggestion", "fill in the rest"), does the assistant
  take exactly the cards it had already marked, rather than suggesting anew? null
  if the player never did.
- limits_question_names_crossover: when asking about the deck's limits, does the
  assistant name crossover cards (printings from other franchises) as an example of
  a limit, without saying whether to prefer or avoid them? null if no limits
  question was asked.
- commander_before_colours: in Brawl, is the commander chosen before the assistant
  asks about colours, unless the player wanted to fix colours first? null if not
  Brawl or no commander was chosen in this conversation.
- set_count_says_any_printing: whenever the assistant counts cards "from a set", does
  it say a card counts when any of its printings is in that set? null if no such
  count.
- terms_explained_where_first_used: is each game term, rule exception and group name
  (such as "recursion") explained in a few words where the assistant first uses it?
  null if none was used.
- name_asked_once_complete_before_handbook: does the assistant ask the player to name
  the deck once it is complete and before writing its handbook, using no name of
  its own before that? null if the deck was never complete.
- handbook_written_unasked: once the deck is complete, does the assistant write the
  handbook and scenes without first asking whether to? null if the deck was never
  complete.
- saved_categories: the card groups the SAVED FILES record, each with its planned
  number of cards (null when none is recorded). Empty if the files hold none.
- deck_counts_stated: every number the assistant states about the deck as it stands
  (its cards, lands, creatures, cards of a type or of a group), with the message it
  is in and the words that state it ("31 Rats"). Not counts of search results.

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


def calls(trace: list[dict]):
    """Every tool call: (exchange, conversation, name, input, refused, answer)."""
    answers = {block.get("tool_use_id"): block for event in trace if event.get("type") == "user"
               for block in event.get("message", {}).get("content", [])
               if isinstance(block, dict) and block.get("type") == "tool_result"}
    for event in trace:
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                answer = answers.get(block.get("id"), {})
                content = answer.get("content")
                text = content if isinstance(content, str) else json.dumps(content)
                refused = bool(answer.get("is_error")) or "publish 429" in str(content)[:300]
                yield (event.get("exchange", 0), event.get("conversation", 1), block.get("name"),
                       block.get("input", {}), refused, text)


def tool_uses(trace: list[dict]):
    """Every tool call: (exchange, conversation, name, input, refused)."""
    for *call, _ in calls(trace):
        yield tuple(call)


ARTIFACT_URL = re.compile(r"claude\.ai/(?:code/)?artifact/([\w-]+)")


def publishes(trace: list[dict]):
    """Each publish the Artifact tool accepted: (exchange, the artifact it went to, None if unnamed)."""
    for exchange, _, name, given, refused, answer in calls(trace):
        if name == "Artifact" and given.get("action", "publish") == "publish" and not refused:
            found = ARTIFACT_URL.search(answer) or ARTIFACT_URL.search(str(given.get("url", "")))
            yield exchange, found and found.group(1)


def publishes_by_exchange(trace: list[dict]) -> Counter:
    return Counter(exchange for exchange, _ in publishes(trace))


SCRIPT_RUN = re.compile(r"\bpython3?\s+(?:-\S+\s+)*['\"]?([^\s'\";&|]+\.py)")


def commands(trace: list[dict]):
    """Each accepted Bash command: (exchange, text, unseen).

    `text` is the command followed by every script it runs that the trace wrote;
    `unseen` is true when it runs a script the trace does not show, whose effect
    cannot be told. Running `pack.py`, the skill's own, is not unseen.
    """
    scripts: dict[str, str] = {}
    for exchange, _, name, given, refused, _ in calls(trace):
        if refused:
            continue
        if name == "Write" and str(given.get("file_path", "")).endswith(".py"):
            scripts[given["file_path"]] = given.get("content", "")
        if name != "Bash":
            continue
        command = given.get("command", "")
        text, unseen = command, False
        for script in SCRIPT_RUN.findall(command):
            if pathlib.PurePath(script).name == "pack.py":
                continue
            script = script.removeprefix("./")
            shown = next((t for path, t in scripts.items() if path == script or path.endswith("/" + script)), None)
            if shown is None:
                unseen = True
            else:
                text += "\n" + shown
        yield exchange, text, unseen


def written_in(text: str, filename: str) -> bool:
    """A command or script writes a file named `filename`, by what it says."""
    name = re.escape(filename)
    target = rf"['\"]?[^\s'\"();&|]*{name}"
    return bool(re.search(rf"open\([^)]*{name}['\"]\s*,\s*['\"][wa]", text)
                or re.search(rf">>?\s*{target}", text)
                or re.search(rf"\btee\s+(?:-a\s+)?{target}", text)
                or re.search(rf"\bsed\s+-i\b[^;&|]*{name}", text)
                or (filename in text and re.search(r"write_text\(|\.write\(" + (r"|json\.dump\(" if filename.endswith(".json") else ""), text)))


def writes(trace: list[dict], filename: str):
    """Each accepted write of a file named `filename`: (exchange, path, text).

    `path` is as the call names it, None when a command names the file without its
    folder. `text` is what wrote it: the content, the edit's new text, or the
    command with its scripts; None for a command running a script the trace does
    not show, which may or may not have written the file.
    """
    bash = iter(commands(trace))
    for exchange, _, name, given, refused, _ in calls(trace):
        if name == "Bash" and not refused:
            _, text, unseen = next(bash)
            if written_in(text, filename):
                found = re.search(rf"[^\s'\"();&|=]*{re.escape(filename)}", text)
                yield exchange, (found.group(0) if found and "/" in found.group(0) else None), text
            elif unseen:
                yield exchange, None, None
            continue
        if refused or pathlib.PurePath(str(given.get("file_path", ""))).name != filename:
            continue
        if name == "Write":
            yield exchange, given["file_path"], given.get("content", "")
        elif name == "Edit":
            yield exchange, given["file_path"], given.get("new_string", "")


def saves_by_exchange(trace: list[dict]) -> Counter:
    """Writes of `deck.json` the trace shows, by exchange."""
    return Counter(exchange for exchange, _, text in writes(trace, "deck.json") if text is not None)


def parsed(text: str | None) -> dict | None:
    try:
        value = json.loads(text) if text else None
    except (ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


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
        self.folder = self.deck_folder()
        # Runs before ADR-0011 kept the deck only as a published page.
        self.page_files = ({p.relative_to(self.folder).as_posix(): p for p in self.folder.rglob("*") if p.is_file()}
                           if self.folder else self.published)
        # The start as the run began: runs copy it in; older runs predate the copy.
        start = path / "start" / "deck.json"
        self.start = json.loads(start.read_text()) if start.exists() else None

    def tool_uses(self):
        return tool_uses(self.trace)

    def deck_folder(self) -> pathlib.Path | None:
        """The folder of the last `deck.json` the trace wrote, else the one the workspace holds."""
        workspace = self.path / "workspace"
        named = [path for _, path, text in writes(self.trace, "deck.json") if path and text is not None]
        if named and (workspace / named[-1]).is_file():  # an absolute path joins as itself
            return (workspace / named[-1]).parent
        held = [p.parent for p in workspace.rglob("deck.json") if ".claude" not in p.parts]
        return max(held, key=lambda folder: (folder / "deck.json").stat().st_mtime, default=None)

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
        source = self.page_files.get("deck.json")
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
        """The deck as last saved, else the last Arena import list in a reply or a
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
        # A page holds no fact the reader is asked for, and a packed one is mostly pictures.
        saved = {name: text for name, text in self.files.items() if not name.endswith(".html")}
        workspace = (self.path / "workspace").resolve()
        for name in ("deck.json", "LEDGER.md"):
            source = self.page_files.get(name)
            if source and workspace not in source.resolve().parents:
                saved[f"published {name}"] = source.read_text(errors="replace")
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
    unsaved, unseen = unsaved_picks(run, pick_exchanges, "deck.json")
    results["C4"] = (("n/a" if not pick_exchanges or (unseen and not unsaved) else "pass" if not unsaved else "fail"),
                     f"{len(saves)} exchanges with a save; picks not saved in their exchange: {len(unsaved)} of {len(pick_exchanges)}"
                     + (f"; a script the trace does not show may have saved exchanges {unseen}" if unseen else ""))

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
    # Checks added after the bare round of 2026-11-10, one per group of criteria
    # the bare runs failed (decided: a check only where a bare run fails).
    results["C9"] = (("n/a", "began from a half-built deck: no intent interview") if started else
                     facts_verdict(facts, ["one_question_per_intent_message", "remaining_stated_after_each_answer",
                                           "no_card_search_before_criteria", "no_strength_or_price_question"]))
    results["C10"] = facts_verdict(facts, ["type_shown_before_broader", "broader_count_stated_and_waited",
                                           "narrowing_said", "nonbasics_offered_as_choices", "tagless_job_warned"])
    results["C11"] = facts_verdict(facts, ["no_step_unasked", "departures_confirmed"])
    results["C12"] = page_shape(run, facts, fmt, cards, cache)
    results.update(skill_checks(run, facts, fmt, cache))
    return results


def holds(facts: dict, name: str) -> bool | None:
    return facts.get(name, {"holds": None})["holds"]


def facts_verdict(facts: dict, names: list[str]) -> tuple[str, str]:
    failed = [f"{n}: {facts[n]['evidence'][:90]}" for n in names if holds(facts, n) is False]
    exercised = any(holds(facts, n) is not None for n in names)
    return ("fail" if failed else "pass" if exercised else "n/a"), "; ".join(failed)


def verdict_of(problems: list[str], exercised: bool, unseen: list[str] = (), passed: str = "") -> tuple[str, str]:
    """Fail on any problem; n/a when nothing was exercised, or when what could not be
    told from the trace is all that stands between the run and a pass."""
    if problems:
        return "fail", "; ".join(problems)
    if unseen:
        return "n/a", "cannot tell from the trace: " + "; ".join(unseen)
    return ("pass", passed) if exercised else ("n/a", passed or "never came up")


def unsaved_picks(run: Run, pick_exchanges: set[int], filename: str) -> tuple[list[int], list[int]]:
    """The pick exchanges that wrote no `filename`, and those where only a script the trace does not show may have."""
    by_exchange: dict[int, list] = {}
    for e, _, text in writes(run.trace, filename):
        by_exchange.setdefault(e, []).append(text)
    missing = sorted(e for e in pick_exchanges if e not in by_exchange)
    unseen = sorted(e for e in pick_exchanges if e in by_exchange and all(t is None for t in by_exchange[e]))
    return missing, unseen


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
    """The deck is a folder of plain files in the template's shape."""
    problems = []
    for name in ("index.html", "deck.json", "LEDGER.md"):
        if name not in run.page_files:
            problems.append(f"no {name} in the deck folder")
    if not any(k.startswith("cards/") and k.endswith(".jpg") for k in run.page_files):
        problems.append("no card images in the deck folder")
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


# ---------- S1 to S13: the skill's close-out criteria ----------

DECK_SIZE = {"brawl": 100, "standard": 60}
LINK_ASKED = re.compile(r"\b(link|url)\b", re.I)
SCRYFALL_LINK = re.compile(r"\]\(\s*https?://[^)\s]*scryfall\.(?:com|io)[^)\s]*\)|https?://(?:www\.)?scryfall\.com/card\S*"
                           r"|https?://cards\.scryfall\.io\S*")
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
SCRYFALL_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def skill_checks(run: Run, facts: dict, fmt: str, cache: dict) -> dict[str, tuple[str, str]]:
    deck = run.deck()
    rounds = offers_seen(run)
    return {
        "S1": saved_and_published(run, facts),
        "S2": round_shown(run, facts),
        "S3": ladder_shown(facts, rounds),
        "S4": suggestions_marked(facts, rounds),
        "S5": crossover_marked(facts, rounds, cache),
        "S6": (("n/a", "Standard has no commander") if fmt != "brawl"
               else facts_verdict(facts, ["commander_before_colours"])),
        "S7": facts_verdict(facts, ["set_count_says_any_printing"]),
        "S8": counts_from_scripts(run, facts),
        "S9": facts_verdict(facts, ["terms_explained_where_first_used"]),
        "S10": name_given(run, facts, deck),
        "S11": handbook_written(facts, deck),
        "S12": folder_named(run, deck),
        "S13": layouts_saved(deck),
    }


def complete(deck: dict | None) -> bool:
    if not deck:
        return False
    size = sum(int(c.get("count", 1)) for c in deck.get("cards") or [] if isinstance(c, dict))
    return size == DECK_SIZE.get(str(deck.get("format", "")).lower())


def offers_seen(run: Run) -> list[dict]:
    """Every round the run put on offer that the trace's writes or the deck folder show in full."""
    decks = [parsed(text) for _, _, text in writes(run.trace, "deck.json")] + [run.deck()]
    found = {}
    for deck in decks:
        if deck and isinstance(deck.get("offer"), dict):
            found[json.dumps(deck["offer"], sort_keys=True)] = deck["offer"]
    return list(found.values())


def groups_of(offer: dict) -> list[dict]:
    return [g for g in offer.get("groups") or [] if isinstance(g, dict)]


def offered_cards(offer: dict) -> list[dict]:
    return [c for g in groups_of(offer) for c in g.get("cards") or [] if isinstance(c, dict)]


def saved_and_published(run: Run, facts: dict) -> tuple[str, str]:
    """S1: each pick writes `deck.json` and `LEDGER.md`; a publish only once the player
    asks for a link, and always to the same artifact. That a failed publish is said in
    one line is the conversation's, and not checked."""
    picks = {message_to_exchange(run, c["message"]): c["cards"] for c in facts["confirmations"] if c["cards"]}
    problems, unseen = [], []
    for filename in ("deck.json", "LEDGER.md"):
        missing, unsure = unsaved_picks(run, set(picks), filename)
        problems += [f"{', '.join(picks[e][:3])} (exchange {e}) never written to {filename}" for e in missing]
        unseen += [f"{filename} in exchange {e} may have been written by a script" for e in unsure]
    asked = [message_to_exchange(run, i) for i, m in enumerate(run.messages)
             if m["role"] == "player" and LINK_ASKED.search(m["text"])]
    done = list(publishes(run.trace))
    unasked = [e for e, _ in done if not asked or e < min(asked)]
    if unasked:
        problems.append(f"published in exchanges {unasked} with no link asked for")
    artifacts = list(dict.fromkeys(a for _, a in done if a))
    if len(artifacts) > 1:
        problems.append(f"published to {len(artifacts)} artifacts: {artifacts}")
    return verdict_of(problems, bool(picks or done), unseen,
                      f"{len(picks)} picks written to deck.json and LEDGER.md; {len(done)} publishes")


def round_shown(run: Run, facts: dict) -> tuple[str, str]:
    """S2: each exchange that offers cards writes them to `deck.json` as `offer`, runs
    `pack.py` and names the packed file; no reply links a card to Scryfall or shows a
    picture, and no picture is sent alone."""
    problems, unseen = [], []
    written: dict[int, list] = {}
    for e, _, text in writes(run.trace, "deck.json"):
        written.setdefault(e, []).append(text)
    packed: dict[int, str] = {}
    for e, _, name, given, refused, answer in calls(run.trace):
        command = str(given.get("command", "")) if name == "Bash" else ""
        if refused or "pack.py" not in command:
            continue
        printed = re.findall(r"[^\s'\"]+\.html", answer)
        folder = re.search(r"pack\.py\s+['\"]?([^\s'\";&|]+)", command)
        packed[e] = (pathlib.PurePath(printed[-1]).name if printed
                     else f"{pathlib.PurePath(folder.group(1)).name}.html" if folder else "the packed file")
    for e, message in sorted({message_to_exchange(run, o["message"]): o["message"] for o in facts["offers"] if o["cards"]}.items()):
        texts = written.get(e, [])
        if not any(puts_on_offer(t) for t in texts if t is not None):
            if None in texts:
                unseen.append(f"exchange {e}'s offer may have been written by a script")
            else:
                problems.append(f"exchange {e} offers cards and writes no offer to deck.json")
        if e not in packed:
            problems.append(f"exchange {e} offers cards and never runs pack.py")
        elif packed[e] not in (run.messages[message]["text"] if message < len(run.messages) else ""):
            problems.append(f"exchange {e}'s reply does not name the packed file {packed[e]}")
    for text in run.deckwright_texts():
        problems += [f"a card linked to scryfall.com: {link}" for link in SCRYFALL_LINK.findall(text)]
        problems += [f"a card picture in a reply: {image}" for image in MARKDOWN_IMAGE.findall(text)]
    for _, _, name, given, refused in run.tool_uses():
        sent = json.dumps(given)
        if name == "SendUserFile" and not refused and re.search(r"\.(jpe?g|png)\b", sent):
            problems.append(f"a card picture sent alone: {sent[:100]}")
    return verdict_of(problems, bool(facts["offers"]), unseen)


def puts_on_offer(text: str) -> bool:
    """A write of `deck.json` holds an offer: a whole file by its content, an edit or a
    command by naming it."""
    deck = parsed(text)
    return bool(deck.get("offer")) if deck is not None else "offer" in text


def ladder_shown(facts: dict, rounds: list[dict]) -> tuple[str, str]:
    """S3: a round with a creature type shows the ladder's three steps, each headed and
    with its full count, about ten cards in all."""
    problems = [facts["ladder_steps_with_counts"]["evidence"]] if holds(facts, "ladder_steps_with_counts") is False else []
    ladders = [o for o in rounds if any(g.get("heading") for g in groups_of(o))]
    for offer in ladders:
        steps, called = groups_of(offer), f"the {offer.get('category', 'unnamed')} round"
        if len(steps) != 3:
            problems.append(f"{called} shows {len(steps)} steps of the ladder, not 3")
        for step in steps:
            if not step.get("heading"):
                problems.append(f"{called} has a step with no heading")
            if not isinstance(step.get("total"), int):
                problems.append(f"{called}: '{step.get('heading')}' states no full count")
        # [inferred] 8 to 12 cards for ADR-0012's "about ten".
        if not 8 <= len(offered_cards(offer)) <= 12:
            problems.append(f"{called} offers {len(offered_cards(offer))} cards, not about ten")
    return verdict_of(problems, holds(facts, "ladder_steps_with_counts") is not None or bool(ladders))


def suggestions_marked(facts: dict, rounds: list[dict]) -> tuple[str, str]:
    """S4: every round marks the cards the tutor would take; "you pick" takes those."""
    names = ["suggestions_marked_with_reasons", "you_pick_takes_the_suggested"]
    problems = [facts[n]["evidence"] for n in names if holds(facts, n) is False]
    problems += [f"the {o.get('category', 'unnamed')} round on offer marks no card suggested"
                 for o in rounds if not any(c.get("suggested") for c in offered_cards(o))]
    return verdict_of(problems, any(holds(facts, n) is not None for n in names) or bool(rounds))


def printing(scryfall_id: str, cache: dict) -> dict | None:
    """One printing's crossover facts, cached under its API path."""
    key = f"/cards/{scryfall_id}"
    if key not in cache:
        found = scryfall_get(key, 0.1) if SCRYFALL_ID.fullmatch(str(scryfall_id)) else None
        cache[key] = found and {**{k: found.get(k) for k in ("id", "name", "games", "promo_types", "flavor_name")},
                                "card_faces": [{"name": f.get("name"), "flavor_name": f.get("flavor_name")}
                                               for f in found.get("card_faces") or []]}
    return cache[key]


def crossover_marked(facts: dict, rounds: list[dict], cache: dict) -> tuple[str, str]:
    """S5: the limits question names crossover cards; every card offered in a crossover
    printing is marked so, under the name Arena prints. Whether the picture is the newest
    Arena printing, and whether the tutor said another exists, are not checked."""
    problems = ([facts["limits_question_names_crossover"]["evidence"]]
                if holds(facts, "limits_question_names_crossover") is False else [])
    crossovers = 0
    for card in (c for o in rounds for c in offered_cards(o)):
        found = printing(card.get("scryfall_id", ""), cache)
        if not found:
            continue
        name = card.get("name")
        if "universesbeyond" not in (found.get("promo_types") or []):
            if card.get("crossover"):
                problems.append(f"{name} is marked crossover, and its printing is not")
            continue
        crossovers += 1
        printed = found.get("flavor_name") or next((f.get("flavor_name") for f in (found.get("card_faces") or [])[:1]), None)
        if not card.get("crossover"):
            problems.append(f"{name}: a crossover printing offered unmarked")
        if printed and card.get("printed_name") != printed:
            problems.append(f"{name}: printed_name {card.get('printed_name')!r}, Arena prints {printed!r}")
    return verdict_of(problems, holds(facts, "limits_question_names_crossover") is not None or bool(crossovers))


def counts_from_scripts(run: Run, facts: dict) -> tuple[str, str]:
    """S8: an exchange that states a count of the deck ran a python3 script over `deck.json`."""
    counted, unsure = set(), set()
    for e, text, unseen in commands(run.trace):
        if re.search(r"\bpython3?\b", text) and "deck.json" in text:
            counted.add(e)
        elif unseen:
            unsure.add(e)
    problems, unseen = [], []
    for stated in facts.get("deck_counts_stated", []):
        e = message_to_exchange(run, stated["message"])
        if e in counted:
            continue
        (unseen if e in unsure else problems).append(f"'{stated['said']}' (exchange {e}) with no python3 script "
                                                     "over deck.json in its exchange")
    return verdict_of(problems, bool(facts.get("deck_counts_stated")), unseen)


def plain(text: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", text.lower()).split())


def name_given(run: Run, facts: dict, deck: dict | None) -> tuple[str, str]:
    """S10: no name before the deck is complete; then the name the player gives."""
    problems = []
    for early in (parsed(text) for _, _, text in writes(run.trace, "deck.json")):
        if early and early.get("name") and not complete(early):
            problems.append(f"named {early['name']!r} before the deck was complete")
    if holds(facts, "name_asked_once_complete_before_handbook") is False:
        problems.append(facts["name_asked_once_complete_before_handbook"]["evidence"])
    name = (deck or {}).get("name")
    said = [plain(m["text"]) for m in run.messages if m["role"] == "player"]
    if name and not any(plain(name) in s for s in said):
        problems.append(f"{name!r} is not a name the player gave")
    if complete(deck) and not name:
        problems.append("the complete deck has no name")
    return verdict_of(list(dict.fromkeys(problems)),
                      bool(name) or holds(facts, "name_asked_once_complete_before_handbook") is not None)


def handbook_written(facts: dict, deck: dict | None) -> tuple[str, str]:
    """S11: a complete deck has its handbook and scenes, written without asking."""
    if not complete(deck):
        return "n/a", "the deck is not complete"
    problems = [f"the complete deck has no {part}" for part in ("handbook", "scenes") if not deck.get(part)]
    if holds(facts, "handbook_written_unasked") is False:
        problems.append(facts["handbook_written_unasked"]["evidence"])
    return verdict_of(problems, True)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"['’]", "", text.lower())).strip("-")


def folder_named(run: Run, deck: dict | None) -> tuple[str, str]:
    """S12: the folder is `<format>-<theme>` until the deck is named, `<format>-<name>`
    after, numbered from 2 when taken; a rename is a ledger line."""
    if run.summary.get("start"):
        return "n/a", "began from a start, in the folder the runner names"
    if not run.folder or not deck:
        return "n/a", "no deck folder"
    theme = next((c.get("text") for c in deck.get("criteria") or [] if isinstance(c, dict) and c.get("kind") == "theme"), None)
    by = deck.get("name") or theme
    if not by:
        return "n/a", "the deck has neither a name nor a theme to name its folder by"
    base, folder = f"{str(deck.get('format', '')).lower()}-{slug(by)}", run.folder.name
    problems = []
    numbered = re.fullmatch(rf"{re.escape(base)}(?:-(\d+))?", folder)
    if not numbered:
        problems.append(f"the deck is in {folder}, not {base}")
    elif numbered.group(1) and (int(numbered.group(1)) < 2 or not (run.folder.parent / base).is_dir()):
        problems.append(f"{folder} is numbered though {base} is free")
    earlier = {pathlib.PurePath(path).parent.name for _, path, _ in writes(run.trace, "deck.json") if path} - {folder}
    moved = any(re.search(rf"\bmv\b.*\b{re.escape(folder)}\b", text) for _, text, _ in commands(run.trace))
    ledger = run.page_files.get("LEDGER.md")
    if (earlier or moved) and not any(folder in line for line in (ledger.read_text().splitlines() if ledger else [])):
        problems.append(f"the rename to {folder} is not a line in the ledger")
    return verdict_of(problems, True)


def layouts_saved(deck: dict | None) -> tuple[str, str]:
    """S13: every card's copy saves its `layout`."""
    cards = [c for c in (deck or {}).get("cards") or [] if isinstance(c, dict)]
    missing = [c.get("name") for c in cards if "layout" not in (c.get("copy") or {})]
    return verdict_of([f"no layout in the copy of: {missing[:8]}"] if missing else [], bool(cards))


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
