"""Refusals: exit 2 with a plain message and the deck unchanged; a corrupt cache file refetched."""

from __future__ import annotations

import json
import shutil

from conftest import SKILL_DIR, Deckwright, category, scryfall_card


def refused(deck: Deckwright, *args: str, **kw):
    """Runs a command that must exit 2 with a message, no traceback, and the deck file as it was."""
    before = deck.deck_file.read_bytes() if deck.deck_file.exists() else None
    proc = deck.run(*args, expect=2, **kw)
    assert (proc.stdout + proc.stderr).strip(), f"deck.py {' '.join(args)} should say why it refused"
    assert "Traceback" not in proc.stderr, proc.stderr
    after = deck.deck_file.read_bytes() if deck.deck_file.exists() else None
    assert after == before, f"deck.py {' '.join(args)} changed the deck file"
    return proc


def test_exit_usage_no_deck_file(deck):
    for args in (("tally",), ("page", "--out", "deck.html"), ("add", "Sol Ring"), ("remove", "Sol Ring")):
        refused(deck, *args)
    assert not deck.deck_file.exists()


def test_exit_usage_unknown_template(deck):
    refused(deck, "new", "--template", "no-such-format", "--commander", "Meren of Clan Nel Toth")
    assert not deck.deck_file.exists()


def test_exit_usage_unknown_category(deck):
    deck.new()
    refused(deck, "add", "Sol Ring", "--category", "Rampp")
    refused(deck, "target", "Rampp", "8")


def test_exit_usage_not_in_deck(deck):
    deck.new()
    deck.add("Sol Ring", "Ramp")
    refused(deck, "remove", "Mana Vault")


def test_exit_usage_out_of_range(deck):
    deck.new()
    deck.add("Sol Ring", "Ramp")
    for n in ("0", "6", "-1"):
        refused(deck, "bracket", n)
    refused(deck, "target", "Ramp", "-1")
    for n in ("0", "-1"):
        refused(deck, "remove", "Sol Ring", "--count", n)

    # The edges are accepted.
    for n in ("1", "5"):
        deck.run("bracket", n)
        assert deck.tally()["bracket"]["target"] == int(n)
    deck.run("target", "Ramp", "0")
    assert category(deck.tally(), "Ramp")["target"] == 0


def test_exit_usage_unreadable_deck_file(deck):
    deck.new()
    deck.deck_file.write_text('{"commander": ', encoding="utf-8")
    for args in (("tally",), ("page", "--out", "deck.html"), ("add", "Sol Ring"), ("bracket", "3")):
        refused(deck, *args)
    deck.deck_file.write_bytes(b"\xff\xfe\x00not a deck")
    refused(deck, "tally")


def test_exit_usage_template_missing_key(tmp_path, scryfall):
    skill = tmp_path / "skill"
    shutil.copytree(SKILL_DIR, skill)
    (skill / "templates" / "broken.toml").write_text(
        'bracket_target = 2\n\n[[categories]]\nname = "Lands"\ntarget = 38\n'
        'counts_when = "the card\'s type line includes Land"\n',
        encoding="utf-8",
    )
    work = tmp_path / "work"
    work.mkdir()
    deck = Deckwright(work, scryfall.url, script=skill / "deck.py")
    refused(deck, "new", "--template", "broken", "--commander", "Meren of Clan Nel Toth")
    assert not deck.deck_file.exists()


def test_lookup_fields_corrupt_cache_refetched(deck, scryfall):
    cache = deck.cwd / "deckwright-cache"
    cache.mkdir()
    (cache / "sol-ring.json").write_text("{not json", encoding="utf-8")
    (cache / "vampiric-tutor.json").write_text("[]", encoding="utf-8")
    (cache / "mana-vault.json").write_text(json.dumps({"object": "error", "status": 404}), encoding="utf-8")

    entries = deck.json("lookup", "Sol Ring", "Vampiric Tutor", "Mana Vault")
    assert [e["result"] for e in entries] == ["found", "found", "found"]
    assert [e["card"]["name"] for e in entries] == ["Sol Ring", "Vampiric Tutor", "Mana Vault"]
    fetched = [r.query.get("exact", [None])[0] for r in scryfall.requests]
    assert fetched == ["Sol Ring", "Vampiric Tutor", "Mana Vault"], "a file that is not a card is treated as missing"
    rewritten = json.loads((cache / "sol-ring.json").read_text(encoding="utf-8"))
    assert rewritten["name"] == scryfall_card("Sol Ring")["name"]


def _break(deck: Deckwright, how: str):
    """Damages deck.json inside while keeping it valid JSON, wherever the layout keeps the part."""
    data = json.loads(deck.deck_file.read_text(encoding="utf-8"))
    done = []

    def walk(node):
        if isinstance(node, dict):
            if how == "commander" and node.get("name") == "Meren of Clan Nel Toth" and "color_identity" in node:
                del node["color_identity"]
                done.append(how)
            if how == "card" and "card" in node and not done:
                del node["card"]
                done.append(how)
            if how == "target" and node.get("name") == "Lands" and node.get("target") == 38:
                node["target"] = "38"
                done.append(how)
            for value in list(node.values()):
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    assert done, f"no part of deck.json to damage for {how!r}"
    deck.deck_file.write_text(json.dumps(data), encoding="utf-8")


def test_exit_usage_deck_file_wrong_inside(deck):
    for how in ("commander", "card", "target"):
        deck.deck_file.unlink(missing_ok=True)
        deck.new()
        deck.add("Sol Ring", "Ramp")
        _break(deck, how)
        for args in (("tally",), ("page", "--out", "deck.html")):
            proc = refused(deck, *args)
            assert proc.returncode == 2, how


def test_exit_usage_page_folder_missing(deck):
    deck.new()
    refused(deck, "page", "--out", "no-such-folder/deck.html")
    assert not (deck.cwd / "no-such-folder").exists()
