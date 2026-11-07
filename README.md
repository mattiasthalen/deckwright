# deckwright

A deckbuilding tutor for Claude. AI-assisted, not AI-generated: deckwright interviews you through a format's template, one category at a time, suggests and critiques cards it has looked up on Scryfall, and records only the cards you say yes to. It ends with a deck page that carries the decklist in ManaBox's import format.

The first template is Commander, after The Command Zone's deckbuilding template (episode 658): 38 lands, 10 ramp, 12 card advantage, 12 targeted disruption, 6 mass disruption, 30 for the deck's plan.

## Code execution is required

Every lookup, count, check and the deck page come from a small Python script that ships with the skill (`plugins/deckwright/skills/interview/deck.py`, standard library only, run with `uv` or Python 3.11+). Without code execution deckwright says so and does not start.

- **Claude app** (web, desktop, mobile): Settings → Capabilities → turn on **Code execution and file creation**. The script needs to reach `api.scryfall.com`; if your network settings for code execution limit domains, allow it.
- **Claude Code**: allow the Bash tool when asked.

## Install

### In the Claude app

Install it once in Settings, and it is there on every surface you sign in to: web, desktop and mobile.

1. Download this repository's `plugins/deckwright/skills/interview` folder as a zip (for example: Code → Download ZIP, then zip the `interview` folder on its own).
2. Open Settings → Capabilities → Skills, choose **Upload skill**, and pick the zip.
3. Make sure the skill is turned on, and that code execution is on (above).

Then start a chat with "help me build a commander deck".

### In Claude Code

Add the marketplace, then install the plugin from it:

```text
/plugin marketplace add mattiasthalen/deckwright
/plugin install deckwright@deckwright
```

On Claude Code 2.1.275 or later this works in one step:

```text
/plugin install deckwright --marketplace mattiasthalen/deckwright
```

The skill is `deckwright:interview`. Ask "help me build a commander deck" or invoke it by name.

## Working on deckwright

```sh
uv run pytest                      # the script's unit tests, against recorded Scryfall answers
uv run ruff check . && uv run ruff format --check .
claude plugin validate . && claude plugin validate plugins/deckwright
```

The skill's behaviour is checked by evals with `claude plugin eval`; see [`evals/README.md`](evals/README.md). Design records are in [`docs/`](docs/).
