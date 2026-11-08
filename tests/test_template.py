"""The Commander template: AC2, and the part of AC3 a test can see (targets come from the file)."""

from __future__ import annotations

import re
import shutil
import tomllib

from conftest import CATEGORIES, SKILL_DIR, Deckwright, category

TEMPLATE = SKILL_DIR / "templates" / "commander.toml"


def test_commander_template():
    template = tomllib.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert template["deck_size"] == 100
    assert template["bracket_target"] == 2
    categories = template["categories"]
    assert [(c["name"], c["target"]) for c in categories] == CATEGORIES
    for c in categories:
        assert isinstance(c["counts_when"], str) and c["counts_when"].strip(), c["name"]
    lands = categories[0]
    assert "land" in lands["counts_when"].lower() and "type line" in lands["counts_when"].lower()


def _copy_skill(tmp_path):
    copy = tmp_path / "skill"
    shutil.copytree(SKILL_DIR, copy)
    return copy


def test_commander_template_targets_come_from_the_file(tmp_path, scryfall):
    skill = _copy_skill(tmp_path)
    path = skill / "templates" / "commander.toml"
    blocks = re.split(r"(?m)^(?=\[\[categories\]\])", path.read_text(encoding="utf-8"))
    for i, block in enumerate(blocks):
        if re.search(r'(?m)^name\s*=\s*"Ramp"', block):
            blocks[i] = re.sub(r"(?m)^target\s*=\s*10\b", "target = 7", block)
    path.write_text("".join(blocks), encoding="utf-8")

    work = tmp_path / "work"
    work.mkdir()
    deck = Deckwright(work, scryfall.url, script=skill / "deck.py")
    deck.new()
    assert category(deck.tally(), "Ramp")["target"] == 7


def test_commander_template_new_format_is_one_file(tmp_path, scryfall):
    skill = _copy_skill(tmp_path)
    (skill / "templates" / "tiny.toml").write_text(
        "\n".join(
            [
                'name = "Tiny"',
                "deck_size = 60",
                "bracket_target = 3",
                "",
                "[[categories]]",
                'name = "Threats"',
                "target = 20",
                'counts_when = "it wins the game if left alone"',
                "",
                "[[categories]]",
                'name = "Answers"',
                "target = 10",
                'counts_when = "it deals with a threat"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    work = tmp_path / "work"
    work.mkdir()
    deck = Deckwright(work, scryfall.url, script=skill / "deck.py")
    deck.new(template="tiny")
    deck.add("Ravenous Chupacabra", "Threats", "Answers")
    tally = deck.tally()
    assert [(c["name"], c["target"]) for c in tally["categories"]] == [("Threats", 20), ("Answers", 10)]
    assert tally["deck_size"] == 60
    assert tally["bracket"]["target"] == 3
    assert category(tally, "Threats")["count"] == 1
    assert category(tally, "Answers")["count"] == 1
