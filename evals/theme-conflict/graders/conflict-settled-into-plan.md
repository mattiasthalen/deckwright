---
# C23, explained and asked: before the plan sentence is recorded, an assistant message speaks of squirrels and of Muerra or her Raccoons, says how they pull against each other, and then asks the player (a question mark after it in that message).
type: regex
target: trace
flags: i
pattern: '^(?:(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant"))(?=(?<L1>[^\n]*\n))\k<L1>|(?!(?<![^\n])(?![^\n]*"(?:name":"Bash"|role":"assistant")))(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:plan)(?:\b|(?<=\\n)))[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?=(?:[^"\\]|\\.)*?squirrel)(?=(?:[^"\\]|\\.)*?(?:Muerra|raccoon))(?:[^"\\]|\\.)*?(?:pulls? against|pulling against|clash(?:es)?|conflicts?|at odds|tension|works? against|cuts? against|fights?|outside (?:her|Muerra\x27s|Muerra’s|the commander\x27s|the commander’s|your commander\x27s|your commander’s) colou?r|(?:only|just) (?:counts|cares about|rewards|pays for|sees) Raccoons|(?:aren\x27t|aren’t|isn\x27t|isn’t|not) Raccoons?|(?:doesn\x27t|doesn’t|does not) (?:count|care about|reward|see) Squirrels)(?:[^"\\]|\\.)*?\?'
---
