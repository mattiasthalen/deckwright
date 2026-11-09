---
# C33 (amended for C36): an assistant message asks for the player's collection in the skill's terms, a ManaBox CSV export or an export: in one sentence that ends in a question mark, or within 300 characters of a request for it (give, hand or send me, share, paste, point me to, upload, attach, "I need", "what's the path", "where's"). Asking whether the player has one counts; saying it cannot be used does not. Once the player has said they keep a collection, which the scripted player says before it is asked for, a question about the file in a message about the collection counts too ("What's the file?").
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:(?:\b|(?<=\\n))(?:ManaBox|CSV|export)(?:[^"\\.!?]|\\[^n])*\?|(?:\b|(?<=\\n))(?:ManaBox|CSV|export)(?:[^"\\]|\\.){0,300}?(?:\b|(?<=\\n))(?:give me|hand me|send me|share|paste|point me (?:to|at)|upload|attach|I need|I''ll need|what''s the path|where''s|where is)(?:\b|(?<=\\n))|(?:\b|(?<=\\n))(?:give me|hand me|send me|share|paste|point me (?:to|at)|upload|attach|I need|I''ll need|what''s the path|where''s|where is)(?:\b|(?<=\\n))(?:[^"\\]|\\.){0,300}?(?:\b|(?<=\\n))(?:ManaBox|CSV|export)|(?:\b|(?<=\\n))collection(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))file(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*\?)'
---
