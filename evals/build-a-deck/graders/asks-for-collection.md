---
# C33 (amended for C36): an assistant message asks for the player's collection in the skill's terms, a ManaBox CSV export or an export: in one sentence that ends in a question mark, or within 300 characters of a request for it (give, hand or send me, share, paste, point me to, upload, attach, "I need", "what's the path", "where's"). Asking whether the player has one counts; saying it cannot be used does not.
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:(?:\b|(?<=\\n))(?:ManaBox|CSV|export)(?:[^"\\.!?]|\\[^n])*\?|(?:\b|(?<=\\n))(?:ManaBox|CSV|export)(?:[^"\\]|\\.){0,300}?(?:\b|(?<=\\n))(?:give me|hand me|send me|share|paste|point me (?:to|at)|upload|attach|I need|I''ll need|what''s the path|where''s|where is)(?:\b|(?<=\\n))|(?:\b|(?<=\\n))(?:give me|hand me|send me|share|paste|point me (?:to|at)|upload|attach|I need|I''ll need|what''s the path|where''s|where is)(?:\b|(?<=\\n))(?:[^"\\]|\\.){0,300}?(?:\b|(?<=\\n))(?:ManaBox|CSV|export))'
---
