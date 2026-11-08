---
# E4: no category is started; none of the template's targets appears beside its category.
type: regex
target: last_message
flags: i
match: not_contains
pattern: '\b(?:lands\b[^\n]{0,40}\b38|ramp\b[^\n]{0,40}\b10)\b'
---
