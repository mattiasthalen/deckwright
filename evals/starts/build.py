"""Write the half-built decks some briefs start from, from live Scryfall searches.

    python3 evals/starts/build.py [deck ...]

A started run skips the opening interview and the first card rounds, which cost
most of a run and are already exercised by the briefs that start from nothing.
Each deck is what the skill would have saved by then: criteria, the template's
categories, the cards the player chose and a ledger line for each decision.
Regenerate rather than edit; the cards are the top EDHREC picks per query.
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from checks import scryfall_get  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
TAKEN = "2026-11-09"

BRAWL = ["Ramp", "Card draw", "Removal", "Personal favourites"]
DECKS = {
    # Criteria and commander only: the template comes next.
    "brawl-rats-criteria": {
        "format": "brawl", "colours": "ub", "theme": "Rats",
        "commander": '!"Vren, the Relentless"', "categories": [], "filled": {}, "per": 8},
    "brawl-dinosaurs": {
        "format": "brawl", "colours": "rg", "theme": "Dinosaurs",
        "commander": '!"Etali, Primal Conqueror // Etali, Primal Sickness"',
        "categories": BRAWL + ["Enrage payoffs", "Big threats", "Protection", "Board wipes"],
        "filled": {"Ramp": "otag:ramp -t:land", "Card draw": "otag:card-advantage -t:land",
                   "Removal": "otag:removal -t:land"},
        "per": 8},
    "brawl-tokens": {
        "format": "brawl", "colours": "gw", "theme": "Creature tokens",
        "commander": '!"Ghalta and Mavren"',
        "categories": BRAWL + ["Token makers", "Anthems", "Token payoffs", "Board wipes"],
        "filled": {"Token makers": 'o:"create" o:"creature token" -t:land', "Ramp": "otag:ramp -t:land"},
        "per": 8},
    "brawl-spells": {
        "format": "brawl", "colours": "ur", "theme": "Instants and sorceries",
        "commander": '!"Niv-Mizzet, Parun"',
        "categories": BRAWL + ["Spell payoffs", "Counterspells", "Burn", "Copy effects"],
        "filled": {"Ramp": "otag:ramp -t:land", "Card draw": "otag:card-advantage -t:land",
                   "Removal": "otag:removal -t:land", "Personal favourites": "(t:instant or t:sorcery) -t:land",
                   "Spell payoffs": 'o:"instant or sorcery spell" t:creature', "Counterspells": "otag:counterspell",
                   "Burn": "otag:burn -t:land", "Copy effects": 'o:"copy target instant or sorcery"'},
        "per": 8},
    "standard-recursion": {
        "format": "standard", "colours": "bg", "theme": "Creatures dying and coming back",
        "categories": ["Early creatures", "Sacrifice outlets", "Death payoffs", "Recursion", "Removal",
                       "Card draw", "Value creatures", "Finishers", "Interaction"],
        "filled": {"Early creatures": "t:creature mv<=2", "Sacrifice outlets": 'o:"sacrifice a creature" -t:land',
                   "Death payoffs": 'o:"dies" t:creature mv>=3', "Recursion": 'o:"from your graveyard" o:"battlefield" -t:land',
                   "Finishers": "t:creature mv>=5"},
        "per": 4},
}


def search(query: str) -> list[dict]:
    found = scryfall_get("/cards/search?order=edhrec&q=" + urllib.parse.quote(query), 0.6)
    return (found or {}).get("data", [])


def copy_of(card: dict) -> dict:
    faces = card.get("card_faces") or [card]
    return {"mana_cost": card.get("mana_cost") or faces[0].get("mana_cost", ""),
            "type_line": card["type_line"],
            "text": "\n//\n".join(f.get("oracle_text", "") for f in faces),
            "rarity": card["rarity"],
            "taken": TAKEN}


def build(name: str, spec: dict) -> None:
    fmt, colours = spec["format"], spec["colours"]
    pool = f"legal:{fmt} game:arena id<={colours}"
    criteria = [{"kind": "format", "text": f"{fmt.title()} on Arena"}, {"kind": "theme", "text": spec["theme"]},
                {"kind": "colours", "text": {"rg": "Red-green", "gw": "Green-white", "ur": "Blue-red",
                                             "bg": "Black-green", "ub": "Blue-black"}[colours]},
                {"kind": "limit", "text": "None"}]
    ledger = [f"- {TAKEN} · criteria · {c['text']} · the player's answer" for c in criteria]
    cards, used = [], set()

    def take(card: dict, category: str) -> None:
        used.add(card["name"])
        cards.append({"scryfall_id": card["id"], "name": card["name"], "count": 1, "category": category,
                      "tags": [category.lower()], "checked": True, "bends": None, "copy": copy_of(card)})
        ledger.append(f"- {TAKEN} · in · {card['name']} ({card['id']}) · the player chose it for {category}")

    categories = []
    if fmt == "brawl":
        commander = search(f"{pool} id={colours} {spec['commander']}")[0]
        take(commander, "Commander")
        categories.append({"name": "Commander", "target": 1})
        pool = f"{pool} -t:land"
    for category in spec["categories"]:
        categories.append({"name": category, "target": spec["per"]})
        ledger.append(f"- {TAKEN} · category · {category} ({spec['per']}) · template accepted by the player")
    if spec["categories"]:
        categories.append({"name": "Lands", "target": 35 if fmt == "brawl" else 24})
    for category, query in spec["filled"].items():
        picks = [c for c in search(f"{pool} {query}") if c["name"] not in used and "Land" not in c["type_line"]]
        # A Standard category of four places holds two cards at two copies each.
        copies = 2 if fmt == "standard" else 1
        for card in picks[: spec["per"] // copies]:
            take(card, category)
            cards[-1]["count"] = copies
    deck = {"version": 2, "name": f"{spec['theme']} ({fmt.title()})", "format": fmt, "criteria": criteria,
            "categories": categories, "cards": cards, "maybeboard": [], "dismissed_findings": [],
            "last_review": None, "tokens": [], "handbook": [], "scenes": [], "approved": False}
    out = HERE / name
    out.mkdir(exist_ok=True)
    (out / "deck.json").write_text(json.dumps(deck, indent=2, ensure_ascii=False) + "\n")
    (out / "LEDGER.md").write_text("# Ledger\n\n" + "\n".join(ledger) + "\n")
    print(name, sum(c["count"] for c in cards), "cards", file=sys.stderr)


if __name__ == "__main__":
    for name, spec in DECKS.items():
        if len(sys.argv) < 2 or name in sys.argv[1:]:
            build(name, spec)
