# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Everything in a deckwright interview that can be computed: lookups, the deck file, the tally, the page.

The skill judges; this script counts, checks and renders. Run it as `uv run deck.py <command>`;
`uv run deck.py --help` lists the commands. Card facts come from Scryfall and nowhere else.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import http.client
import json
import os
import re
import sys
import time
import tomllib
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

VERSION = "0.1.0"
HERE = Path(__file__).resolve().parent
SCRYFALL = "https://api.scryfall.com"
# Scryfall limits cards/named to 2 requests a second (its other endpoints allow 10).
REQUEST_GAP = 0.5
STRIPPED_KEYS = re.compile(r"price|purchase|image|tcgplayer|cardmarket", re.I)
ANY_NUMBER = "a deck can have any number of cards named"
UP_TO = re.compile(r"a deck can have up to (\w+) cards named")
NUMBER_WORDS = {w: n for n, w in enumerate("one two three four five six seven eight nine ten".split(), 1)}

EXIT_NOT_RECORDED = 4


class Failure(Exception):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


class Unreachable(Failure):
    def __init__(self, name: str, reason: str):
        super().__init__(f"Scryfall could not be reached to look up {name!r} ({reason}). Nothing was recorded.", 3)


class RateLimited(Failure):
    def __init__(self, name: str):
        super().__init__(
            f"Scryfall rate-limited the lookup of {name!r} (HTTP 429). Nothing was recorded. "
            "Wait 30 seconds before looking anything else up.",
            3,
        )


def comparable(name: str) -> str:
    """A name as Scryfall matches it: case, accents and punctuation ignored."""
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    return "".join(c for c in decomposed if c.isascii() and c.isalnum())


def names_of(card: dict) -> list[str]:
    return [card["name"], *card["name"].split(" // ")]


# Lookups -----------------------------------------------------------------------------


class Scryfall:
    def __init__(self, cache: Path):
        self.cache = cache
        self.base = os.environ.get("DECKWRIGHT_SCRYFALL_API") or SCRYFALL
        self.last_request = 0.0

    def lookup(self, query: str) -> dict:
        """One `{"query", "result", "card"}` entry. Raises Unreachable when Scryfall cannot answer."""
        card = self._cached(query)
        if card is None:
            self._cache_file(query).unlink(missing_ok=True)
            card = self._fetch(query, "exact") or self._fetch(query, "fuzzy")
            if card is None:
                return {"query": query, "result": "not_found"}
            self.cache.mkdir(parents=True, exist_ok=True)
            self._cache_file(query).write_text(json.dumps(card, ensure_ascii=False, indent=1), encoding="utf-8")
        names = [card["name"], *(face.get("name", "") for face in card.get("card_faces", []))]
        found = comparable(query) in (comparable(n) for n in names)
        return {"query": query, "result": "found" if found else "closest_match", "card": fixed_fields(card)}

    def _cache_file(self, query: str) -> Path:
        key = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
        if not key or not query.isascii():
            digest = hashlib.sha256(query.casefold().encode("utf-8")).hexdigest()[:12]
            key = f"{key}-{digest}" if key else digest
        return self.cache / f"{key}.json"

    def _cached(self, query: str) -> dict | None:
        """The cached card, or None when there is none or the file does not hold a card."""
        path = self._cache_file(query)
        if not path.is_file():
            return None
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        return card if isinstance(card, dict) and card.get("object") == "card" and "name" in card else None

    def _fetch(self, query: str, mode: str) -> dict | None:
        """The card Scryfall names for the query, or None on Scryfall's own 404."""
        wait = self.last_request + REQUEST_GAP - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        url = f"{self.base}/cards/named?{urllib.parse.urlencode({mode: query})}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": f"deckwright/{VERSION}", "Accept": "application/json;q=0.9,*/*;q=0.8"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            # A proxy that blocks the host can answer 404 too; only Scryfall's own error object means "no card".
            if error.code == 404 and _is_scryfall_error(error):
                return None
            if error.code == 429:
                raise RateLimited(query) from None
            raise Unreachable(query, f"HTTP {error.code}") from None
        except http.client.HTTPException as error:
            raise Unreachable(query, type(error).__name__) from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise Unreachable(query, str(getattr(error, "reason", error))) from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise Unreachable(query, "the answer was not a card") from None
        finally:
            self.last_request = time.monotonic()
        if not isinstance(body, dict) or body.get("object") != "card":
            raise Unreachable(query, "the answer was not a card")
        return strip_shop_keys(body)


