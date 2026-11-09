---
# AC26: the player answers "Both.", so cards they own go in by swap (owned-swapped-unowned-maybeboarded) and cards they do not own onto the maybeboard: a maybeboard add runs.
type: tool_used
tool: Bash
input_match: '"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+maybeboard(?:\s+--deck\s+\S+)?\s+add(?:\b|(?<=\\n))'
min: 1
---
