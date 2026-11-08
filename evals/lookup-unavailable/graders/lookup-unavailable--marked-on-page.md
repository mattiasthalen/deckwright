---
# E2: the page marks it as the player's text.
type: regex
target: { source: file, path: deck.html }
pattern: 'data-section="player-text"[^>]*>(?:(?!data-section=)[\s\S])*?Sol Ring'
---
