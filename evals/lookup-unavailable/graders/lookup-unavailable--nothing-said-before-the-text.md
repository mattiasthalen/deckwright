---
# E2: until an assistant message asks for Sol Ring's text, no assistant message says what it is or does (colourless, taps for, artifact, its cost) within 300 characters of its name.
type: regex
target: trace
flags: i
match: not_contains
pattern: '^(?:(?!"role":"assistant"[^\n]*"type":"text","text":"(?:(?!(?:\b|(?<=\\n))(?:text|oracle|wording|what (?:it|the card) (?:does|says))(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*\?)(?:[^"\\]|\\.))*?(?:\b|(?<=\\n))(?:text|oracle|wording|what (?:it|the card) (?:does|says))(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*\?)[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:(?!(?:\b|(?<=\\n))(?:text|oracle|wording|what (?:it|the card) (?:does|says))(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*\?)(?:[^"\\]|\\.))*?(?:Sol Ring(?:(?!(?:\b|(?<=\\n))(?:text|oracle|wording|what (?:it|the card) (?:does|says))(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*\?)(?:[^"\\]|\\.)){0,300}?(?:\{C\}|colou?rless|(?:\b|(?<=\\n))taps? for(?:\b|(?<=\\n))|(?:\b|(?<=\\n))mana rock(?:\b|(?<=\\n))|(?:\b|(?<=\\n))artifact(?:\b|(?<=\\n))|(?:\b|(?<=\\n))costs? (?:\{?1\}?|one)(?:\b|(?<=\\n))|\{1\})|(?:\{C\}|colou?rless|(?:\b|(?<=\\n))taps? for(?:\b|(?<=\\n))|(?:\b|(?<=\\n))mana rock(?:\b|(?<=\\n))|(?:\b|(?<=\\n))artifact(?:\b|(?<=\\n))|(?:\b|(?<=\\n))costs? (?:\{?1\}?|one)(?:\b|(?<=\\n))|\{1\})(?:(?!(?:\b|(?<=\\n))(?:text|oracle|wording|what (?:it|the card) (?:does|says))(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*\?)(?:[^"\\]|\\.)){0,300}?Sol Ring)'
---
