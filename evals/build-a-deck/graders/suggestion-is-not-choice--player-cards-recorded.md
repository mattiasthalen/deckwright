---
# The whitelist above means something only if the player's own yeses were recorded.
type: regex
target: { source: file, path: deck.html }
pattern: '^(?=[\s\S]*\n1 Sol Ring(?:\s|<))(?=[\s\S]*\n1 Sign in Blood(?:\s|<))(?=[\s\S]*\n18 Swamp(?:\s|<))(?=[\s\S]*\n17 Forest(?:\s|<))(?=[\s\S]*\n1 Command Tower(?:\s|<))'
---
