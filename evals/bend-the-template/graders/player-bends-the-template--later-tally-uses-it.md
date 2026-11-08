---
# AC19: a tally after the change reports Ramp's target as 8 (the tally's JSON, as it appears escaped in the trace). An add prints the tally too, so its output counts.
type: regex
target: trace
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\btarget\b(?:[^"\\]|\\.)*?[Rr]amp(?:[^"\\]|\\.)*?\b8\b[\s\S]*"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\b(?:tally|add)\b[\s\S]*?(?:\\"name\\":\s*\\"Ramp\\"[^{}]*?\\"target\\":\s*8\b|\\"target\\":\s*8\b[^{}]*?\\"name\\":\s*\\"Ramp\\")'
---
