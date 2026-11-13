"""Tests for the repository's own upkeep: the ruleset file, the lint command, the CI jobs and CLAUDE.md.

    python3 tests/test_repo.py

Each test checks a fact (a key, a path, a command, a job), never a word of prose.
"""

from __future__ import annotations

import fnmatch
import json
import pathlib
import re
import shlex
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
RULESET = REPO / ".github/rulesets/main-needs-tests.json"
RULESET_PATH = ".github/rulesets/main-needs-tests.json"
WORKFLOWS = REPO / ".github/workflows"
PAGE = "plugins/deckwright/skills/deckwright/page/index.html"
LINT = "npm run lint"
TEST_COMMANDS = ["python3 evals/test_checks.py", "python3 tests/test_pack.py", "node --test tests/*.test.cjs"]

# Keys GitHub adds to a ruleset it serves and refuses or ignores on import.
SERVER_ONLY_KEYS = {"id", "node_id", "_links", "created_at", "updated_at", "current_user_can_bypass"}

# The live ruleset's pull_request rule, as exported from GitHub on 2026-11-13; the file must carry it unchanged.
LIVE_PULL_REQUEST_PARAMETERS = {
    "required_approving_review_count": 0, "dismiss_stale_reviews_on_push": False, "required_reviewers": [],
    "require_code_owner_review": False, "require_last_push_approval": False, "required_review_thread_resolution": False,
    "require_extra_approval_for_unattributed_changes": True, "allowed_merge_methods": ["merge", "squash", "rebase"]}

EXACT_VERSION = re.compile(r"\d+\.\d+\.\d+")


def read(rel):
    path = REPO / rel
    if not path.is_file():
        raise AssertionError(f"there is no {rel}")
    return path.read_text(encoding="utf-8")


def ruleset():
    return json.loads(read(RULESET_PATH))


def workflows():
    """Every workflow file as {path: (triggers, jobs)}, read with regexes, since the tests use the stdlib only.
    A job is {"name": its name: line or its key, "uses": [...], "runs": [...]}, in step order."""
    found = {}
    for path in sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")]):
        text = path.read_text(encoding="utf-8")
        found[path.name] = (triggers_of(text), jobs_of(text))
    return found


def triggers_of(text):
    inline = re.search(r"^(?:on|\"on\"|'on'):[ \t]*(\S.*)$", text, re.MULTILINE)
    if inline:
        return set(re.findall(r"[A-Za-z_]+", inline.group(1)))
    block = re.search(r"^(?:on|\"on\"|'on'):[ \t]*\n((?:[ \t]+.*\n|[ \t]*\n)*)", text, re.MULTILINE)
    return set(re.findall(r"^  ([A-Za-z_]+):", block.group(1), re.MULTILINE)) if block else set()


def jobs_of(text):
    block = re.search(r"^jobs:[ \t]*\n((?:[ \t]+.*\n|[ \t]*\n)*)", text + "\n", re.MULTILINE)
    if not block:
        return []
    jobs = []
    for key, body in re.findall(r"^  ([\w-]+):[ \t]*\n((?:    .*\n|[ \t]*\n)*)", block.group(1), re.MULTILINE):
        name = re.search(r"^    name:[ \t]*(.+?)[ \t]*$", body, re.MULTILINE)
        jobs.append({
            "name": unquoted(name.group(1)) if name else key,
            "uses": [unquoted(u) for u in re.findall(r"^\s*(?:- )?uses:[ \t]*(.+?)[ \t]*$", body, re.MULTILINE)],
            "runs": [unquoted(r) for r in re.findall(r"^\s*(?:- )?run:[ \t]*(.+?)[ \t]*$", body, re.MULTILINE)],
        })
    return jobs


def unquoted(value):
    return value[1:-1] if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'" else value


def ci_commands():
    return {run for _, jobs in workflows().values() for job in jobs for run in job["runs"]}


def package():
    return json.loads(read("package.json"))


def lint_commands(scripts):
    """The commands `npm run lint` runs: its script, split on && and ;, with each `npm run <name>` in it followed."""
    commands, pending, seen = [], ["lint"], set()
    while pending:
        name = pending.pop(0)
        if name in seen or name not in scripts:
            continue
        seen.add(name)
        for command in re.split(r"&&|;|\|\|", scripts[name]):
            words = shlex.split(command)
            if words[:2] == ["npm", "run"] and len(words) > 2:
                pending.append(words[2])
            elif words:
                commands.append(words)
    return commands


def ruff_runs(commands, subcommand):
    """The arguments after `uvx ruff@X.Y.Z <subcommand...>` in each command that runs it, with the version."""
    runs = []
    for words in commands:
        if len(words) >= 2 and words[0] == "uvx" and words[1].startswith("ruff@"):
            if words[2:2 + len(subcommand)] == subcommand:
                runs.append((words[1][len("ruff@"):], words[2 + len(subcommand):]))
    return runs