def _is_scryfall_error(error: urllib.error.HTTPError) -> bool:
    try:
        return json.loads(error.read().decode("utf-8")).get("object") == "error"
    except (ValueError, UnicodeDecodeError, AttributeError):
        return False


def strip_shop_keys(value):
    if isinstance(value, dict):
        return {k: strip_shop_keys(v) for k, v in value.items() if not STRIPPED_KEYS.search(k)}
    if isinstance(value, list):
        return [strip_shop_keys(v) for v in value]
    return value


def fixed_fields(card: dict) -> dict:
    faces = card.get("card_faces") or []

    def joined(key: str, between: str) -> str:
        if key in card:
            return card[key]
        return between.join(face[key] for face in faces if face.get(key))

    return {
        "name": card["name"],
        "mana_cost": joined("mana_cost", " // "),
        "type_line": card.get("type_line", ""),
        "oracle_text": joined("oracle_text", "\n//\n"),
        "color_identity": list(card.get("color_identity", [])),
        "commander_legality": card.get("legalities", {}).get("commander", "not_legal"),
        "game_changer": bool(card.get("game_changer", False)),
    }


# The deck file -----------------------------------------------------------------------


def load_template(name: str) -> dict:
    path = HERE / "templates" / f"{name}.toml"
    if not path.is_file():
        known = sorted(p.stem for p in (HERE / "templates").glob("*.toml"))
        raise Failure(f"No template {name!r}. Templates: {', '.join(known)}.", 2)
    try:
        template = tomllib.loads(path.read_text(encoding="utf-8"))
        checked = {
            "name": template.get("name", name),
            "deck_size": template["deck_size"],
            "bracket_target": template["bracket_target"],
            "categories": template["categories"],
        }
        for category in checked["categories"]:
            category["name"], category["target"], category["counts_when"]
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, KeyError, TypeError) as error:
        raise Failure(f"The template {name!r} is not readable or lacks a key ({error}).", 2) from None
    return checked


def read_deck(path: Path) -> dict:
    if not path.is_file():
        raise Failure(f"No deck file at {path.name}. Start one with: new --template <name> --commander NAME", 2)
    try:
        deck = json.loads(path.read_text(encoding="utf-8"))
        deck["commander"]["name"], deck["cards"]
        targets = [c["target"] for c in deck["template"]["categories"]] + [deck["template"]["bracket_target"]]
        if not all(type(n) is int for n in targets):
            raise TypeError("a target is not a whole number")
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as error:
        raise Failure(
            f"The deck file {path.name} is not a readable deck ({error}). Start a new one with new.", 2
        ) from None
    return deck


