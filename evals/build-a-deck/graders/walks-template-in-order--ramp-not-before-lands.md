---
# AC13: Ramp is not introduced, with its target and purpose, before Lands is.
type: regex
target: trace
match: not_contains
pattern: '^(?:(?!"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:(?:\b|(?<=\\n))Lands(?:\b|(?<=\\n))(?=(?:[^"\\]|\\.){0,300}?(?:(?:\b|(?<=\\n))38(?:\b|(?<=\\n))))|(?:\b|(?<=\\n))38 [Ll]ands(?:\b|(?<=\\n)))(?:(?=(?:[^"\\]|\\.){0,400}?(?:[Tt]ype line|mana base))|(?<=(?:[Tt]ype line|mana base)(?:[^"\\]|\\.){0,400})))[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:(?!(?:(?:\b|(?<=\\n))Lands(?:\b|(?<=\\n))(?=(?:[^"\\]|\\.){0,300}?(?:(?:\b|(?<=\\n))38(?:\b|(?<=\\n))))|(?:\b|(?<=\\n))38 [Ll]ands(?:\b|(?<=\\n)))(?:(?=(?:[^"\\]|\\.){0,400}?(?:[Tt]ype line|mana base))|(?<=(?:[Tt]ype line|mana base)(?:[^"\\]|\\.){0,400})))(?:[^"\\]|\\.))*?(?:(?:\b|(?<=\\n))Ramp(?:\b|(?<=\\n))(?=(?:[^"\\]|\\.){0,300}?(?:(?:\b|(?<=\\n))10(?:\b|(?<=\\n))))|(?:\b|(?<=\\n))10 [Rr]amp(?:\b|(?<=\\n)))(?:(?=(?:[^"\\]|\\.){0,400}?(?:extra mana|more mana|mana or lands|lands? (?:onto|into) (?:play|the battlefield)|beyond (?:the|your)(?: one)? land drop))|(?<=(?:extra mana|more mana|mana or lands|lands? (?:onto|into) (?:play|the battlefield)|beyond (?:the|your)(?: one)? land drop)(?:[^"\\]|\\.){0,400}))'
---
