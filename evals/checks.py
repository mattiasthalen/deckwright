"""The counted checks, read off a run's conversation, trace and files.

    python3 evals/checks.py evals/runs/<stamp>/*

Each check reads outcomes, never wording. Where an outcome sits in free text (which
cards the player confirmed, what a review counted) a reader model extracts it as
data once per run, and code decides C1 to C8 and C12. C9 to C11 are the reader's
yes or no on a stated fact, with quoted evidence. S1 to S13 are the skill's
close-out criteria, decided from the deck folders and the trace where they can be,
and by the reader's facts where only the conversation says. Card facts come from
Scryfall.

What a run saved is read from the runner's record of the workspace after each
exchange (`after/<exchange>/`, `Run.states`), never guessed from the commands in
the trace: a save is an exchange whose `deck.json` changed, not a publish. A run
recorded before that record began has no `after/`, and what only the record shows
is n/a there. The deck is read from its folder in the run's workspace (ADR-0011).
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
               "narrowing_said",
               "nonbasics_offered_as_choices", "tagless_job_warned", "no_step_unasked", "departures_confirmed",
               "no_strength_or_price_question", "ladder_steps_with_counts", "suggestions_marked",
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
  choose (a commander, a category's round, a suggested swap-in, a suggested land). Exact
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
- narrowing_said: does every round say how it was narrowed from the search?
- nonbasics_offered_as_choices: are nonbasic lands offered for the player to pick,
  rather than chosen by the assistant?
- tagless_job_warned: when a category with a job was searched by rules text alone
  because it has no tag, did the assistant say the search may miss cards? Personal
  favourites has no job of its own and never counts. null if never relevant.
- no_step_unasked: does the assistant only take steps the player asked for (no
  moving to the next group, adding cards, or rewriting the plan unasked)? Writing
  the handbook and scenes of a complete deck, and packing the page, are not steps
  unasked; nor is renaming the deck's folder once the player names the deck.
  Offering the next step of the build once the player has answered the current one
  (commander choices after the last criterion, the template after the commander, a
  round after the template) is not a step unasked. Neither is saving an offer,
  review swaps included, or correcting a saved card to the exact card the player
  named when the reply says so.
- departures_confirmed: when a group ends above or below its planned size, or the
  land count changes, did the assistant say so, give a reason, and get the
  player's yes? null if it never happened.
- no_strength_or_price_question: while settling what the deck should be, does the
  assistant hold off asking how strong, competitive or casual the deck should be, or
  about budget, price or wildcards? null if no such settling happened.
- ladder_steps_with_counts: with a creature type wanted, does every round offered
  for a group show three steps under their own headings (cards of the type that do
  the job, cards that reward the type and do the job, the strongest cards for the
  job), each with how many cards that step holds in all? A further round of one
  step the player asked for needs only its heading and count. The steps overlap by
  design; do not compare their counts with each other or with a total, and do not
  judge which step a card belongs in. A creature type is a creature subtype (Rat,
  Elf); an artifact type such as Spacecraft is not. null when the deck has no
  creature type.
- suggestions_marked: does the reply that offers each round for a group mark the
  cards the assistant would take? Commanders and swaps are not a group's round.
  null if none was offered.
- you_pick_takes_the_suggested: when the player, after a round with marked cards,
  leaves the choice to the assistant ('you pick', 'go with your suggestions', 'yes,
  all of those'), does the assistant take exactly the marked cards of that round?
  'Just fill in the rest' asks for the remaining rounds with marks and is not
  itself leaving the choice; judge the answer that follows those rounds. null if
  the player never did.
- limits_question_names_crossover: when asking about the deck's limits, does the
  assistant ask one open question that names crossover cards (printings from other
  franchises) as an example of a limit, with no question or options of its own
  about them, and without saying whether to prefer or avoid them? Stating facts
  about crossover printings is allowed. null if no limits question was asked.
- commander_before_colours: in Brawl, is the commander chosen before the assistant
  asks about colours, unless the player wanted to fix colours first? null if not
  Brawl or no commander was chosen in this conversation.
- set_count_says_any_printing: whenever the assistant counts cards from a set the
  player named as a limit, does it say a card counts when any of its printings is in
  that set? Counts of crossover printings, types or the whole pool are not set
  counts. null if no set was named or no such count was made.
- terms_explained_where_first_used: is each game term, rule exception and group name
  (such as "recursion") explained in a few words where the assistant first uses it?
  null if none was used. A term counts as explained if its own sentence or the one
  just before says what it does. Search and tool words (a Scryfall tag) are not game
  terms. Evergreen keywords (flying, lifelink, vigilance) are game terms.
- name_asked_once_complete_before_handbook: does the assistant ask the player to name
  the deck once it is complete and before writing its handbook, using no name of
  its own before that? null if the deck was never complete.
- handbook_written_unasked: once the deck is complete, does the assistant write the
  handbook and scenes without first asking whether to? Announcing that the handbook
  comes next is not asking. It fails only if the assistant asked whether to write
  it. null if the deck was never complete.
- saved_categories: the card groups the SAVED FILES record, each with its planned
  number of cards (null when none is recorded). Empty if the files hold none.
- deck_counts_stated: every count the assistant states of the deck as it stands now
  (cards in the deck, in a group, of a type), one count per entry, with the message
  it is in and the words that state it ("31 Rats"). Not the template's sizes or
  targets, not the format's fixed numbers (100, 60, 35 lands), not totals of a
  search or an offer, and not sums or differences.

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
    """Every tool call: (exchange, conversation, name, input, refused, answer).

    A Bash command that exits non-zero ran, and Claude Code reports it as an error
    whose answer begins "Exit code"; any other Bash error is a command refused before
    it ran (needs approval, blocked). A publish over the account's limit is refused.
    """
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
                ran = block.get("name") == "Bash" and text.startswith("Exit code")
                refused = (bool(answer.get("is_error")) and not ran) or "publish 429" in str(content)[:300]
                yield (event.get("exchange", 0), event.get("conversation", 1), block.get("name"),
                       block.get("input", {}), refused, text)


def tool_uses(trace: list[dict]):
    """Every tool call: (exchange, conversation, name, input, refused)."""
    for *call, _ in calls(trace):
        yield tuple(call)


ARTIFACT_URL = re.compile(r"claude\.ai/(?:code/)?artifact/([\w-]+)")


def accepted_calls(trace: list[dict]):
    """Each tool call that was not refused: (exchange, name, input, answer)."""
    for exchange, _, name, given, refused, answer in calls(trace):
        if not refused:
            yield exchange, name, given, answer


def publishes(trace: list[dict]):
    """Each publish the Artifact tool accepted: (exchange, the artifact it went to, None if unnamed)."""
    for exchange, name, given, answer in accepted_calls(trace):
        if name == "Artifact" and given.get("action", "publish") == "publish":
            found = ARTIFACT_URL.search(answer) or ARTIFACT_URL.search(str(given.get("url", "")))
            yield exchange, found and found.group(1)


def publishes_by_exchange(trace: list[dict]) -> Counter:
    return Counter(exchange for exchange, _ in publishes(trace))


def copies(card: dict) -> int:
    """A saved card's count; one that is null or not a number counts as none, so one bad
    card does not stop the checks of the whole round."""
    try:
        return int(card.get("count", 1))
    except (TypeError, ValueError):
        return 0


def parsed(text: str | None) -> dict | None:
    try:
        value = json.loads(text) if text else None
    except (ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


NO_RECORD = "this run has no record of the deck folder after each exchange"

# The deck folders as one exchange left them: by path relative to the workspace, the
# parsed `deck.json` (None when it is missing or does not parse) and the ledger's lines.
State = dict[str, tuple[dict | None, list[str]]]


def read_state(folder: pathlib.Path) -> State:
    """The deck folders the runner copied under `folder`."""
    state: State = {}
    for path in sorted(p for p in folder.rglob("*") if p.is_file() and p.name in ("deck.json", "LEDGER.md")):
        deck, lines = state.get(path.parent.relative_to(folder).as_posix(), (None, []))
        text = path.read_text(errors="replace")
        if path.name == "deck.json":
            deck = parsed(text)
        else:
            lines = text.splitlines()
        state[path.parent.relative_to(folder).as_posix()] = (deck, lines)
    return state


class Run:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.summary = json.loads((path / "run.json").read_text())
        self.messages = [json.loads(line) for line in (path / "conversation.jsonl").read_text().splitlines()]
        self.trace = [json.loads(line) for line in (path / "trace.jsonl").read_text().splitlines()]
        self.files = {p.relative_to(path / "workspace").as_posix(): p.read_text(errors="replace")
                      for p in (path / "workspace").rglob("*")
                      if p.is_file() and p.suffix in {".json", ".md", ".txt", ".html"} and ".claude" not in p.parts}
        after = path / "after"
        self.start_state = read_state(after / "start") if (after / "start").is_dir() else {}
        self.states: list[State] = []
        recorded = sorted((int(p.name), p) for p in after.iterdir() if p.name.isdigit()) if after.is_dir() else []
        for exchange, folder in recorded:
            # An empty after/<n> is an exchange that left no deck folder. A missing one is
            # from a runner before 2026-11-13, which made none for such an exchange or a turn
            # that raised; it is taken to have changed nothing.
            while len(self.states) < exchange:
                self.states.append(self.state_before(len(self.states)))
            self.states.append(read_state(folder))
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

    def state_before(self, exchange: int) -> State:
        """The deck folders as the exchange found them: a run from a start begins at the start."""
        return self.states[exchange - 1] if exchange > 0 else self.start_state

    def changed_in(self, exchange: int) -> list[str]:
        """The deck folders whose `deck.json` the exchange changed or made, and left parseable."""
        before = self.state_before(exchange)
        return [folder for folder, (deck, _) in self.states[exchange].items()
                if deck is not None and deck != before.get(folder, (None, []))[0]]

    def saves_by_exchange(self) -> Counter:
        return Counter(e for e in range(len(self.states)) if self.changed_in(e))

    def deck_folder(self) -> pathlib.Path | None:
        """The folder of the last state's most recently changed deck, else the workspace's
        most recently written `deck.json`."""
        workspace = self.path / "workspace"
        if self.states:
            changed = {folder: e for e in range(len(self.states)) for folder in self.changed_in(e)}
            held = [folder for folder, (deck, _) in self.states[-1].items()
                    if deck is not None and (workspace / folder / "deck.json").is_file()]
            if held:
                return workspace / max(held, key=lambda folder: (changed.get(folder, -1), folder))
        held = [p.parent for p in workspace.rglob("deck.json") if ".claude" not in p.parts]
        # A tie goes to the name that sorts last, not to the listing's order.
        return max(held, key=lambda folder: ((folder / "deck.json").stat().st_mtime, folder.name), default=None)

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
        mine = {artifact for text in results if "Published" in text for artifact in ARTIFACT_URL.findall(text)}
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

    def list_at(self, exchange: int) -> tuple[Counter, str | None]:
        """The deck as it stood after `exchange`, as `final_list` gives it: the run's deck
        folder in that state, or the deck holding the most cards when it is not there yet
        (a folder renamed later). An exchange the runner never recorded is the last one."""
        state = self.states[min(exchange, len(self.states) - 1)]
        own = self.folder.relative_to(self.path / "workspace").as_posix() if self.folder else None
        decks = [deck for deck, _ in state.values() if deck]
        deck = state[own][0] if own in state else max(decks, key=lambda d: len(d.get("cards") or []), default=None)
        return listed(deck)

    def final_list(self) -> tuple[Counter, str | None]:
        """The deck as last saved, else the last Arena import list in a reply or a
        saved file: cards and commander."""
        deck = self.deck()
        if deck and deck.get("cards"):
            return listed(deck)
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
        # Without a deck folder in the workspace the deck is the published page's.
        if not self.folder:
            for name in ("deck.json", "LEDGER.md"):
                if source := self.page_files.get(name):
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


def listed(deck: dict | None) -> tuple[Counter, str | None]:
    """A saved deck's cards and commander. A saved card with no name is no card."""
    named = [c for c in (deck or {}).get("cards") or [] if isinstance(c, dict) and isinstance(c.get("name"), str)]
    cards = Counter()
    for card in named:
        cards[card["name"]] += copies(card)
    cards = +cards  # a card at count 0 was taken out
    commander = next((c["name"] for c in named if str(c.get("category", "")).lower() == "commander"), None)
    return cards, commander


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
    if not cards and run.summary.get("ends") and not any(c["cards"] for c in facts["confirmations"]):
        results["C1"] = ("n/a", f"the brief ends at the {run.summary['ends']}, before any card is picked")
    elif not cards:
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
    # A pick in an exchange the runner never recorded (the run died in its turn) is unseen, not unsaved.
    never_recorded = sorted(e for e in pick_exchanges if e >= len(run.states)) if run.states else []
    unsaved = sorted(pick_exchanges - set(saves) - set(never_recorded))
    saved = f"{len(saves)} exchanges with a save; picks not saved in their exchange: {len(unsaved)} of {len(pick_exchanges)}"
    unseen = unrecorded(run) + [f"exchange {e} has a pick and no record of its folder" for e in never_recorded]
    results["C4"] = verdict_of([saved] if unsaved and run.states else [], bool(pick_exchanges), unseen, saved)

    if facts["review_type_counts"] and (cards or run.states):
        wrong = []
        for said in facts["review_type_counts"]:
            reviewed, leader = run.list_at(message_to_exchange(run, said["message"])) if run.states else (cards, commander)
            # A two-faced card may be counted by its front face or by every face: a
            # review is right anywhere between the two counts.
            # A Brawl review may count the commander or only the 99, so either is right.
            t = said["card_type"]
            front = sum(n for name, n in reviewed.items() if t in type_line_of(name, cache).split(" // ")[0] and name != leader)
            any_face = sum(n for name, n in reviewed.items() if t in type_line_of(name, cache))
            if not front <= said["count"] <= any_face:
                wrong.append(f"{t} said {said['count']}, is {front if front == any_face else f'{front} to {any_face}'}")
        against = " (against the deck at that review)" if run.states else " (against the final list)"
        results["C5"] = ("pass" if not wrong else "fail", "; ".join(wrong[:6]) + against)
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
    want = DECK_SIZE.get(fmt)
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
    results["C10"] = facts_verdict(facts, ["narrowing_said", "nonbasics_offered_as_choices", "tagless_job_warned"])
    results["C11"] = facts_verdict(facts, ["no_step_unasked", "departures_confirmed"])
    results["C12"] = page_shape(run, facts, fmt, cards, cache)
    results.update(skill_checks(run, facts, fmt, cache))
    return results


