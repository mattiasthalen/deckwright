---
# C25: the collection cannot fill Ramp: an assistant message about ramp says how many the collection has (a number within 80 characters of your collection, you own, you have) and, later in that message, labels cards not owned.
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?=(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))ramp)(?:[^"\\]|\\.)*?(?:(?:\b|(?<=\\n))(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)(?:\b|(?<=\\n))(?:[^"\\]|\\.){0,80}?(?:your collection|you own|you have|owned by you|in your binders?|from your cards)|(?:your collection|you own|you have|owned by you|in your binders?|from your cards)(?:[^"\\]|\\.){0,80}?(?:\b|(?<=\\n))(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)(?:\b|(?<=\\n)))(?:[^"\\]|\\.)*?not owned'
---
