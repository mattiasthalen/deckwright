---
# AC31: an assistant message asks "swap it in now, or on the maybeboard?" (swap … now … maybeboard …?).
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))swap(?:\b|(?<=\\n))(?:[^"\\?]|\\[^n]){0,80}?(?:\b|(?<=\\n))now(?:\b|(?<=\\n))(?:[^"\\?]|\\[^n]){0,80}?(?:\b|(?<=\\n))maybeboard(?:[^"\\?]|\\[^n]){0,40}?\?'
---
