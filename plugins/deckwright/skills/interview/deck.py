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
import html
import json
import os
import re
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

VERSION = "0.1.0"
HERE = Path(__file__).resolve().parent
SCRYFALL = "https://api.scryfall.com"
# Scryfall asks for at most 10 requests a second.
REQUEST_GAP = 0.1
STRIPPED_KEYS = re.compile(r"price|purchase|image|tcgplayer|cardmarket", re.I)
ANY_NUMBER = "a deck can have any number of cards named"

EXIT_UNREACHABLE = 3
EXIT_NOT_RECORDED = 4


class Failure(Exception):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


class Unreachable(Failure):
    def __init__(self, name: str, reason: str):
        super().__init__(
            f"Scryfall could not be reached to look up {name!r} ({reason}). "
            "Nothing was recorded. Ask the player for the card's text and add it with --from-player.",
            EXIT_UNREACHABLE,
        )


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
            card = self._fetch(query, "exact") or self._fetch(query, "fuzzy")
            if card is None:
                return {"query": query, "result": "not_found"}
            self.cache.mkdir(parents=True, exist_ok=True)
            self._cache_file(query).write_text(json.dumps(card, ensure_ascii=False, indent=1), encoding="utf-8")
        names = [card["name"], *(face.get("name", "") for face in card.get("card_faces", []))]
        found = query.casefold() in (n.casefold() for n in names)
        return {"query": query, "result": "found" if found else "closest_match", "card": fixed_fields(card)}

    def _cache_file(self, query: str) -> Path:
        return self.cache / f"{re.sub(r'[^a-z0-9]+', '-', query.lower()).strip('-')}.json"

    def _cached(self, query: str) -> dict | None:
        path = self._cache_file(query)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

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
            raise Unreachable(query, f"HTTP {error.code}") from None
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
        return between.join(face.get(key, "") for face in faces)

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
    template = tomllib.loads(path.read_text(encoding="utf-8"))
    return {
        "name": template.get("name", name),
        "deck_size": template["deck_size"],
        "bracket_target": template["bracket_target"],
        "categories": [
            {k: c[k] for k in ("name", "target", "counts_when", "from_type_line") if k in c}
            for c in template["categories"]
        ],
    }


def read_deck(path: Path) -> dict:
    if not path.is_file():
        raise Failure(f"No deck file at {path.name}. Start one with: new --template commander --commander NAME", 2)
    return json.loads(path.read_text(encoding="utf-8"))


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


def player_card(name: str, text: str) -> dict:
    return {
        "name": name,
        "mana_cost": "",
        "type_line": "",
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
        return re.search(rf"\b{re.escape(word)}\b", entry["card"]["type_line"]) is not None
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
                "target": deck["targets"][category["name"]],
                "count": sum(e["count"] for e in counted),
                "cards": sorted({e["card"]["name"] for e in counted}, key=by_name),
            }
        )

    looked = [e for e in entries if not e.get("from_player")]
    identity = set(commander["color_identity"])

    def allows_copies(card: dict) -> bool:
        return "Basic" in card["type_line"] or ANY_NUMBER in card["oracle_text"].casefold()

    checks = {
        "singleton": [
            e["card"]["name"]
            for e in entries
            if (e["count"] > 1 and not allows_copies(e["card"])) or e["card"]["name"] == commander["name"]
        ],
        "color_identity": [e["card"]["name"] for e in looked if set(e["card"]["color_identity"]) - identity],
        "commander_legality": [
            card["name"] for card in [commander, *(e["card"] for e in looked)] if card["commander_legality"] != "legal"
        ],
    }
    game_changers = [card["name"] for card in [commander, *(e["card"] for e in looked)] if card["game_changer"]]
    return {
        "template": deck["template"]["name"],
        "commander": commander["name"],
        "deck_size": deck["template"]["deck_size"],
        "total": 1 + sum(e["count"] for e in entries),
        "categories": categories,
        "checks": {k: sorted(set(v), key=by_name) for k, v in checks.items()},
        "bracket": {
            "target": deck["bracket_target"],
            "lowest": lowest_bracket(len(game_changers)),
            "game_changers": sorted(set(game_changers), key=by_name),
        },
        "player_text": sorted({e["card"]["name"] for e in entries if e.get("from_player")}, key=by_name),
    }


