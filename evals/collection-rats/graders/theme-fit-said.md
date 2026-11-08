---
# E17: after the theme is given, an assistant message says why rats fit Vren: rats within 300 characters of a fit word, and Vren or the commander within 400 characters.
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?=(?:[^"\\]|\\.){0,400}?(?:Vren|commander))(?:\b|(?<=\\n))rats?(?:\b|(?<=\\n))(?:[^"\\]|\\.){0,300}?(?:fits?|suits?|matches|works|lines? up|natural|perfect|right at home|made for|built for|exactly|squarely|on[- ]theme|cares about|wants)'
---
