---
description: "Calibration of the no-code-execution llm grader: a real reply from the final no-code-execution pass (2026-11-07, run nPsbm6), judged a pass by hand: it says the interview needs code execution, says how to turn it on in Claude Code and in the Claude app, and starts nothing."
max_turns: 2
timeout_seconds: 300
allowed_tools: []
---
Reply with exactly the text between the two lines of five equals signs, and nothing before or after it. Do not add, remove or change a word, and do not use any tool.

=====
I can't start the deck interview: it needs code execution to look cards up and keep the deck file, and I don't have a tool that runs shell commands in this session.

To turn it on:
- **Claude Code:** allow the Bash tool (e.g. approve it when prompted, or add it to your permissions).
- **Claude app:** Settings → Capabilities → "Code execution and file creation" (called "Create and edit files" in newer versions).

Once that's on, ask again and we'll pick it up from the top.
=====