def fenced_commands(markdown, languages="sh|bash|shell"):
    commands = []
    for body in re.findall(rf"^```(?:{languages})[ \t]*\n(.*?)^```", markdown, re.MULTILINE | re.DOTALL):
        for line in body.splitlines():
            line = line.split(" #", 1)[0].strip()
            if line and not line.startswith("#"):
                commands.append(line)
    return commands


def named_paths(markdown):
    """Repo paths a markdown file names: link targets that are not URLs, and the path-like words of backticked
    spans (a word with a / or ending .md, .py, .json or .cjs). Fenced blocks are commands and are left out."""
    prose = re.sub(r"^```.*?^```", "", markdown, flags=re.MULTILINE | re.DOTALL)
    targets = [t.split("#", 1)[0] for t in re.findall(r"\]\(([^)\s]+)\)", prose)]
    words = [w for span in re.findall(r"`([^`\n]+)`", prose) for w in span.split()]
    looks_like_path = lambda w: ("/" in w or re.search(r"\.(md|py|json|cjs)$", w)) and not re.match(r"[a-z]+:", w) \
        and not w.startswith(("@", "-"))
    paths = [t for t in targets if t and not re.match(r"[a-z]+:", t)] + [w.rstrip(".,;:") for w in words if looks_like_path(w)]
    return sorted(set(paths))


class RulesetTest(unittest.TestCase):
    def test_u1_the_ruleset_file_is_the_live_ruleset_in_import_shape_with_lint_required(self):
        rules = ruleset()
        self.assertEqual(SERVER_ONLY_KEYS & set(rules), set(), "the ruleset file carries keys only GitHub's server sets")
        self.assertEqual(rules.get("name"), "main needs tests")
        self.assertEqual(rules.get("target"), "branch")
        self.assertEqual(rules.get("enforcement"), "active")
        self.assertEqual(rules.get("conditions", {}).get("ref_name", {}).get("include"), ["~DEFAULT_BRANCH"])
        self.assertEqual(rules.get("conditions", {}).get("ref_name", {}).get("exclude"), [])
        self.assertEqual(rules.get("bypass_actors"), [], "the ruleset file lets someone bypass it")
        by_type = {rule["type"]: rule for rule in rules.get("rules", [])}
        self.assertEqual(len(by_type), len(rules.get("rules", [])), "the ruleset file has a rule type twice")
        self.assertEqual(set(by_type), {"required_status_checks", "pull_request", "required_signatures"})
        checks = by_type["required_status_checks"]["parameters"]
        contexts = [c["context"] for c in checks["required_status_checks"]]
        self.assertEqual(sorted(contexts), sorted(["offline tests", "browser tests", "lint"]))
        self.assertIs(checks.get("strict_required_status_checks_policy"), False)
        self.assertIs(checks.get("do_not_enforce_on_create"), False)
        self.assertEqual(by_type["pull_request"].get("parameters"), LIVE_PULL_REQUEST_PARAMETERS)

    def test_u1_every_required_check_is_the_name_of_a_ci_job(self):
        contexts = {c["context"] for rule in ruleset()["rules"] if rule["type"] == "required_status_checks"
                    for c in rule["parameters"]["required_status_checks"]}
        job_names = {job["name"] for _, jobs in workflows().values() for job in jobs}
        self.assertEqual(contexts - job_names, set(), f"required checks no CI job is named for; the jobs are {sorted(job_names)}")

    def test_u1_u3_the_readme_names_the_ruleset_file_and_the_lint_command(self):
        readme = read("README.md")
        self.assertIn(RULESET_PATH, named_paths(readme), "README.md does not name the ruleset file's path")
        self.assertTrue((REPO / RULESET_PATH).is_file(), f"README.md names {RULESET_PATH}, which does not exist")
        self.assertIn(LINT, fenced_commands(readme, languages="sh|bash|shell|") + re.findall(r"`([^`\n]+)`", readme), "README.md does not name `npm run lint`")


