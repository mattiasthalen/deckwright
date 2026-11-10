#!/usr/bin/env python3
"""Writes the S4 eval cases' fixture deck files, with deck.py itself, against the shared bulk file.

    python3 evals/tools/make-review-decks.py              # every case's decks/meren-recursion.json
    python3 evals/tools/make-review-decks.py --collections # only the collection.txt files

FOR THE BUILD TO RUN: it needs deck.py's S4 commands (`measure`, `review`, `maybeboard add`,
`add --serves-theme`) and card facts that carry `cmc` and `produced_mana`, which the script at the
test stage does not have. Run it once they are built, commit what it writes, and run it again
whenever deck.py's deck file changes: `tests/test_evals_tools.py::test_review_fixture_decks_open`
reads every file it writes with `tally` and `measure`, so a fixture the code can no longer read
fails there, not in an eval.

Every deck is Meren of Clan Nel Toth's, named "Meren Recursion" (`decks/meren-recursion.json`), at
the template's bracket 2 with no Game Changer. The 100-card deck plants what the review must find
and the improvements answer: Ramp short (5 of 10), Targeted disruption heavy (16 of 12), Evolving
Wilds (a land that makes no mana), and two cards kept in a category they count in only on a stretch
(Viscera Seer as Card advantage, Spore Frog as Mass disruption). The Game Changer (Demonic Tutor)
and the card outside the colour identity (Lightning Bolt) come in with the scripted player's
proposals, never from the deck.

- review-a-deck: the 100, no collection, theme and plan set, theme fit on every card.
- review-a-deck-picked-up: the same, measured and reviewed: a finished deck.
- review-with-collection: the 100, every card owned (collection.txt), "not owned: no", the read
  judged, and one maybeboard entry (Sheoldred, Whispering One for Grisly Salvage) for the
  scripted swap to orphan.
- fantasy-deck: the 100, every card owned, "not owned: yes", the read judged.
- ninety-nine: 99 cards, no collection, no theme, every category at its target.

The bulk file comes from evals/tools/bulk-cache.sh, as each scaffold's does; nothing else is fetched.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "deckwright" / "skills" / "interview" / "deck.py"
DECK = "decks/meren-recursion.json"
COMMANDER = "Meren of Clan Nel Toth"
THEME = "graveyard recursion"
PLAN = "Fill the graveyard, sacrifice creatures for value, and bring the best of them back with Meren every end step."

R, CA, TD, MD, P = "Ramp", "Card advantage", "Targeted disruption", "Mass disruption", "Plan"

NONBASIC = [
    "Command Tower",
    "Evolving Wilds",
    "Golgari Rot Farm",
    "Jungle Hollow",
    "Llanowar Wastes",
    "Woodland Cemetery",
    "Golgari Guildgate",
    "Temple of Malady",
    "Bojuka Bog",
    "Phyrexian Tower",
    "Overgrown Tomb",
    "Twilight Mire",
]

# The 100: 37 lands (12 nonbasic, 13 Swamp, 12 Forest) and 62 nonland cards, each with its categories.
RECURSION = {
    "lands": {"Swamp": 13, "Forest": 12},
    "cards": [
        # Ramp, planted short: 5 of 10.
        ("Sol Ring", [R]),
        ("Arcane Signet", [R]),
        ("Golgari Signet", [R]),
        ("Cultivate", [R]),
        ("Sakura-Tribe Elder", [R, P]),
        # Card advantage: 11 of 12; Viscera Seer is a stretch (it scries, it draws nothing).
        ("Phyrexian Arena", [CA]),
        ("Midnight Reaper", [CA, P]),
        ("Harvester of Souls", [CA, P]),
        ("Grim Haruspex", [CA, P]),
        ("Night's Whisper", [CA]),
        ("Read the Bones", [CA]),
        ("Sign in Blood", [CA]),
        ("Eternal Witness", [CA, P]),
        ("Viscera Seer", [CA, P]),
        ("Fecundity", [CA]),
        ("Deathreap Ritual", [CA]),
        # Targeted disruption, planted heavy: 16 of 12.
        ("Ravenous Chupacabra", [TD, P]),
        ("Assassin's Trophy", [TD]),
        ("Beast Within", [TD]),
        ("Putrefy", [TD]),
        ("Murder", [TD]),
        ("Go for the Throat", [TD]),
        ("Doom Blade", [TD]),
        ("Infernal Grasp", [TD]),
        ("Hero's Downfall", [TD]),
        ("Krosan Grip", [TD]),
        ("Naturalize", [TD]),
        ("Reclamation Sage", [TD, P]),
        ("Acidic Slime", [TD, P]),
        ("Shriekmaw", [TD, P]),
        ("Fleshbag Marauder", [TD, P]),
        ("Plaguecrafter", [TD, P]),
        # Mass disruption: 5 of 6; Spore Frog is a stretch (a fog, which wipes nothing).
        ("Pernicious Deed", [MD]),
        ("Massacre Wurm", [MD, P]),
        ("Living Death", [MD, P]),
        ("Spore Frog", [MD, P]),
        ("Tormod's Crypt", [MD]),
        # The plan.
        ("Carrion Feeder", [P]),
        ("Bloodghast", [P]),
        ("Gravecrawler", [P]),
        ("Stitcher's Supplier", [P]),
        ("Mesmeric Fiend", [P]),
        ("Woodfall Primus", [P]),
        ("Blood Artist", [P]),
        ("Zulaport Cutthroat", [P]),
        ("Grisly Salvage", [P]),
        ("Mulch", [P]),
        ("Golgari Grave-Troll", [P]),
        ("Stinkweed Imp", [P]),
        ("Life from the Loam", [P]),
        ("Victimize", [P]),
        ("Animate Dead", [P]),
        ("Necromancy", [P]),
        ("Rotlung Reanimator", [P]),
        ("Nantuko Husk", [P]),
        ("Ghoulcaller Gisa", [P]),
        ("Butcher of Malakir", [P]),
        ("Grave Pact", [P]),
        ("Dictate of Erebos", [P]),
        ("Moldgraf Monstrosity", [P]),
        ("Splinterfright", [P]),
        ("Dread Return", [P]),
    ],
    "counts": {"Lands": 37, R: 5, CA: 11, TD: 16, MD: 5, P: 40},
}

# The 99: 38 lands and 60 nonland cards, every category at its target, without the two cards the
# scripted player adds (Eternal Witness, Ravenous Chupacabra).
NINETY_NINE = {
    "lands": {"Swamp": 13, "Forest": 13},
    "cards": [
        ("Sol Ring", [R]),
        ("Arcane Signet", [R]),
        ("Golgari Signet", [R]),
        ("Cultivate", [R]),
        ("Sakura-Tribe Elder", [R, P]),
        ("Kodama's Reach", [R]),
        ("Rampant Growth", [R]),
        ("Wood Elves", [R, P]),
        ("Farhaven Elf", [R]),
        ("Burnished Hart", [R]),
        ("Phyrexian Arena", [CA]),
        ("Midnight Reaper", [CA, P]),
        ("Harvester of Souls", [CA, P]),
        ("Grim Haruspex", [CA, P]),
        ("Night's Whisper", [CA]),
        ("Read the Bones", [CA]),
        ("Sign in Blood", [CA]),
        ("Fecundity", [CA]),
        ("Deathreap Ritual", [CA]),
        ("Graveborn Muse", [CA, P]),
        ("Painful Truths", [CA]),
        ("Village Rites", [CA]),
        ("Assassin's Trophy", [TD]),
        ("Beast Within", [TD]),
        ("Putrefy", [TD]),
        ("Murder", [TD]),
        ("Go for the Throat", [TD]),
        ("Doom Blade", [TD]),
        ("Infernal Grasp", [TD]),
        ("Hero's Downfall", [TD]),
        ("Krosan Grip", [TD]),
        ("Reclamation Sage", [TD, P]),
        ("Acidic Slime", [TD, P]),
        ("Shriekmaw", [TD, P]),
        ("Pernicious Deed", [MD]),
        ("Massacre Wurm", [MD, P]),
        ("Living Death", [MD, P]),
        ("Tormod's Crypt", [MD]),
        ("Crypt Incursion", [MD]),
        ("Bane of Progress", [MD]),
        ("Carrion Feeder", [P]),
        ("Bloodghast", [P]),
        ("Gravecrawler", [P]),
        ("Stitcher's Supplier", [P]),
        ("Mesmeric Fiend", [P]),
        ("Woodfall Primus", [P]),
        ("Blood Artist", [P]),
        ("Zulaport Cutthroat", [P]),
        ("Grisly Salvage", [P]),
        ("Mulch", [P]),
        ("Golgari Grave-Troll", [P]),
        ("Stinkweed Imp", [P]),
        ("Life from the Loam", [P]),
        ("Victimize", [P]),
        ("Animate Dead", [P]),
        ("Necromancy", [P]),
        ("Rotlung Reanimator", [P]),
        ("Nantuko Husk", [P]),
        ("Ghoulcaller Gisa", [P]),
        ("Grave Pact", [P]),
    ],
    "counts": {"Lands": 38, R: 10, CA: 12, TD: 12, MD: 6, P: 31},
}

# Owned beside the deck, for the improvements to find: ramp for the short category, Satyr Wayfinder
# for the swap the scripted player proposes, and the two planted cards.
OWNED_EXTRAS = {
    "Satyr Wayfinder": [P],
    "Wood Elves": [R, P],
    "Farhaven Elf": [R],
    "Rampant Growth": [R],
    "Kodama's Reach": [R],
    "Burnished Hart": [R],
    "Mind Stone": [R],
    "Fellwar Stone": [R],
    "Commander's Sphere": [R],
    "Explosive Vegetation": [R],
    "Demonic Tutor": [P],
}
OFF_COLOUR_OWNED = ["Lightning Bolt"]  # owned, outside Meren's colours: never in the read

PICKED_UP_REVIEW = (
    "Meren Recursion wins the long game. The early turns fill the graveyard with self-mill and cheap "
    "creatures; the middle turns turn every death into value through the sacrifice outlets and the "
    "drain creatures; Meren then returns the best creature every end step until Living Death, Massacre "
    "Wurm or a drain ends it.\n\n"
    "The curve leans on three and four mana with too little ramp to hurry it: Ramp is the short "
    "category, and the deck plays its mid-game a turn late. Without Meren the engine is slower but "
    "Grim Haruspex, Midnight Reaper and the reanimation spells keep it going.\n\n"
    "Targeted disruption is heavy and Card advantage a touch short. Viscera Seer is counted as card "
    "advantage only on a stretch, and Spore Frog as mass disruption the same way. Evolving Wilds makes "
    "no mana itself: it fetches a basic Swamp or Forest."
)

SHEOLDRED = ("Sheoldred, Whispering One", "Grisly Salvage", "A stronger end-step engine than a one-shot dig.")


def collection_lines(deck: dict, extras: dict, off_colour: list[str]) -> str:
    """Every card of the deck owned once (basics with room to spare), and the extras."""
    names = [*NONBASIC, *(name for name, _ in deck["cards"]), *extras, *off_colour]
    lines = [f"1 {name}" for name in names] + ["20 Swamp", "20 Forest", f"1 {COMMANDER}"]
    return "\n".join(lines) + "\n"


class Folder:
    def __init__(self, path: Path, cache: Path):
        self.path = path
        self.env = {**os.environ, "DECKWRIGHT_CACHE": str(cache)}

    def run(self, *args: str, deck: bool = True) -> str:
        args = list(args)
        if deck:
            at = 2 if args[0] == "maybeboard" else 1
            args[at:at] = ["--deck", DECK]
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *args], cwd=self.path, env=self.env, capture_output=True, text=True
        )
        if proc.returncode != 0:
            sys.exit(f"deck.py {' '.join(args)} exited {proc.returncode}:\n{proc.stdout}\n{proc.stderr}")
        return proc.stdout


def build(folder: Folder, deck: dict, *, theme: bool, collection: Path | None, not_owned: str | None) -> dict:
    folder.run("new", "--template", "commander", "--commander", COMMANDER, "--name", "Meren Recursion", deck=False)
    if theme:
        folder.run("theme", THEME)
        folder.run("plan", PLAN)
    if collection is not None:
        shutil.copy(collection, folder.path / "collection.txt")
        folder.run("collection", "collection.txt", deck=False)
        folder.run("not-owned", not_owned)
        judged = [{"name": n, "categories": c, "serves_theme": P in c} for n, c in deck["cards"]]
        judged += [{"name": n, "categories": c, "serves_theme": P in c} for n, c in OWNED_EXTRAS.items()]
        judged += [{"name": n, "categories": [], "serves_theme": False} for n in NONBASIC]
        judged += [{"name": n, "categories": [], "serves_theme": False} for n in ("Swamp", "Forest")]
        read = json.loads(folder.run("judge", json.dumps(judged)))
        if read["unjudged"] != 0:
            sys.exit(f"the read still has {read['unjudged']} unjudged cards")
    for name in NONBASIC:
        folder.run("add", name)
    for name, count in deck["lands"].items():
        folder.run("add", name, "--count", str(count))
    for name, categories in deck["cards"]:
        flags = ["--category", *categories]
        if theme:
            flags += ["--serves-theme", "yes" if P in categories else "no"]
        folder.run("add", name, *flags)
    return json.loads(folder.run("tally"))


def verify(tally: dict, deck: dict, total: int) -> None:
    counts = {c["name"]: c["count"] for c in tally["categories"]}
    problems = []
    if tally["total"] != total:
        problems.append(f"total {tally['total']}, not {total}")
    for name, count in deck["counts"].items():
        if counts[name] != count:
            problems.append(f"{name} {counts[name]}, not {count}")
    if any(tally["checks"].values()):
        problems.append(f"flagged: {tally['checks']}")
    if tally["bracket"]["lowest"] != 2 or tally["bracket"]["game_changers"]:
        problems.append(f"bracket: {tally['bracket']}")
    if problems:
        sys.exit("the deck is not as planted: " + "; ".join(problems))


def main() -> None:
    collection_file = ROOT / "evals" / "review-with-collection" / "fixture" / "collection.txt"
    text = collection_lines(RECURSION, OWNED_EXTRAS, OFF_COLOUR_OWNED)
    for case in ("review-with-collection", "fantasy-deck"):
        target = ROOT / "evals" / case / "fixture" / "collection.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    if sys.argv[1:] == ["--collections"]:
        return

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        cache = work / "deckwright-cache"
        subprocess.run(["bash", str(ROOT / "evals" / "tools" / "bulk-cache.sh"), str(cache)], check=True, cwd=work)
        cases = [
            ("review-a-deck", RECURSION, 100, dict(theme=True, collection=None, not_owned=None)),
            ("review-a-deck-picked-up", RECURSION, 100, dict(theme=True, collection=None, not_owned=None)),
            ("review-with-collection", RECURSION, 100, dict(theme=True, collection=collection_file, not_owned="no")),
            ("fantasy-deck", RECURSION, 100, dict(theme=True, collection=collection_file, not_owned="yes")),
            ("ninety-nine", NINETY_NINE, 99, dict(theme=False, collection=None, not_owned=None)),
        ]
        for case, deck, total, how in cases:
            path = work / case
            path.mkdir()
            folder = Folder(path, cache)
            verify(build(folder, deck, **how), deck, total)
            if case == "review-with-collection":
                name, replaces, why = SHEOLDRED
                folder.run("maybeboard", "add", name, "--replaces", replaces, "--why", why)
            if case == "review-a-deck-picked-up":
                folder.run("measure")
                folder.run("review", PICKED_UP_REVIEW)
            target = ROOT / "evals" / case / "fixture" / DECK
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(path / DECK, target)
            print(f"wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
