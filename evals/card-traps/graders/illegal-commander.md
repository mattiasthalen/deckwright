---
# E7: after Llanowar Elves is looked up and before any deck is started, an assistant message says within 600 characters of its name that it cannot be a commander, that it is not legendary, and asks whether to keep it or choose another.
type: regex
target: trace
flags: i
pattern: '^(?:(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))new(?:\b|(?<=\\n)))[\s\S])*?"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))lookup(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Llanowar Elves(?:(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))new(?:\b|(?<=\\n)))[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?Llanowar Elves(?=(?:[^"\\]|\\.){0,600}?(?:(?:can''t|can’t|cannot|can not|isn''t able to|not able to|isn''t eligible|not eligible|isn''t legal as|not legal as|doesn''t qualify)(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n]){0,40}?(?:\b|(?<=\\n))(?:commander|lead)))(?=(?:[^"\\]|\\.){0,600}?(?:(?:\b|(?<=\\n))not (?:a )?legendary|isn''t (?:a )?legendary|isn’t (?:a )?legendary|non-?legendary|lacks? (?:the )?(?:word |supertype )?legendary|without (?:the )?legendary|(?:\b|(?<=\\n))no legendary))(?=(?:[^"\\]|\\.){0,600}?(?:(?:\b|(?<=\\n))(?:keep|another|different|choose|pick|instead|anyway|else)(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*\?))'
---