def write_deck(path: Path, deck: dict) -> None:
    path.write_text(json.dumps(deck, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def category_names(deck: dict, asked: list[str]) -> list[str]:
    known = [c["name"] for c in deck["template"]["categories"]]
    unknown = [c for c in asked if c not in known]
    if unknown:
        raise Failure(f"Unknown category {unknown[0]!r}. Categories: {', '.join(known)}.", 2)
    return [c for c in known if c in asked]


def looked_up(scryfall: Scryfall, name: str) -> dict:
    """The fixed fields of the card named exactly so; anything less is not recorded."""
    entry = scryfall.lookup(name)
    if entry["result"] == "not_found":
        raise Failure(f"No card named {name!r}. Nothing was recorded.", EXIT_NOT_RECORDED)
    if entry["result"] == "closest_match":
        raise Failure(
            f"No card named {name!r}; the closest match is {entry['card']['name']!r}. "
            "Nothing was recorded: add it by that name once the player confirms it.",
            EXIT_NOT_RECORDED,
        )
    return entry["card"]


def player_card(name: str, text: str, type_line: str) -> dict:
    return {
        "name": name,
        "mana_cost": "",
        "type_line": type_line,
        "oracle_text": text,
        "color_identity": [],
        "commander_legality": "unknown",
        "game_changer": False,
    }


# The tally ---------------------------------------------------------------------------


def by_name(name: str):
    return (name.casefold(), name)


def counts_in(entry: dict, category: dict) -> bool:
    word = category.get("from_type_line")
    if word:
        front = entry["card"]["type_line"].split(" // ")[0]
        return re.search(rf"\b{re.escape(word)}\b", front, re.I) is not None
    return category["name"] in entry["categories"]


def tally(deck: dict) -> dict:
    commander = deck["commander"]
    entries = deck["cards"]
    categories = []
    for category in deck["template"]["categories"]:
        counted = [e for e in entries if counts_in(e, category)]
        categories.append(
            {
                "name": category["name"],
                "counts_when": category["counts_when"],
                "target": category["target"],
                "count": sum(e["count"] for e in counted),
                "cards": sorted((e["card"]["name"] for e in counted), key=by_name),
            }
        )

    looked = [e for e in entries if not e.get("from_player")]
    identity = set(commander["color_identity"])

    def copies_allowed(card: dict) -> float:
        text = card["oracle_text"].casefold()
        if "basic" in card["type_line"].casefold() or ANY_NUMBER in text:
            return float("inf")
        up_to = UP_TO.search(text)
        if up_to:
            word = up_to.group(1)
            return int(word) if word.isdigit() else NUMBER_WORDS.get(word, 1)
        return 1

    front = commander["type_line"].split(" // ")[0]
    can_lead = ("Legendary" in front and "Creature" in front) or ("can be your commander" in commander["oracle_text"])
    checks = {
        "singleton": [
            e["card"]["name"]
            for e in entries
            if e["count"] > copies_allowed(e["card"]) or e["card"]["name"] == commander["name"]
        ],
        "color_identity": [e["card"]["name"] for e in looked if set(e["card"]["color_identity"]) - identity],
        "commander_legality": [
            card["name"] for card in [commander, *(e["card"] for e in looked)] if card["commander_legality"] != "legal"
        ],
        "commander": [] if can_lead else [commander["name"]],
    }
    game_changers = {card["name"] for card in [commander, *(e["card"] for e in looked)] if card["game_changer"]}
    target = deck["template"]["bracket_target"]
    lowest = lowest_bracket(len(game_changers))
    # Bracket 1 differs from 2 by intent, not by count, so a target of 1 is judged as 2.
    judged = max(target, 2)
    allowed = bracket_rules()[judged].get("max_game_changers")
    return {
        "template": deck["template"]["name"],
        "commander": commander["name"],
        "deck_size": deck["template"]["deck_size"],
        "total": 1 + sum(e["count"] for e in entries),
        "categories": categories,
        "checks": {k: sorted(set(v), key=by_name) for k, v in checks.items()},
        "bracket": {
            "target": target,
            "lowest": lowest,
            "game_changers": sorted(game_changers, key=by_name),
            "over": lowest > judged,
            **({} if allowed is None else {"game_changers_allowed": allowed}),
        },
        "player_text": sorted((e["card"]["name"] for e in entries if e.get("from_player")), key=by_name),
    }


def bracket_rules() -> dict[int, dict]:
    """Each bracket's rule from brackets.toml; a bracket the file does not list follows the next lower one."""
    rules = tomllib.loads((HERE / "brackets.toml").read_text(encoding="utf-8"))
    listed = {b["bracket"]: b for b in rules["brackets"]}
    by_bracket, last = {}, listed[min(listed)]
    for bracket in range(1, 6):
        last = listed.get(bracket, last)
        by_bracket[bracket] = last
    return by_bracket


def lowest_bracket(game_changers: int) -> int:
    rules = bracket_rules()
    return next(b for b in range(2, 6) if game_changers <= rules[b].get("max_game_changers", game_changers))


# The page ----------------------------------------------------------------------------


def text(value) -> str:
    return html.escape(str(value), quote=False)


def decklist(deck: dict) -> str:
    rows = [
        f"{e['count']} {e['card']['name']}" for e in sorted(deck["cards"], key=lambda e: by_name(e["card"]["name"]))
    ]
    return "\n".join(["// COMMANDER", f"1 {deck['commander']['name']}", "", "// MAINBOARD", *rows])


def render_page(deck: dict) -> str:
    counted = tally(deck)
    copies = {e["card"]["name"]: e["count"] for e in deck["cards"]}
    flagged = {name for names in counted["checks"].values() for name in names} | set(
        counted["bracket"]["game_changers"]
    )
    player_text = set(counted["player_text"])

    def card_row(name: str) -> str:
        marks = []
        if name in flagged:
            marks.append('<span class="mark flag">flagged</span>')
        if name in player_text:
            marks.append('<span class="mark own">player text</span>')
        return f'<li><span class="n">{copies[name]}</span> {text(name)} {"".join(marks)}</li>'

    categories = []
    for row in counted["categories"]:
        state = "done" if row["count"] >= row["target"] else "open"
        filled = min(100, 100 * row["count"] // max(1, row["target"]))
        cards = "".join(card_row(name) for name in row["cards"]) or '<li class="empty">No cards yet</li>'
        categories.append(
            f'<section class="category {state}" data-category="{html.escape(row["name"])}">'
            f'<h3>{text(row["name"])} <span class="count">{row["count"]} / {row["target"]}</span></h3>'
            f'<p class="when">Counts when {text(row["counts_when"])}.</p>'
            f'<div class="bar"><span style="width:{filled}%"></span></div>'
            f"<ul>{cards}</ul></section>"
        )

    size, total = counted["deck_size"], counted["total"]
    if total > size:
        standing = f"{total - size} over the deck size"
    elif total < size:
        standing = f"{size - total} to go"
    else:
        standing = "complete"

    labels = {
        "singleton": "More than one copy",
        "color_identity": "Outside the commander's colour identity",
        "commander_legality": "Not legal in this format",
        "commander": "Cannot be a commander",
    }
    checks = [
        f"<li><strong>{labels[key]}:</strong> {text(', '.join(names))}</li>"
        for key, names in counted["checks"].items()
        if names
    ]
    if counted["player_text"]:
        unchecked = text(", ".join(counted["player_text"]))
        checks.append(f"<li><strong>From the player's text, not checked:</strong> {unchecked}</li>")
    bracket = counted["bracket"]
    changers = text(", ".join(bracket["game_changers"])) if bracket["game_changers"] else "none"
    owned = ", ".join(counted["player_text"])

    fills = {
        "title": text(f"{counted['commander']} · {counted['template']}"),
        "commander": text(counted["commander"]),
        "identity": text("".join(deck["commander"]["color_identity"]) or "colourless"),
        "template": text(counted["template"]),
        "total": f"{total} / {size}",
        "standing": text(standing),
        "categories": "".join(categories),
        "checks": "".join(checks) or "<li>Every card passes.</li>",
        "bracket_over": " · over the target" if bracket["over"] else "",
        "bracket_target": str(bracket["target"]),
        "bracket_lowest": str(bracket["lowest"]),
        "bracket_state": "over" if bracket["over"] else "within",
        "game_changers": changers,
        "player_text": text(owned) if owned else "None: every card was looked up.",
        "decklist": text(decklist(deck)),
    }
    page = (HERE / "page.html").read_text(encoding="utf-8")
    return re.sub(r"\{\{(\w+)\}\}", lambda m: fills[m.group(1)], page)


# Commands ----------------------------------------------------------------------------


def cache_folder(deck_path: Path) -> Path:
    return Path(os.environ.get("DECKWRIGHT_CACHE") or deck_path.parent / "deckwright-cache")


def run(args) -> str | None:
    deck_path = Path(args.deck)
    scryfall = Scryfall(cache_folder(deck_path))

    if args.command == "lookup":
        try:
            return as_json([scryfall.lookup(name) for name in args.names])
        except Unreachable as failure:
            raise Failure(f"{failure} Ask the player for the card's type line and text.", failure.code) from None

    if args.command == "new":
        deck = {"template": load_template(args.template), "commander": looked_up(scryfall, args.commander), "cards": []}
        write_deck(deck_path, deck)
        return as_json(tally(deck))

    deck = read_deck(deck_path)
    try:
        return changed(args, deck, deck_path, scryfall)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise Failure(
            f"The deck file {deck_path.name} is not a readable deck ({error!r}). Start a new one with new.", 2
        ) from None


def changed(args, deck: dict, deck_path: Path, scryfall: Scryfall) -> str | None:
    """Runs a command on a read deck, writing the deck only when the command and its tally succeed."""
    if args.command == "add":
        categories = category_names(deck, args.category or [])
        at_least(1, args.count, "--count")
        if args.from_player is not None:
            card = player_card(args.name, args.from_player, args.type_line or "")
        else:
            try:
                card = looked_up(scryfall, args.name)
            except Unreachable as failure:
                raise Failure(
                    f"{failure} Ask the player for the card's type line and text, and add it with "
                    "--from-player TEXT --type-line LINE.",
                    failure.code,
                ) from None
        entry = next((e for name in names_of(card) if (e := recorded(deck, name))), None)
        if entry is None:
            entry = {"card": card, "count": 0, "categories": []}
            deck["cards"].append(entry)
        if args.from_player is not None:
            entry.setdefault("from_player", entry["count"] == 0)
        elif entry.pop("from_player", False):
            entry["card"] = card
        entry["count"] += args.count
        entry["categories"] = category_names(deck, [*entry["categories"], *categories])
        deck["cards"].sort(key=lambda e: by_name(e["card"]["name"]))
    elif args.command == "remove":
        if args.count is not None:
            at_least(1, args.count, "--count")
        entry = recorded(deck, args.name)
        if entry is None:
            raise Failure(f"{args.name!r} is not in the deck.", 2)
        entry["count"] -= entry["count"] if args.count is None else args.count
        if entry["count"] <= 0:
            deck["cards"].remove(entry)
    elif args.command == "target":
        (name,) = category_names(deck, [args.category])
        at_least(0, args.n, "A target")
        next(c for c in deck["template"]["categories"] if c["name"] == name)["target"] = args.n
    elif args.command == "bracket":
        if not 1 <= args.n <= 5:
            raise Failure("A bracket is 1 to 5.", 2)
        deck["template"]["bracket_target"] = args.n
    elif args.command == "tally":
        return as_json(tally(deck))
    elif args.command == "page":
        out = Path(args.out) if args.out else deck_path.parent / "deck.html"
        if not out.parent.is_dir():
            raise Failure(f"There is no folder {out.parent} to write the page to.", 2)
        out.write_text(render_page(deck), encoding="utf-8")
        return f"Wrote {out}\n"

    counted = as_json(tally(deck))
    write_deck(deck_path, deck)
    return counted


def recorded(deck: dict, name: str) -> dict | None:
    """The deck's entry for a card, matched by its full name or a face name as Scryfall matches names."""
    wanted = matching_key(name)
    return next((e for e in deck["cards"] if wanted in map(matching_key, names_of(e["card"]))), None)


def matching_key(name: str) -> str:
    """The comparable name, or the casefolded name where nothing comparable is left (a name in another script)."""
    return comparable(name) or name.casefold()


def at_least(lowest: int, n: int, what: str) -> None:
    if n < lowest:
        raise Failure(f"{what} must be at least {lowest}.", 2)


def as_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="deck.py", description=__doc__.splitlines()[0])
    commands = top.add_subparsers(dest="command", required=True)

    def command(name: str, help: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=help, description=help)
        sub.add_argument("--deck", default="deck.json", help="the deck file (default ./deck.json)")
        return sub

    lookup = command("lookup", "Look cards up on Scryfall; prints each card's fixed fields as JSON.")
    lookup.add_argument("names", nargs="+", metavar="NAME")

    new = command("new", "Start a deck file from a template, with its commander.")
    new.add_argument("--template", required=True)
    new.add_argument("--commander", required=True)

    add = command("add", "Record a card the player said yes to.")
    add.add_argument("name", metavar="NAME")
    add.add_argument("--count", type=int, default=1)
    add.add_argument("--category", nargs="+", action="extend", metavar="C")
    add.add_argument("--from-player", metavar="TEXT", help="the card's text as the player gave it; no lookup")
    add.add_argument(
        "--type-line", metavar="LINE", help="with --from-player: the card's type line as the player gave it"
    )

    remove = command("remove", "Take copies of a card out (all of them unless --count).")
    remove.add_argument("name", metavar="NAME")
    remove.add_argument("--count", type=int)

    target = command("target", "Change one category's target.")
    target.add_argument("category", metavar="CATEGORY")
    target.add_argument("n", type=int, metavar="N")

    bracket = command("bracket", "Change the deck's bracket target.")
    bracket.add_argument("n", type=int, metavar="N")

    command("tally", "Count the deck against the template; prints JSON.")

    page = command("page", "Render the deck page.")
    page.add_argument("--out", metavar="FILE", help="where to write it (default deck.html beside the deck file)")
    return top


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    args = parser().parse_args()
    try:
        output = run(args)
    except Failure as failure:
        print(failure, file=sys.stderr)
        return failure.code
    if output:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