def holds(facts: dict, name: str) -> bool | None:
    return facts.get(name, {"holds": None})["holds"]


def failed_facts(facts: dict, names: list[str]) -> dict[str, str]:
    """The evidence of each named fact that does not hold, by name."""
    return {n: facts[n]["evidence"] for n in names if holds(facts, n) is False}


def facts_verdict(facts: dict, names: list[str]) -> tuple[str, str]:
    failed = [f"{n}: {evidence[:90]}" for n, evidence in failed_facts(facts, names).items()]
    exercised = any(holds(facts, n) is not None for n in names)
    return ("fail" if failed else "pass" if exercised else "n/a"), "; ".join(failed)


def verdict_of(problems: list[str], exercised: bool, unseen: list[str] = (), passed: str = "") -> tuple[str, str]:
    """Fail on any problem; n/a when nothing was exercised, or when what the run does
    not show (`unseen`, each said as why) is all that stands between it and a pass."""
    if problems:
        return "fail", "; ".join(problems)
    if unseen:
        return "n/a", "; ".join(unseen)
    return ("pass", passed) if exercised else ("n/a", passed or "never came up")


def unrecorded(run: Run) -> list[str]:
    """What a check cannot see in a run with no record of its deck folders, as `verdict_of`'s unseen."""
    return [] if run.states else [NO_RECORD]


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
# Any Scryfall address: one with its scheme, or a host with a path ("api.scryfall.com/cards/…").
# A bare "Scryfall.com" in prose names the site and links nowhere.
SCRYFALL_LINK = re.compile(r"https?://(?:[\w-]+\.)*scryfall\.(?:com|io)(?:/[^\s)\]>\"'<]*)?"
                           r"|(?:[\w-]+\.)*scryfall\.(?:com|io)/[^\s)\]>\"'<]*", re.I)