class LintTest(unittest.TestCase):
    def test_u2_npm_run_lint_runs_ruff_pinned_through_uvx_over_everything_and_eslint(self):
        pkg = package()
        scripts = pkg.get("scripts", {})
        self.assertIn("lint", scripts, "package.json has no lint script")
        self.assertNotRegex(" ".join(scripts.values()), r"\bnpx\s+ruff\b", "a script runs the npm package ruff, a different tool")
        for deps in ("dependencies", "devDependencies"):
            self.assertNotIn("ruff", pkg.get(deps, {}), f"ruff is in {deps}: the npm package ruff is a different tool")
        commands = lint_commands(scripts)
        for subcommand in (["check"], ["format", "--check"]):
            with self.subTest(ruff=" ".join(subcommand)):
                runs = ruff_runs(commands, subcommand)
                self.assertTrue(runs, f"npm run lint never runs `uvx ruff@X.Y.Z {' '.join(subcommand)}`")
                for version, rest in runs:
                    self.assertRegex(version, rf"^{EXACT_VERSION.pattern}$", f"ruff is pinned as {version!r}, not an exact version")
                    paths = [w for w in rest if not w.startswith("-")]
                    self.assertIn(paths, ([], ["."]), f"ruff {' '.join(subcommand)} runs over {paths}, not every Python file")
        self.assertTrue(any("eslint" in w for words in commands for w in words[:2]), "npm run lint never runs eslint")

    def test_u2_eslint_and_its_config_packages_are_pinned_exactly_and_locked(self):
        pkg = package()
        dev = pkg.get("devDependencies", {})
        missing = {"eslint", "@eslint/js", "eslint-plugin-html", "globals"} - set(dev)
        self.assertEqual(missing, set(), "packages not in devDependencies")
        for name in ("eslint", "@eslint/js", "eslint-plugin-html", "globals"):
            self.assertRegex(dev[name], rf"^{EXACT_VERSION.pattern}$", f"{name} is {dev[name]!r}, not an exact version")
        self.assertEqual(dev["eslint"].split(".")[0], "10", f"eslint is {dev['eslint']}, not ESLint 10")
        locked = json.loads(read("package-lock.json"))["packages"][""]
        self.assertEqual(locked.get("devDependencies"), dev, "package-lock.json does not lock package.json's devDependencies, so npm ci fails")

    def test_u2_the_eslint_flat_config_uses_the_three_packages_over_tests_and_the_deck_page(self):
        configs = [p for p in (REPO / f"eslint.config.{ext}" for ext in ("mjs", "js", "cjs")) if p.is_file()]
        self.assertEqual(len(configs), 1, f"there is not exactly one eslint.config.* at the root: {[p.name for p in configs]}")
        config = configs[0].read_text(encoding="utf-8")
        for name in ("@eslint/js", "eslint-plugin-html", "globals"):
            self.assertRegex(config, rf"""(?:from\s+|require\(\s*)['"]{re.escape(name)}['"]""", f"the config does not load {name}")
        literals = re.findall(r"""['"`]([^'"`\n]+)['"`]""", config)
        self.assertTrue(any(lit.startswith("tests/") for lit in literals), "no file glob in the config covers tests/")
        page_globs = [lit for lit in literals if lit.endswith("page/index.html")]
        self.assertTrue(page_globs, "no file glob in the config names the deck page's page/index.html")
        self.assertTrue(any(fnmatch.fnmatch(PAGE, g) for g in page_globs), f"no glob of {page_globs} matches {PAGE}")


class CiTest(unittest.TestCase):
    def test_u3_a_lint_job_with_node_and_python_runs_npm_run_lint_on_push_and_pull_request(self):
        lint_jobs = [(file, triggers, job) for file, (triggers, jobs) in workflows().items() for job in jobs if job["name"] == "lint"]
        self.assertEqual(len(lint_jobs), 1, f"there is not exactly one CI job named lint: {[(f, j['name']) for f, _, j in lint_jobs]}")
        file, triggers, job = lint_jobs[0]
        self.assertTrue({"push", "pull_request"} <= triggers, f"{file} runs on {sorted(triggers)}, not on push and pull_request")
        actions = [u.split("@", 1)[0] for u in job["uses"]]
        self.assertIn("actions/setup-node", actions, "the lint job does not set up Node")
        self.assertTrue({"actions/setup-python", "astral-sh/setup-uv"} & set(actions), "the lint job sets up neither Python nor uv")
        self.assertIn(LINT, job["runs"], "the lint job does not run npm run lint")


class ClaudeMdTest(unittest.TestCase):
    def test_u4_every_path_claude_md_names_exists(self):
        named = named_paths(read("CLAUDE.md"))
        for must in ("docs/lexicon.md", "docs/adr/", "docs/assumptions.md"):
            self.assertTrue(any(p.rstrip("/") == must.rstrip("/") for p in named), f"CLAUDE.md does not name {must}")
        for path in named:
            with self.subTest(path=path):
                if "*" in path:
                    self.assertTrue(list(REPO.glob(path)), f"CLAUDE.md names {path}, which matches no file")
                else:
                    self.assertTrue((REPO / path).exists(), f"CLAUDE.md names {path}, which does not exist")

    def test_u4_claude_md_runs_the_ci_test_commands_and_lint_and_no_command_ci_does_not(self):
        commands = fenced_commands(read("CLAUDE.md"))
        for must in [*TEST_COMMANDS, LINT]:
            self.assertIn(must, commands, f"CLAUDE.md has no sh block running {must}")
        allowed = ci_commands() | {LINT}
        self.assertEqual(set(commands) - allowed, set(), "CLAUDE.md names commands the CI workflow does not run")


if __name__ == "__main__":
    unittest.main()
