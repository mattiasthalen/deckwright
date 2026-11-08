---
# C24: the squirrels recorded before the change are still in the decklist.
type: regex
target: { source: file, path: decks/trash-pandas.html }
pattern: '^(?=[\s\S]*\n1 Thornvault Forager(?:\s|<))(?=[\s\S]*\n1 Treetop Sentries(?:\s|<))(?=[\s\S]*\n1 Bakersbane Duo(?:\s|<))'
---
