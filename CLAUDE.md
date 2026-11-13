# deckwright

A Claude plugin that tutors a player through building a Magic deck for Arena.

- `docs/lexicon.md`: the domain's words. Use only these, in code, tests and docs.
- `docs/adr/`: the decisions. Read them before changing behaviour.
- `docs/assumptions.md`: what the design stands on, and how we would know each stopped holding.

## Commands

```sh
python3 evals/test_checks.py
python3 tests/test_pack.py
python3 tests/test_repo.py
node --test tests/*.test.cjs   # after npm ci and npx playwright install chromium
npm run lint
```

## Tests check facts

A test checks a fact: a key, a path, a count, a command, a job. No test searches prose for a word,
so rewording a document never breaks a test, and a test never pins the wording of a document.
