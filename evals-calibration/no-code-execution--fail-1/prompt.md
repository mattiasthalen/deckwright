---
description: "Calibration of the no-code-execution llm grader: the pass's reply with its last sentence replaced by one that starts the interview and asks for the commander and the bracket: a known fail."
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

While you do that, let's start: who's your commander, and what bracket are you aiming for?
=====
