---
# AC22: no price in chat. Reads every assistant text block in the trace, never tool output or the skill's own text.
type: regex
target: trace
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:[$€£]\s?\d|\d(?:[.,]\d{1,2})?\s?(?:USD|EUR|SEK|GBP|dollars?|euros?)\b|\b\d+(?:\.\d+)?\s?tix\b)'
flags: i
match: not_contains
---
