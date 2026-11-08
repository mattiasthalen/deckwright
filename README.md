# deckwright

A deckbuilding tutor for Claude. AI-assisted, not AI-generated: deckwright interviews you through a format's template, one category at a time, suggests and critiques cards it has looked up on Scryfall, and records only the cards you say yes to. It ends with a deck page that carries the decklist in ManaBox's import format.

The first template is Commander, after The Command Zone's deckbuilding template (episode 658): 38 lands, 10 ramp, 12 card advantage, 12 targeted disruption, 6 mass disruption, 30 for the deck's plan.

## Code execution is required

Every lookup, count, check and the deck page come from a small Python script that ships with the skill (`plugins/deckwright/skills/interview/deck.py`, standard library only, run with `uv` or Python 3.11+). Without code execution deckwright says so and does not start.

- **Claude app** (web, desktop, mobile): Settings → Capabilities → turn on **Code execution and file creation** (called **Create and edit files** in newer versions). The script needs to reach `api.scryfall.com`. On a Team or Enterprise plan, code execution's network access is limited by default and only an organisation owner can allow a domain: ask yours to allow `api.scryfall.com`. Without it, deckwright asks you for each card's text instead of looking it up.
- **Claude Code**: allow the Bash tool when asked.

## Install

### In the Claude app

Add the marketplace and the plugin once, on the web or in the desktop app. They are saved to your account, so the skill is there in chat wherever you sign in. Plugins need a paid plan.

1. Open **Customize** in the left sidebar and go to **Plugins**.
2. Choose **Add → Add marketplace → Add from a repository**, and enter `mattiasthalen/deckwright`.
3. On the **Discover** tab, pick **deckwright** and choose **Add**.
4. Make sure code execution is on (above).

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
