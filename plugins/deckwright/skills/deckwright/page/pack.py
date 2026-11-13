"""Pack a deck folder into one page that opens anywhere (ADR-0011).

    python3 pack.py <deck folder>

Writes the deck page beside this script into the folder as index.html, titled by
the deck, and the same page holding every file of the folder it reads as
<folder name>.html beside the folder; prints the packed file's path.
"""

from __future__ import annotations

import base64
import html
import json
import pathlib
import re
import sys

PAGE = pathlib.Path(__file__).resolve().with_name("index.html")
# A Scryfall id names a file of the folder, so it may not climb out of it.
PICTURE_ID = re.compile(r"[0-9A-Za-z-]+")


class Unpackable(Exception):
    pass


def read_deck(folder: pathlib.Path) -> tuple[str, dict]:
    try:
        text = (folder / "deck.json").read_text(encoding="utf-8-sig")
        deck = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise Unpackable(f"{folder / 'deck.json'} could not be read: {e}") from None
    if not isinstance(deck, dict):
        raise Unpackable(f"{folder / 'deck.json'} holds no deck")
    return text, deck


def objects(value) -> list[dict]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def text_of(value) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def title(deck: dict) -> str:
    """The deck page's title for the deck, as its hero draws it."""
    if name := text_of(deck.get("name")):
        return name
    # The page reads the format as written and lower-cased, so " brawl" is Standard to it too.
    fmt = deck.get("format")
    fmt = "Brawl" if isinstance(fmt, str) and fmt.lower() == "brawl" else "Standard"
    themes = [text_of(c.get("text")) for c in objects(deck.get("criteria")) if c.get("kind") == "theme"]
    return " · ".join([fmt, *[t for t in themes if t][:1]])


def named_pictures(deck: dict) -> list[str]:
    """Every picture the deck page can ask for: the cards in the deck, on the
    maybeboard and on offer, the tokens, the card back and the hero's art."""
    offer = deck.get("offer")
    groups = objects(offer.get("groups")) if isinstance(offer, dict) else []
    offered = [c for g in groups for c in objects(g.get("cards"))]
    cards = [*objects(deck.get("cards")), *objects(deck.get("maybeboard")), *objects(deck.get("tokens")), *offered]
    ids = [c.get("scryfall_id") for c in cards]
    paths = [f"cards/{i}.jpg" for i in ids if isinstance(i, str) and PICTURE_ID.fullmatch(i)] + ["cards/back.jpg"]
    hero = deck.get("hero")
    if isinstance(hero, str) and PICTURE_ID.fullmatch(hero):
        paths.append(f"art/{hero}.jpg")
    return list(dict.fromkeys(paths))


def packed_files(folder: pathlib.Path, deck_text: str, deck: dict) -> dict[str, str]:
    ledger = folder / "LEDGER.md"
    files = {"deck.json": deck_text, "LEDGER.md": ledger.read_text(encoding="utf-8", errors="replace") if ledger.is_file() else ""}
    for rel in named_pictures(deck):
        if (folder / rel).is_file():
            files[rel] = "data:image/jpeg;base64," + base64.b64encode((folder / rel).read_bytes()).decode("ascii")
    return files


def pack(folder: pathlib.Path) -> pathlib.Path:
    folder = folder.resolve()
    deck_text, deck = read_deck(folder)
    page = re.sub(r"<title>.*?</title>", lambda _: f"<title>{html.escape(title(deck), quote=False)}</title>",
                  PAGE.read_text(encoding="utf-8"), count=1, flags=re.DOTALL)
    # With every "<" written as \u003c, no text of the deck can end the script or open a comment in it.
    files = json.dumps(packed_files(folder, deck_text, deck), ensure_ascii=False).replace("<", "\\u003c")
    at = page.index("<script")
    # Both pages are encoded in full before either is written, so a deck that cannot
    # be written leaves no page cut short; a lone surrogate is written as "?".
    written = page.encode("utf-8", errors="replace")
    packed_page = f"{page[:at]}<script>window.DECK_FILES = {files};</script>\n{page[at:]}".encode("utf-8", errors="replace")
    packed = folder.parent / f"{folder.name}.html"
    (folder / "index.html").write_bytes(written)
    packed.write_bytes(packed_page)
    return packed


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python3 pack.py <deck folder>", file=sys.stderr)
        return 2
    try:
        print(pack(pathlib.Path(argv[1])))
    except (Unpackable, OSError, UnicodeError) as e:
        print(f"pack.py: {str(e).replace(chr(10), ' ')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
