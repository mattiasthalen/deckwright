---
# E2: an assistant message says the card could not be looked up (Scryfall out of reach), names Sol Ring within 300 characters of that, and asks for its text within 500.
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:(?:(?:couldn''t|couldn’t|could not|can''t|can’t|cannot|unable to|wasn''t able to|failed to)\s+(?:\w+\s+){0,2}?(?:reach|look|fetch|connect|get to|access)|(?:\b|(?<=\\n))unreachable(?:\b|(?<=\\n))|(?:\b|(?<=\\n))out of reach(?:\b|(?<=\\n))|(?:\b|(?<=\\n))offline(?:\b|(?<=\\n))|(?:\b|(?<=\\n))unavailable(?:\b|(?<=\\n))|(?:\b|(?<=\\n))down(?:\b|(?<=\\n))|(?:\b|(?<=\\n))blocked(?:\b|(?<=\\n))|(?:\b|(?<=\\n))denied(?:\b|(?<=\\n)))(?=(?:[^"\\]|\\.){0,300}?(?:Sol Ring))|Sol Ring(?=(?:[^"\\]|\\.){0,300}?(?:(?:couldn''t|couldn’t|could not|can''t|can’t|cannot|unable to|wasn''t able to|failed to)\s+(?:\w+\s+){0,2}?(?:reach|look|fetch|connect|get to|access)|(?:\b|(?<=\\n))unreachable(?:\b|(?<=\\n))|(?:\b|(?<=\\n))out of reach(?:\b|(?<=\\n))|(?:\b|(?<=\\n))offline(?:\b|(?<=\\n))|(?:\b|(?<=\\n))unavailable(?:\b|(?<=\\n))|(?:\b|(?<=\\n))down(?:\b|(?<=\\n))|(?:\b|(?<=\\n))blocked(?:\b|(?<=\\n))|(?:\b|(?<=\\n))denied(?:\b|(?<=\\n)))))(?=(?:[^"\\]|\\.){0,500}?(?:(?:\b|(?<=\\n))(?:text|oracle|wording|what (?:it|the card) (?:does|says))(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*\?))'
---