PICTURE = re.compile(r"!\[[^\]]*\]\([^)]*\)|<img\b[^>]*>", re.I)
SCRYFALL_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def skill_checks(run: Run, facts: dict, fmt: str, cache: dict) -> dict[str, tuple[str, str]]:
    deck = run.deck()
    rounds = rounds_on_offer(run)
    return {
        "S1": saved_and_published(run, facts),
        "S2": round_shown(run, facts),
        "S3": ladder_shown(run, facts, rounds),
        "S4": suggestions_marked(run, facts, rounds),
        "S5": crossover_marked(run, facts, rounds, cache),
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
    size = sum(copies(c) for c in deck.get("cards") or [] if isinstance(c, dict))
    return size == DECK_SIZE.get(str(deck.get("format", "")).lower())


def rounds_on_offer(run: Run) -> list[tuple[dict, set[str]]]:
    """Each distinct `offer` the deck folders held after an exchange, with the categories
    of the deck that held it, lowercased and without the commander (deck.example.json
    lists the commander as a category, and a commander offer is no category's round)."""
    found: dict[str, tuple[dict, set[str]]] = {}
    for state in run.states:
        for deck, _ in state.values():
            if deck and isinstance(deck.get("offer"), dict):
                categories = {str(c.get("name", "")).lower() for c in deck.get("categories") or [] if isinstance(c, dict)}
                found.setdefault(json.dumps(deck["offer"], sort_keys=True), (deck["offer"], categories - {"commander"}))
    return list(found.values())


def category_rounds(rounds: list[tuple[dict, set[str]]]) -> list[dict]:
    return [o for o, categories in rounds if str(o.get("category", "")).lower() in categories]


def groups_of(offer) -> list[dict]:
    return [g for g in offer.get("groups") or [] if isinstance(g, dict)] if isinstance(offer, dict) else []


def offered_cards(offer) -> list[dict]:
    return [c for g in groups_of(offer) for c in g.get("cards") or [] if isinstance(c, dict)]


def copies_held(name: str, state: State) -> int:
    """Copies of the card `name` across the deck folders of a state."""
    return sum(copies(c) for deck, _ in state.values() if deck for c in deck.get("cards") or []
               if isinstance(c, dict) and isinstance(c.get("name"), str) and faces(c["name"]) & faces(name))


def saved_and_published(run: Run, facts: dict) -> tuple[str, str]:
    """S1: each pick adds the card to `deck.json` (or raises its count) and a ledger line
    naming it, in its exchange; a publish only once the player asks for a link, and
    always to the same artifact. That a failed publish is said in one line is the
    conversation's, and not checked."""
    picks: dict[int, list[str]] = {}
    # The reader may split one message's picks over several confirmations.
    for c in facts["confirmations"]:
        if c["cards"]:
            picks.setdefault(message_to_exchange(run, c["message"]), []).extend(c["cards"])
    problems = []
    for e, names in sorted(picks.items()):
        if e >= len(run.states):
            continue
        before, after = run.state_before(e), run.states[e]
        gained = Counter(line for _, lines in after.values() for line in lines)
        gained -= Counter(line for _, lines in before.values() for line in lines)
        for name in names:
            if copies_held(name, after) <= copies_held(name, before):
                problems.append(f"{name} (exchange {e}) not added to deck.json")
            if not any(named_in(name, line.lower()) for line in gained):
                problems.append(f"{name} (exchange {e}) has no new line in LEDGER.md")
    asked = [message_to_exchange(run, i) for i, m in enumerate(run.messages)
             if m["role"] == "player" and LINK_ASKED.search(m["text"])]
    done = list(publishes(run.trace))
    unasked = [e for e, _ in done if not asked or e < min(asked)]
    if unasked:
        problems.append(f"published in exchanges {unasked} with no link asked for")
    artifacts = list(dict.fromkeys(a for _, a in done if a))
    if len(artifacts) > 1:
        problems.append(f"published to {len(artifacts)} artifacts: {artifacts}")
    return verdict_of(problems, bool(picks or done), unrecorded(run) if picks else [],
                      f"{len(picks)} picks added to deck.json and LEDGER.md; {len(done)} publishes")


def packed_file(command: str, answer: str) -> str | None:
    """The file a Bash call running `pack.py` packed, by name; None if it packed nothing.

    pack.py prints `<deck folder name>.html`, and a later step of the same chain may
    print other pages (an `ls` of the folder lists its `index.html`). With the folder
    argument known, a printed page of its name is the packed file; otherwise it is the
    last printed page that is not `index.html` (an argument such as `"$deck"` names no
    page). A command that exited non-zero packed only if it printed the page: a later
    step of a chain may have failed.
    """
    printed = [pathlib.PurePath(path).name for path in re.findall(r"[^\s'\"]+\.html", answer)]
    folder = re.search(r"pack\.py\s+['\"]?([^\s'\";&|]+)", command)
    folder_name = pathlib.PurePath(folder.group(1)).name if folder else ""  # `pack.py .` names none
    wanted = f"{folder_name}.html" if folder_name else None
    pages = [page for page in printed if page != "index.html"]
    if wanted in pages:
        return wanted
    if answer.startswith("Exit code") and not pages:
        return None
    return pages[-1] if pages else wanted or "the packed file"


def swaps_gained(state: State, before: State) -> list[str]:
    """The names of the review swaps (maybeboard entries of kind `swap`) a state holds
    that the state before it did not."""
    def swaps(s: State) -> list[dict]:
        return [c for deck, _ in s.values() if deck for c in deck.get("maybeboard") or []
                if isinstance(c, dict) and c.get("kind") == "swap"]
    held = swaps(before)
    return [c["name"] for c in swaps(state) if c not in held and isinstance(c.get("name"), str)]


def round_shown(run: Run, facts: dict) -> tuple[str, str]:
    """S2: after each exchange that offers cards the deck folder holds them, as `offer`
    or as review swaps the maybeboard gained in it (at least half of the cards the
    reader saw offered in it, a two-faced card matched by a face); each exchange that
    offers cards or saves ran `pack.py`, and its reply names the packed file, a link
    given beside it or not; no reply gives a Scryfall URL or shows a picture. A file
    sent into the chat is not judged: the runner disallows the tool."""
    problems = []
    packed: dict[int, str] = {}
    for e, name, given, answer in accepted_calls(run.trace):
        command = str(given.get("command", "")) if name == "Bash" else ""
        if "pack.py" in command and (page := packed_file(command, answer)):
            packed[e] = page
    shown: dict[int, list[str]] = {}
    for o in sorted(facts["offers"], key=lambda o: o["message"]):
        if o["cards"]:
            shown.setdefault(message_to_exchange(run, o["message"]), []).extend(o["cards"])
    saves = run.saves_by_exchange()
    replies = {message_to_exchange(run, i): m["text"] for i, m in enumerate(run.messages) if m["role"] == "deckwright"}
    for e in sorted(set(shown) | set(saves)):
        names = shown.get(e, [])
        if names and e < len(run.states):
            held = [c["name"] for deck, _ in run.states[e].values() if deck
                    for c in offered_cards(deck.get("offer")) if isinstance(c.get("name"), str)]
            held += swaps_gained(run.states[e], run.state_before(e))
            on_offer = [n for n in names if any(faces(n) & faces(h) for h in held)]
            if not held:
                problems.append(f"exchange {e} offers cards and its deck folder holds no offer after it")
            elif 2 * len(on_offer) < len(names):
                problems.append(f"exchange {e} offers {names[:6]} and its deck folder's offer holds "
                                f"{len(on_offer)} of them after it")
        doing = "offers cards" if names else "saves"
        if e not in packed:
            problems.append(f"exchange {e} {doing} and never runs pack.py")
        elif packed[e] not in replies.get(e, ""):
            problems.append(f"exchange {e}'s reply does not name the packed file {packed[e]}")
    for text in run.deckwright_texts():
        problems += [f"a Scryfall URL in a reply: {link}" for link in SCRYFALL_LINK.findall(text)]
        problems += [f"a card picture in a reply: {image}" for image in PICTURE.findall(text)]
    return verdict_of(problems, bool(facts["offers"] or saves), unrecorded(run) if facts["offers"] else [])


def ladder_shown(run: Run, facts: dict, rounds: list[tuple[dict, set[str]]]) -> tuple[str, str]:
    """S3: with a creature type wanted, a category's round shows each step under its
    heading with its full count; a round of more than one step shows all three, about
    ten cards in all. A further round of one step is the player's to ask for (ADR-0012),
    so it passes only after a round of three steps of its category.

    Only a round as first shown is held to about ten: an offer whose cards were all in
    the previous offer of its category is that round shrinking as picks come off. The
    Lands round is never held to it."""
    names = ["ladder_steps_with_counts"]
    problems = list(failed_facts(facts, names).values())
    ladders = category_rounds(rounds) if holds(facts, names[0]) is not None else []
    laddered: set[str] = set()
    previous: dict[str, set[str]] = {}
    for offer in ladders:
        category = str(offer.get("category", "")).lower()
        steps, called = groups_of(offer), f"the {offer.get('category', 'unnamed')} round"
        cards = {str(c.get("name")) for c in offered_cards(offer)}
        shrunk = category in previous and cards <= previous[category]
        previous[category] = cards
        for step in steps:
            if not step.get("heading"):
                problems.append(f"{called} has a step with no heading")
            if not isinstance(step.get("total"), int):
                problems.append(f"{called}: '{step.get('heading')}' states no full count")
        if len(steps) == 1:
            if category not in laddered:
                problems.append(f"{called} is of one step, and no earlier round of its category showed three")
            continue
        if len(steps) == 3:
            laddered.add(category)
        else:
            problems.append(f"{called} shows {len(steps)} steps of the ladder, not 3")
        # 6 to 14 cards for ADR-0012's "about ten", as decided on 2026-11-13.
        if not (shrunk or category == "lands" or 6 <= len(offered_cards(offer)) <= 14):
            problems.append(f"{called} offers {len(offered_cards(offer))} cards, not about ten")
    return verdict_of(problems, holds(facts, names[0]) is not None or bool(ladders), unrecorded(run))


def suggestions_marked(run: Run, facts: dict, rounds: list[tuple[dict, set[str]]]) -> tuple[str, str]:
    """S4: every round of one of the deck's categories marks the cards the tutor would
    take, and its reply says so; every card of the round carries its reason; "you pick"
    takes the marked cards."""
    names = ["suggestions_marked", "you_pick_takes_the_suggested"]
    problems = list(failed_facts(facts, names).values())
    judged = category_rounds(rounds)
    for o in judged:
        called = f"the {o.get('category', 'unnamed')} round on offer"
        if not any(c.get("suggested") for c in offered_cards(o)):
            problems.append(f"{called} marks no card suggested")
        unreasoned = [c.get("name") for c in offered_cards(o) if not str(c.get("reason") or "").strip()]
        if unreasoned:
            problems.append(f"{called} gives no reason for: {unreasoned[:8]}")
    return verdict_of(problems, any(holds(facts, n) is not None for n in names) or bool(judged), unrecorded(run))


def printing(scryfall_id: str, cache: dict) -> dict | None:
    """One printing's crossover facts, cached under its API path."""
    key = f"/cards/{scryfall_id}"
    if key not in cache:
        found = scryfall_get(key, 0.1) if SCRYFALL_ID.fullmatch(str(scryfall_id)) else None
        cache[key] = found and {**{k: found.get(k) for k in ("id", "name", "games", "promo_types", "flavor_name")},
                                "card_faces": [{"name": f.get("name"), "flavor_name": f.get("flavor_name")}
                                               for f in found.get("card_faces") or []]}
    return cache[key]


def crossover_marked(run: Run, facts: dict, rounds: list[tuple[dict, set[str]]], cache: dict) -> tuple[str, str]:
    """S5: the limits question names crossover cards; every card offered in a crossover
    printing is marked so, under the name Arena prints, and is a printing Arena has.
    Whether the picture is the newest Arena printing, and whether the tutor said
    another exists, are not checked."""
    names = ["limits_question_names_crossover"]
    problems = list(failed_facts(facts, names).values())
    crossovers = 0
    for card in (c for o, _ in rounds for c in offered_cards(o)):
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
            problems.append(f"{name}: a crossover printing unmarked")
        if "arena" not in (found.get("games") or []):
            problems.append(f"{name}: a crossover printing Arena does not have, so its printed name is not Arena's")
        if printed and card.get("printed_name") != printed:
            problems.append(f"{name}: printed_name {card.get('printed_name')!r}, Arena prints {printed!r}")
    return verdict_of(list(dict.fromkeys(problems)), holds(facts, names[0]) is not None or bool(crossovers),
                      unrecorded(run))


# A file name printed beside a count ("backup-31.json") holds no count.
FILE_NAME = re.compile(r"\S+\.(?:json|md|html?|py|jpe?g|png|txt|csv)\b", re.I)
TRACEBACK = "Traceback (most recent call last):"


def script_output(answer: str) -> str:
    """What a command printed itself: without the "Exit code N" line Claude Code puts
    before a command that failed, and without a Python traceback, from its first line
    on, whose line numbers are no count. What a failed command printed before it stays."""
    return re.sub(r"\AExit code \d+\n?", "", answer).split(TRACEBACK)[0]


def counts_from_scripts(run: Run, facts: dict) -> tuple[str, str]:
    """S8: an exchange that states a count of the deck ran a python3 command that
    printed the number stated, the first whole number in the reader's `said`. A stated
    0 needs only that such a command printed something: a count by category often
    leaves out the category that has none. The command need not name `deck.json`,
    since a script may import a helper that holds the path. A count said without
    digits is not judged, since no number can be found for it."""
    answers: dict[int, list[str]] = {}
    for e, name, given, answer in accepted_calls(run.trace):
        if name == "Bash" and re.search(r"\bpython3?\b", str(given.get("command", ""))):
            answers.setdefault(e, []).append(answer)

    def printed(outputs: list[str], number: str) -> bool:
        outputs = [script_output(out) for out in outputs]
        if number == "0":
            return any(out.strip() for out in outputs)
        return any(re.search(rf"(?<![\w.]){number}(?!\w|\.\d)", FILE_NAME.sub(" ", out)) for out in outputs)

    problems, judged = [], 0
    for stated in facts.get("deck_counts_stated", []):
        number = re.search(r"\d+", stated["said"])
        if not number:
            continue
        judged += 1
        e, number = message_to_exchange(run, stated["message"]), str(int(number.group(0)))
        if not printed(answers.get(e, []), number):
            problems.append(f"'{stated['said']}' (exchange {e}) with no python3 command printing it in its exchange")
    return verdict_of(problems, bool(judged), passed="" if judged or not facts.get("deck_counts_stated")
                      else "every count was said without digits")


def plain(text: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", text.lower()).split())


def name_given(run: Run, facts: dict, deck: dict | None) -> tuple[str, str]:
    """S10: no deck folder holds a name before the deck is first complete; then the name
    is one the player gives in a message after the exchange that made it complete, when
    the tutor asks for it."""
    names = ["name_asked_once_complete_before_handbook"]
    completed = next((e for e, state in enumerate(run.states) if any(complete(d) for d, _ in state.values())), None)
    problems = [f"named {d['name']!r} before the deck was complete" for state in run.states[:completed]
                for d, _ in state.values() if d and d.get("name") and not complete(d)]
    problems += failed_facts(facts, names).values()
    name = str((deck or {}).get("name") or "")
    if name and run.states:
        said = [plain(m["text"]) for i, m in enumerate(run.messages) if m["role"] == "player"
                and (completed is None or message_to_exchange(run, i) > completed)]
        if not any(plain(name) in s for s in said):
            problems.append(f"{name!r} is not a name the player gave")
    if complete(deck) and not name:
        problems.append("the complete deck has no name")
    return verdict_of(list(dict.fromkeys(problems)), bool(name) or holds(facts, names[0]) is not None, unrecorded(run))


def handbook_written(facts: dict, deck: dict | None) -> tuple[str, str]:
    """S11: a complete deck has its handbook and scenes, written without asking."""
    if not complete(deck):
        return "n/a", "the deck is not complete"
    problems = [f"the complete deck has no {part}" for part in ("handbook", "scenes") if not deck.get(part)]
    problems += failed_facts(facts, ["handbook_written_unasked"]).values()
    return verdict_of(problems, True)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"['’]", "", text.lower())).strip("-")


