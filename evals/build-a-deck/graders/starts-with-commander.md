---
# AC12: an assistant message asks for the commander, and nothing before that question, in it or in an earlier message, gives a category its target, asks about a category, or runs the script (no lookup, so no card offered). Saying the template or that categories will follow is allowed.
type: regex
target: trace
flags: i
pattern: '^(?:(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:lookup|new|add|tally|target)(?:\b|(?<=\\n))|"role":"assistant"[^\n]*"type":"text","text":"(?:(?!(?:\b|(?<=\\n))(?:commander|legend|general)(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*\?)(?:[^"\\]|\\.))*?(?:(?:\b|(?<=\\n))(?:Lands|Ramp|Card advantage|Targeted disruption|Mass disruption|Plan)(?:\b|(?<=\\n))(?:[^"\\]|\\.){0,40}?(?:\b|(?<=\\n))(?:38|10|12|6|30)(?:\b|(?<=\\n))|(?:\b|(?<=\\n))(?:lands?|ramp|card advantage|disruption)(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*\?))[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:(?!(?:\b|(?<=\\n))(?:Lands|Ramp|Card advantage|Targeted disruption|Mass disruption|Plan)(?:\b|(?<=\\n))(?:[^"\\]|\\.){0,40}?(?:\b|(?<=\\n))(?:38|10|12|6|30)(?:\b|(?<=\\n))|(?:\b|(?<=\\n))(?:lands?|ramp|card advantage|disruption)(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*\?)(?:[^"\\]|\\.))*?(?:\b|(?<=\\n))(?:commander|legend|general)(?:\b|(?<=\\n))(?:[^"\\.!?]|\\[^n])*\?'
---
