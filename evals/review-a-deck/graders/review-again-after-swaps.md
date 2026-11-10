---
# AC34: only the maybeboard changed, which leaves the review standing, so no measure runs after the first review is recorded. A measure before the first review, a probe included, is the first review's own.
type: regex
target: trace
flags: i
match: not_contains
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\")?\s+review(?:\b|(?<=\\n))[\s\S]*?"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\")?\s+measure(?:\b|(?<=\\n))'
---
