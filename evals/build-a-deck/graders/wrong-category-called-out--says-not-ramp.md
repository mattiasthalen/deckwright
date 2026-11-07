---
# AC17, the part a pattern can see: an assistant message says Sign in Blood is not ramp.
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:Sign in Blood(?:[^"\\]|\\.)*?(?:\bnot|isn''t|isn’t|doesn''t count as|does not count as|wouldn''t count as|won''t count as)\s+(?:really\s+|actually\s+|a\s+|as\s+)*ramp|(?:\bnot|isn''t|isn’t|doesn''t count as|does not count as)\s+(?:really\s+|actually\s+|a\s+|as\s+)*ramp(?:[^"\\]|\\.)*?Sign in Blood)'
---
