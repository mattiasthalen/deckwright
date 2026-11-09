---
# AC28: the planted Game Changer. After Demonic Tutor is looked up, an assistant message names it, calls it a Game Changer (not "not a Game Changer") and speaks of the bracket: the deck's target is 2, which allows none.
type: regex
target: trace
flags: i
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+lookup(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Demonic Tutor(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?=(?:[^"\\]|\\.)*?Demonic Tutor)(?=(?:[^"\\]|\\.)*?(?<!(?:\bnot|n''t|n’t|\bno)\s+(?:an?\s+|one of the\s+)?)game[ -]?changer)(?=(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))bracket)'
---
