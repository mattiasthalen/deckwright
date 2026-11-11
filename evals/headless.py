"""How a headless Claude is started for the evals: the runner's turns, the reader and the judge."""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile


def isolated_env(memory: pathlib.Path) -> dict:
    """The parent's environment minus the project's shared memory.

    A run inherits the cloud session's memory store, and the bare runs of
    2026-11-10 wrote stand-in decks into it as the owner's and read them back in
    later runs. Each run gets an empty memory folder of its own instead.
    """
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_MEMORY_STORES"}
    env["CLAUDE_COWORK_MEMORY_PATH_OVERRIDE"] = str(memory)
    return env


def claude(args: list[str], prompt: str, memory: pathlib.Path | None = None, **how) -> subprocess.CompletedProcess:
    """One `claude -p` call cut off from shared memory.

    A `memory` folder lasts across calls, as a conversation's turns need; without one
    the call gets an empty folder that is removed after it. The prompt goes on stdin:
    as an argument, a message opening with "-" is read as an option and the call fails.
    """
    if memory is None:
        with tempfile.TemporaryDirectory() as fresh:
            return claude(args, prompt, pathlib.Path(fresh), **how)
    memory.mkdir(parents=True, exist_ok=True)
    return subprocess.run(["claude", "-p", *args], input=prompt, env=isolated_env(memory),
                          capture_output=True, text=True, **how)
