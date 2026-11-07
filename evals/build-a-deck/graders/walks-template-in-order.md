---
# AC13: Lands is introduced with its target (38) and its purpose from counts_when (the type line), and later Ramp with its target (10) and its purpose (extra mana or lands beyond the land drop). Purpose and target are looked for within 400 characters of the category name, in the same message.
type: regex
target: trace
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:(?:\b|(?<=\\n))Lands(?:\b|(?<=\\n))(?=(?:[^"\\]|\\.){0,300}?(?:(?:\b|(?<=\\n))38(?:\b|(?<=\\n))))|(?:\b|(?<=\\n))38 [Ll]ands(?:\b|(?<=\\n)))(?:(?=(?:[^"\\]|\\.){0,400}?(?:[Tt]ype line|mana base))|(?<=(?:[Tt]ype line|mana base)(?:[^"\\]|\\.){0,400}))(?:(?:[^"\\]|\\.)*?|[\s\S]*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?)(?:(?:\b|(?<=\\n))Ramp(?:\b|(?<=\\n))(?=(?:[^"\\]|\\.){0,300}?(?:(?:\b|(?<=\\n))10(?:\b|(?<=\\n))))|(?:\b|(?<=\\n))10 [Rr]amp(?:\b|(?<=\\n)))(?:(?=(?:[^"\\]|\\.){0,400}?(?:extra mana|more mana|mana or lands|lands? (?:onto|into) (?:play|the battlefield)|beyond (?:the|your)(?: one)? land drop))|(?<=(?:extra mana|more mana|mana or lands|lands? (?:onto|into) (?:play|the battlefield)|beyond (?:the|your)(?: one)? land drop)(?:[^"\\]|\\.){0,400}))'
---
