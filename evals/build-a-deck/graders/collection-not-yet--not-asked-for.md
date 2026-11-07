---
# E14: no assistant message asks for the collection or offers to read, import or use it.
type: regex
target: trace
flags: i
match: not_contains
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:(?:\b|(?<=\\n))(?:share|send|upload|paste|export|attach|give me|point me (?:to|at))(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*?(?:\b|(?<=\\n))(?:collection|cards you own|list|export|file)(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*\?|(?:\b|(?<=\\n))(?:I can|I could|I''ll|I will|happy to|want me to)\s+(?:\w+\s+){0,3}?(?:read|import|load|use|parse|work from)\s+(?:\w+\s+){0,2}?(?:collection|export|list|file)(?:\b|(?<=\\n)))'
---
