---
# C24: after the theme is changed, the theme judgements are redone with the script's judge.
type: regex
target: trace
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:add)(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?Treetop Sentries[\s\S]*?"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:theme)(?:\b|(?<=\\n))[\s\S]*?"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:judge)(?:\b|(?<=\\n))'
---