def renames(run: Run) -> list[tuple[str, str, list[str]]]:
    """Each deck folder gone after an exchange while a new one carries on its ledger (its
    ledger starts with the old one's lines, at least one entry among them): the old
    folder, the new one, and the new one's lines beyond the old, as last recorded."""
    found = []
    for e, state in enumerate(run.states):
        before = run.state_before(e)
        for old, (_, old_lines) in before.items():
            if old in state or not any(line.startswith("- ") for line in old_lines):
                continue
            for new, (_, lines) in state.items():
                if new not in before and lines[:len(old_lines)] == old_lines:
                    last = next(s[new][1] for s in reversed(run.states) if new in s)
                    found.append((old, new, last[len(old_lines):]))
    return found


NAME_LINE = re.compile(r"·\s*name\s*·")


def folder_named(run: Run, deck: dict | None) -> tuple[str, str]:
    """S12: the folder is `<format>-<theme>` until the deck is named, `<format>-<name>`
    after, numbered from 2 when taken; a rename is a `name` line in the ledger. A theme
    folder may be made of some of the theme's words, singular or plural (`brawl-tokens`
    for "Creature tokens", `brawl-rats` for "Rat typal"). A run from a start is judged
    only once its ledger gains a `name` line: until then its folder is the runner's.

    The deck's name is `deck.json`'s alone. A `name` line records a rename
    (`deck → brawl-creature-tokens` in one of its `·` fields) and never names the
    deck: the folder after the last such line's `→` must be the deck's folder, or it
    numbered."""
    if not run.folder or not deck:
        return "n/a", "no deck folder"
    name = deck.get("name")
    at_start = {line for _, lines in run.start_state.values() for line in lines} if run.summary.get("start") else set()
    ledger = run.folder / "LEDGER.md"
    name_lines = [line for line in (ledger.read_text(errors="replace").splitlines() if ledger.is_file() else [])
                  if NAME_LINE.search(line) and line not in at_start]
    if run.summary.get("start") and not name_lines:
        return "n/a", "began from a start, in the folder the runner names"
    theme = next((c.get("text") for c in deck.get("criteria") or [] if isinstance(c, dict) and c.get("kind") == "theme"), None)
    by = name or theme
    if not by:
        return "n/a", "the deck has neither a name nor a theme to name its folder by"
    fmt, folder = str(deck.get("format", "")).lower(), run.folder.name
    base = f"{fmt}-{slug(by)}"

    def theme_word(word: str) -> bool:
        return any(word == t or word in singulars(t) or t in singulars(word) for t in slug(by).split("-"))

    def fits(words: str) -> bool:
        return words == slug(by) or (not name and bool(words) and all(map(theme_word, words.split("-"))))

    problems = []
    rest = folder.removeprefix(f"{fmt}-") if folder.startswith(f"{fmt}-") else ""
    numbered = re.fullmatch(r"(.+)-(\d+)", rest)
    if fits(rest):
        pass
    elif numbered and fits(numbered.group(1)):
        free = f"{fmt}-{numbered.group(1)}"
        if int(numbered.group(2)) < 2 or not (run.folder.parent / free).is_dir():
            problems.append(f"{folder} is numbered though {free} is free")
    else:
        problems.append(f"the deck is in {folder}, not {base}")
    targets = [words[0].strip("`'\"") for line in name_lines for field in line.split("·") if "→" in field
               if (words := field.split("→", 1)[1].split())]
    if targets:
        target = pathlib.PurePath(targets[-1]).name
        if not re.fullmatch(re.escape(target) + r"(-\d+)?", folder):
            problems.append(f"the deck is in {folder}, and its ledger's last name line renames it to {target}")
    problems += [f"the rename of {old} to {new} is not a name line in its ledger" for old, new, lines in renames(run)
                 if not any(NAME_LINE.search(line) for line in lines)]
    return verdict_of(problems, True, unrecorded(run))


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