def lowest_bracket(game_changers: int) -> int:
    rules = tomllib.loads((HERE / "brackets.toml").read_text(encoding="utf-8"))
    for bracket in sorted(rules["brackets"], key=lambda b: b["bracket"]):
        limit = bracket.get("max_game_changers")
        if limit is None or game_changers <= limit:
            return bracket["bracket"]
    return max(b["bracket"] for b in rules["brackets"])


# The page ----------------------------------------------------------------------------


def text(value) -> str:
    return html.escape(str(value), quote=False)


def decklist(deck: dict) -> str:
    copies: dict[str, int] = {}
    for entry in deck["cards"]:
        copies[entry["card"]["name"]] = copies.get(entry["card"]["name"], 0) + entry["count"]
    rows = [f"{copies[name]} {name}" for name in sorted(copies, key=by_name)]
    return "\n".join(["// COMMANDER", f"1 {deck['commander']['name']}", "", "// MAINBOARD", *rows])


def render_page(deck: dict) -> str:
    counted = tally(deck)
    copies = {e["card"]["name"]: 0 for e in deck["cards"]}
    for entry in deck["cards"]:
        copies[entry["card"]["name"]] += entry["count"]
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
    for category, row in zip(deck["template"]["categories"], counted["categories"]):
        state = "done" if row["count"] >= row["target"] else "open"
        filled = min(100, 100 * row["count"] // max(1, row["target"]))
        cards = "".join(card_row(name) for name in row["cards"]) or '<li class="empty">No cards yet</li>'
        categories.append(
            f'<section class="category {state}" data-category="{html.escape(row["name"])}">'
            f'<h3>{text(row["name"])} <span class="count">{row["count"]} / {row["target"]}</span></h3>'
            f'<p class="when">Counts when {text(category["counts_when"])}.</p>'
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
    }
    checks = [
        f"<li><strong>{labels[key]}:</strong> {text(', '.join(names))}</li>"
        for key, names in counted["checks"].items()
        if names
    ]
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
        "bracket_target": str(bracket["target"]),
        "bracket_lowest": str(bracket["lowest"]),
        "bracket_state": "over" if bracket["lowest"] > bracket["target"] else "within",
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
        return as_json([scryfall.lookup(name) for name in args.names])

    if args.command == "new":
        template = load_template(args.template)
        deck = {
            "template": template,
            "targets": {c["name"]: c["target"] for c in template["categories"]},
            "bracket_target": template["bracket_target"],
            "commander": looked_up(scryfall, args.commander),
            "cards": [],
        }
        write_deck(deck_path, deck)
        return as_json(tally(deck))

    deck = read_deck(deck_path)

    if args.command == "add":
        categories = category_names(deck, args.category or [])
        if args.count < 1:
            raise Failure("--count must be at least 1.", 2)
        card = (
            player_card(args.name, args.from_player) if args.from_player is not None else looked_up(scryfall, args.name)
        )
        entry = next((e for e in deck["cards"] if e["card"]["name"].casefold() == card["name"].casefold()), None)
        if entry is None:
            entry = {"card": card, "count": 0, "categories": []}
            if args.from_player is not None:
                entry["from_player"] = True
            deck["cards"].append(entry)
        entry["count"] += args.count
        entry["categories"] = category_names(deck, [*entry["categories"], *categories])
        deck["cards"].sort(key=lambda e: by_name(e["card"]["name"]))
    elif args.command == "remove":
        entry = next((e for e in deck["cards"] if e["card"]["name"].casefold() == args.name.casefold()), None)
        if entry is None:
            raise Failure(f"{args.name!r} is not in the deck.", 2)
        entry["count"] -= entry["count"] if args.count is None else args.count
        if entry["count"] <= 0:
            deck["cards"].remove(entry)
    elif args.command == "target":
        (name,) = category_names(deck, [args.category])
        deck["targets"][name] = args.n
    elif args.command == "bracket":
        deck["bracket_target"] = args.n
    elif args.command == "tally":
        return as_json(tally(deck))
    elif args.command == "page":
        out = Path(args.out) if args.out else deck_path.parent / "deck.html"
        out.write_text(render_page(deck), encoding="utf-8")
        return f"Wrote {out}\n"

    write_deck(deck_path, deck)
    return as_json(tally(deck))


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
    add.add_argument("--category", nargs="+", metavar="C")
    add.add_argument("--from-player", metavar="TEXT", help="the card's text as the player gave it; no lookup")

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
