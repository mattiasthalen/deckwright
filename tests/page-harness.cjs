// Shared harness for the deck page test: a static server over a temp folder of
// test decks, each beside a copy of the production page, and a way to open one.

const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const { chromium } = require('playwright');

const REPO = path.resolve(__dirname, '..');
const PAGE = process.env.DECK_PAGE
  || path.join(REPO, 'plugins/deckwright/skills/deckwright/page/index.html');
const EXAMPLE = path.join(REPO, 'plugins/deckwright/skills/deckwright/page/deck.example.json');
const FONT_HOSTS = ['fonts.googleapis.com', 'fonts.gstatic.com'];
const CLOCK_START = Date.parse('2026-11-10T12:00:00Z');
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

const scryfallId = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;

// ---------- test decks ----------

function card(n, name, category, cost, type, extra = {}) {
  const { count = 1, rarity, text = '', why, bends = null, checked = true, manaValue } = extra;
  const copy = { mana_cost: cost, type_line: type, text, taken: '2026-11-10' };
  if (rarity) copy.rarity = rarity;
  if (manaValue !== undefined) copy.mana_value = manaValue;
  const c = { scryfall_id: scryfallId(n), name, count, category, tags: [], checked, bends, copy };
  if (why) c.why = why;
  return c;
}

const RICH_CARDS = [
  card(1, 'Vesk, the Burrow Mind', 'Commander', '{3}{B}', 'Legendary Creature — Rat Warlock',
    { rarity: 'mythic', text: 'Whenever another Rat you control enters, put a +1/+1 counter on a Snail you control.', why: 'The engine: every Rat that enters grows the Snail.' }),
  card(2, 'Gutter Scout', 'Ramp', '{B}', 'Creature — Rat Scout', { count: 3, rarity: 'common', text: 'Menace.', why: 'A Rat on the first turn.' }),
  card(3, 'Sewer Captain', 'Ramp', '{1}{B}', 'Creature — Rat Soldier', { rarity: 'uncommon', text: 'Other Rats you control get +1/+0.', why: 'Makes every Rat hit harder.' }),
  card(4, 'Plague Herald', 'Ramp', '{2}{B}', 'Creature — Human Cleric', { rarity: 'rare', text: 'When this creature enters, each opponent loses 2 life.', why: 'Drains the opponent as the swarm grows.' }),
  card(5, 'Tunnel Brute', 'Removal', '{3}{R}', 'Creature — Ogre Berserker', { rarity: 'common', text: 'Trample.', why: 'A big body to close the game.' }),
  card(6, 'Ash Drake', 'Removal', '{4}{R}{R}', 'Creature — Dragon', { count: 2, rarity: 'rare', text: 'Flying.', why: 'A flyer the opponent must answer.' }),
  card(7, 'Clockwork Beetle', 'Ramp', '{0}', 'Artifact Creature — Insect', { rarity: 'common', text: 'Defender.', why: 'A free body for the sacrifice outlets.' }),
  card(8, 'Ember Hound', 'Removal', '{1}{R}', 'Creature — Dog', { rarity: 'common', text: 'Haste.', why: 'Early pressure.' }),
  card(9, 'Burrow Signet', 'Ramp', '{2}', 'Artifact', { rarity: 'common', text: 'Tap: add one mana of any colour in your commander\'s colour identity.', why: 'Puts Vesk out a turn early.' }),
  card(10, 'Grim Bargain', 'Removal', '{2/B}', 'Instant', { rarity: 'uncommon', text: 'Destroy target creature with power 2 or less.', why: 'Cheap removal for early blockers.' }),
  card(11, 'Fire Lash', 'Removal', '{R}', 'Instant', { rarity: 'common', text: 'Fire Lash deals 2 damage to any target.' }),
  card(12, 'Cinder Pact', 'Removal', '{3}{B}{R}', 'Sorcery', { rarity: 'rare', text: 'Destroy all creatures that are not Rats.', why: 'A sweeper that spares the swarm.', bends: 'Not a Bloomburrow card, kept on the player\'s word' }),
  card(13, 'Doom of Ages', 'Removal', '{8}{B}', 'Sorcery', { rarity: 'mythic', text: 'Each opponent sacrifices three creatures.', why: 'A late finisher.' }),
  card(14, 'Prism Totem', 'Ramp', '{2}{W}{U}{B}{R}{G}', 'Artifact', { rarity: 'uncommon', text: '{T}: Add {B}.', why: 'Shows every colour of mana.' }),
  card(15, 'Swamp', 'Lands', '', 'Basic Land — Swamp', { count: 4, rarity: 'common' }),
  card(16, 'Mountain', 'Lands', '', 'Basic Land — Mountain', { count: 6, rarity: 'common' }),
  card(17, 'Smoldering Tunnels', 'Lands', '', 'Land', { rarity: 'uncommon', text: '{T}: Add {B} or {R}.' }),
  // Scryfall gives an adventure card both costs in mana_cost and the creature's alone as its cmc.
  card(18, 'Ember Giant', 'Removal', '{2}{R}{R} // {2}{R}', 'Creature — Giant // Instant — Adventure',
    { rarity: 'uncommon', manaValue: 4, text: 'Trample.\n//\nEmber Giant deals 2 damage to target creature.', why: 'A body and a removal spell in one.' }),
];

const RICH_LEDGER = [
  ['2026-11-01', 'criteria', 'Brawl on Arena', "the player's first answer"],
  ['2026-11-01', 'criteria', 'Rats', 'what the deck is about'],
  ['2026-11-01', 'in', `Vesk, the Burrow Mind (${scryfallId(1)})`, 'picked as the commander'],
  ['2026-11-01', 'category', 'Ramp (8)', 'template accepted'],
  ['2026-11-02', 'in', `Gutter Scout (${scryfallId(2)})`, 'cheap Rat for the first turn'],
  ['2026-11-02', 'in', `Plague Herald (${scryfallId(4)})`, 'grows the swarm'],
  ['2026-11-02', 'out', `Old Sewer Rat (${scryfallId(90)})`, 'cut for a cheaper Rat'],
  ['2026-11-02', 'finding', 'Only six removal spells', 'the player keeps them'],
  ['2026-11-03', 'in', `Fire Lash (${scryfallId(11)})`, 'answers early blockers'],
  ['2026-11-03', 'in', `Cinder Pact (${scryfallId(12)})`, 'bends the Rat theme on purpose'],
  ['2026-11-03', 'in', `Doom of Ages (${scryfallId(13)})`, 'a late finisher'],
];

const FILLER = 'The swarm wants a wide board before it wants a big one, so spend the early turns on cheap Rats and keep the removal for whatever blocks.';
const longText = n => Array.from({ length: n }, (_, i) => `${FILLER} Paragraph ${i + 1}.`).join('\n\n');

const rich = {
  version: 2,
  name: 'The Gutter Swarm',
  format: 'brawl',
  hero: scryfallId(1),
  pitch: 'A black-red Rat swarm led by Vesk. Every Rat that enters grows a Snail, and the Snail ends the game.',
  curve_note: 'Most of the spells cost three or less, so the deck casts something every turn.',
  criteria: [
    { kind: 'format', text: 'Brawl on Arena' },
    { kind: 'theme', text: 'Rats' },
    { kind: 'colours', text: 'Black-red, from the commander' },
  ],
  categories: [
    { name: 'Commander', target: 1 },
    { name: 'Ramp', target: 8, count_reason: 'Ends at 6 of 8: two places went to removal.' },
    { name: 'Removal', target: 8, count_reason: null },
    { name: 'Protection', target: 4 },
    { name: 'Lands', target: 35 },
  ],
  cards: RICH_CARDS,
  maybeboard: [{ scryfall_id: scryfallId(40), name: 'Shade of Doubt', kind: 'later', why: 'Saved for later.' }],
  dismissed_findings: [],
  last_review: null,
  tokens: [{ name: 'Snail', scryfall_id: scryfallId(50) }, { name: 'Rat', scryfall_id: scryfallId(51) }],
  scenes: [
    {
      title: 'Every Rat grows the Snail',
      lede: 'Vesk turns each Rat that enters into a counter on a Snail.',
      steps: [
        { caption: 'Vesk waits on the battlefield.', things: [{ card: 'Vesk, the Burrow Mind', does: 'enters' }] },
        { caption: 'A Rat enters and Vesk makes a Snail.', things: [
          { card: 'Vesk, the Burrow Mind' }, { card: 'Gutter Scout', does: 'enters' }, { token: 'Snail', does: 'enters', badge: '1/1' }] },
        { caption: 'The Snail is sacrificed for the win.', things: [
          { card: 'Vesk, the Burrow Mind', does: 'glows' }, { token: 'Snail', does: 'leaves', badge: '3/3' }] },
      ],
    },
    {
      title: 'Removal clears the way',
      steps: [
        { caption: 'Fire Lash hits a blocker.', things: [{ card: 'Fire Lash', does: 'enters' }] },
        { caption: 'The blocker is gone.', things: [{ card: 'Fire Lash', does: 'leaves' }] },
      ],
    },
    {
      title: 'Every motion at once',
      steps: [
        { caption: 'Five motions and one card standing still.', things: [
          { card: 'Sewer Captain', does: 'enters' }, { card: 'Plague Herald', does: 'glows' },
          { card: 'Tunnel Brute', does: 'taps' }, { card: 'Ember Hound', does: 'leaves' },
          { token: 'Rat', does: 'copies' }, { card: 'Clockwork Beetle' }] },
      ],
    },
    {
      title: 'Piles, mana and chips',
      steps: [
        { caption: 'Counters, a graveyard, a cost and damage.', things: [
          { card: 'Sewer Captain', badge: '2/2' }, { pile: 'Graveyard', count: '5' },
          { mana: '{U}{B}{R}', label: 'Pay' }, { chip: '3', label: 'Damage' }] },
      ],
    },
  ],
  handbook: [
    { title: 'How it wins', blocks: [
      { text: 'Vesk, the Burrow Mind grows the Snail while Lightning Bolt is not in this deck. Vesk alone is a short name.\n\nPlague Herald drains as the swarm grows.' },
      { text: longText(6) },
    ] },
    { title: 'Turn by turn', blocks: [
      { turns: [{ turn: 'T1', text: 'Play a Swamp and Gutter Scout.' }, { turn: 'T2', text: 'Play Sewer Captain.' }] },
      { note: 'A token that leaves the battlefield stops existing.' },
      { text: longText(6) },
    ] },
    { title: 'What to hold', blocks: [
      { list: ['Keep Grim Bargain for a flyer.', 'Hold Cinder Pact until the board is wide.'] },
      { text: longText(6) },
    ] },
    { title: 'Pairs that win', blocks: [
      { pairs: [{ cards: ['Vesk, the Burrow Mind', 'Plague Herald'], text: 'Each Rat grows the Snail and drains the opponent.' }] },
      { text: longText(6) },
    ] },
  ],
  approved: false,
};

const MONO_CARDS = [
  card(101, 'Moss Elf', 'Early creatures', '{G}', 'Creature — Elf', { count: 2, rarity: 'common', why: 'A first-turn creature.' }),
  card(102, 'Grove Bear', 'Early creatures', '{1}{G}', 'Creature — Bear', { count: 2, rarity: 'common' }),
  card(103, 'Thicket Wurm', 'Finishers', '{5}{G}{G}', 'Creature — Wurm', { count: 2, rarity: 'uncommon' }),
  card(104, 'Briar Beast', 'Finishers', '{3}{G}', 'Creature — Beast', { count: 2, rarity: 'common' }),
  card(105, 'Canopy Spider', 'Early creatures', '{2}{G}', 'Creature — Spider', { count: 2, rarity: 'common' }),
  card(106, 'Wild Growth Rite', 'Ramp', '{G}', 'Sorcery', { count: 4, rarity: 'common', text: 'Search your library for a basic land card.' }),
  card(107, 'Forest', 'Lands', '', 'Basic Land — Forest', { count: 22, rarity: 'common' }),
];

const mono = {
  version: 2,
  name: 'Green Test Stompy',
  format: 'standard',
  hero: scryfallId(103),
  pitch: 'Big green creatures, one after another.',
  curve_note: 'The curve tops out at seven for the Wurms.',
  criteria: [{ kind: 'format', text: 'Standard on Arena' }, { kind: 'colours', text: 'Mono-green' }],
  categories: [
    { name: 'Early creatures', target: 4 }, { name: 'Finishers', target: 4 },
    { name: 'Ramp', target: 4 }, { name: 'Lands', target: 24 },
  ],
  cards: MONO_CARDS,
  maybeboard: [],
  tokens: [],
  scenes: [],
  approved: true,
};

const several = {
  version: 2,
  name: 'Ash and Shadow Pack',
  format: 'brawl',
  criteria: [{ kind: 'format', text: 'Brawl on Arena' }],
  categories: [{ name: 'Commander', target: 1 }, { name: 'Spells', target: 8 }, { name: 'Lands', target: 35 }],
  cards: [
    card(201, 'Smoke Tyrant', 'Commander', '{B}{R}', 'Legendary Creature — Elemental Giant'),
    card(202, 'Night Ritual', 'Spells', '{B}', 'Instant', { text: 'Add {B}{B}{B}.' }),
    card(203, 'Quick Shock', 'Spells', '{R}', 'Instant', { text: 'Quick Shock deals 2 damage to any target.' }),
    card(204, 'Swamp', 'Lands', '', 'Basic Land — Swamp', { count: 5 }),
    card(205, 'Mountain', 'Lands', '', 'Basic Land — Mountain', { count: 5 }),
  ],
  approved: false,
};

const colourless = {
  version: 2,
  name: 'Grey Machine',
  format: 'brawl',
  hero: scryfallId(301),
  criteria: [{ kind: 'format', text: 'Brawl on Arena' }],
  categories: [{ name: 'Commander', target: 1 }, { name: 'Ramp', target: 8 }, { name: 'Lands', target: 35 }],
  cards: [
    card(301, 'Iron Golem Sovereign', 'Commander', '{4}', 'Legendary Artifact Creature — Golem', { rarity: 'rare' }),
    card(302, 'Thinking Stone', 'Ramp', '{2}', 'Artifact', { text: '{T}: Add {C}.' }),
    card(303, 'Wastes', 'Lands', '', 'Basic Land', { count: 10, text: '{T}: Add {C}.' }),
  ],
  approved: false,
};

const stray = {
  version: 2,
  name: 'Stray Things',
  format: 'brawl',
  criteria: [{ kind: 'format', text: 'Brawl on Arena' }],
  categories: [{ name: 'Commander', target: 1 }, { name: 'Protection', target: 8 }, { name: 'Lands', target: 35 }],
  cards: [
    card(401, 'Lost Picture Rat', 'Commander', '{2}{B}', 'Legendary Creature — Rat', { why: 'Its picture was never saved.' }),
    card(402, 'Swamp', 'Lands', '', 'Basic Land — Swamp', { count: 9 }),
  ],
  tokens: [],
  scenes: [{
    title: 'Names without pictures',
    steps: [{ caption: 'Three things with no picture to show.', things: [
      { card: 'Not In This Deck' }, { token: 'Unlisted Token' }, { card: 'Lost Picture Rat' }] }],
  }],
  approved: false,
};

const versionOne = {
  version: 1,
  name: 'Old Shape Deck',
  format: 'brawl',
  criteria: [{ kind: 'format', text: 'Brawl on Arena' }],
  categories: [{ name: 'Commander', target: 1 }],
  cards: [card(501, 'Old Commander', 'Commander', '{1}{B}', 'Legendary Creature — Rat')],
  handbook: [{ title: 'How it wins', text: 'Old text chapter.' }],
  scenes: [{ title: 'Every kill is a rat', svg: '<svg data-v1-scene viewBox="0 0 10 10"><text x="1" y="5">Old drawing</text></svg>' }],
  approved: false,
};

const secondThoughts = {
  version: 2,
  name: 'Second Thoughts',
  format: 'brawl',
  criteria: [{ kind: 'format', text: 'Brawl on Arena' }],
  categories: [{ name: 'Commander', target: 1 }, { name: 'Removal', target: '<b>8</b>' }, { name: 'Lands', target: 35 }],
  cards: [
    card(601, 'Marsh Warden', 'Commander', '{2}{B}', 'Legendary Creature — Rat', { why: 'Leads the deck.' }),
    card(602, 'Grim Snare', 'Removal', '{1}{B}', 'Instant', { text: 'Destroy target creature.', why: 'Kills a blocker.' }),
    card(603, 'Swamp', 'Lands', '', 'Basic Land — Swamp', { count: 9 }),
  ],
  maybeboard: [
    { scryfall_id: scryfallId(604), name: 'Maybe Rat', kind: 'later', why: 'Saved for later.' },
    { scryfall_id: scryfallId(605), name: 'Feed the Swarm', kind: 'swap', out: 'Grim Snare', why: 'Also answers enchantments.', bends: null },
  ],
  tokens: [],
  scenes: [{
    title: 'A card that is not in the deck',
    steps: [{ caption: 'Marsh Warden and a maybeboard card.', things: [{ card: 'Marsh Warden' }, { card: 'Maybe Rat' }] }],
  }],
  handbook: [{ title: 'Notes', blocks: [
    { text: 'Marsh Warden leads, and Maybe Rat waits on the maybeboard.' },
    { pairs: [{ cards: ['Marsh Warden', 'Maybe Rat'], text: 'A pair with a card that is not in the deck.' }] },
  ] }],
  approved: false,
};

// A hero whose art file was never saved, and pictures missing from a scene and a pair.
const lostFiles = {
  version: 2,
  name: 'Lost Files',
  format: 'brawl',
  hero: scryfallId(701),
  criteria: [{ kind: 'format', text: 'Brawl on Arena' }],
  categories: [{ name: 'Commander', target: 1 }, { name: 'Lands', target: 35 }],
  cards: [
    card(701, 'Faded Rat', 'Commander', '{2}{B}', 'Legendary Creature — Rat'),
    card(702, 'Swamp', 'Lands', '', 'Basic Land — Swamp', { count: 9 }),
  ],
  tokens: [],
  scenes: [{
    title: 'A picture that was never saved',
    steps: [
      { caption: 'Faded Rat waits.', things: [{ card: 'Faded Rat' }] },
      { caption: 'Faded Rat attacks.', things: [{ card: 'Faded Rat', does: 'taps' }] },
      { caption: 'Faded Rat is exiled.', things: [{ card: 'Faded Rat', does: 'leaves' }] },
    ],
  }],
  handbook: [{ title: 'Pairs', blocks: [{ pairs: [{ cards: ['Faded Rat', 'Swamp'], text: 'One picture is missing.' }] }] }],
  approved: false,
};

// The rich deck with a round on offer: two groups, the first with a heading and a
// total, the second with a heading only; one card each suggested and crossover,
// one crossover card with the name printed on Arena, and one card whose picture
// was never saved. Each is a rare creature, so counting one moves every number.
const offered = (n, name, reason, marks = {}) => ({
  scryfall_id: scryfallId(n), name, reason, ...marks,
  copy: { mana_cost: '{1}{B}', mana_value: 2, type_line: 'Creature — Rat Assassin', text: 'Deathtouch.', rarity: 'rare' },
});
const OFFER = {
  category: 'Removal',
  groups: [
    { heading: 'Rats that remove', total: 14, cards: [
      offered(61, 'Gnawing Executioner', 'Kills a blocker and leaves a Rat behind.', { suggested: true }),
      offered(62, 'Sewer Hexblade', 'Trades with anything & <i>grows</i> the swarm.', { crossover: true, printed_name: 'Hexblade of the Undercity' }),
      offered(63, 'Burrow Ambusher', 'Ambushes an attacker from the tunnels.', { suggested: false, crossover: false }),
    ] },
    { heading: 'Other removal', cards: [
      offered(64, 'Ashen Verdict', 'Clears the board but spares the swarm.', { crossover: true }),
    ] },
  ],
};
const MISSING_OFFERED_PICTURE = scryfallId(64);
const offeredDeck = { ...rich, offer: OFFER };

// A round with no ladder: one group with no heading and no total.
const offeredUnheaded = { ...several, name: 'One Round', offer: { category: 'Spells', groups: [{ cards: [
  offered(71, 'Night Bargain', 'Draws two cards for a little life.'),
  offered(72, 'Cinder Bolt', 'Burns a small flyer.'),
] }] } };
const offerNoGroups = { ...several, name: 'No Groups', offer: { category: 'Spells', groups: [] } };
const offerNoCards = { ...several, name: 'No Cards', offer: { category: 'Spells', groups: [{ heading: 'Rats that remove', total: 3, cards: [] }] } };

// Decks with no name: the hero falls back to the format and the first theme criterion.
const namelessWithTheme = { ...several, name: undefined, criteria: [
  { kind: 'format', text: 'Brawl on Arena' }, { kind: 'colours', text: 'Black-red' },
  { kind: 'theme', text: 'Rats' }, { kind: 'theme', text: 'Snails' }] };
const namelessEmptyName = { ...mono, name: '', criteria: [{ kind: 'format', text: 'Standard on Arena' }, { kind: 'theme', text: 'Big green creatures' }] };
const namelessWithoutTheme = { ...several, name: undefined, criteria: [{ kind: 'format', text: 'Brawl on Arena' }] };

// Cards of every layout the Arena list tells apart, each named with " // ".
const laidOut = (n, name, category, type, layout, extra) => {
  const c = card(n, name, category, '{1}{R}', type, extra);
  if (layout) c.copy.layout = layout;
  return c;
};
const layouts = {
  version: 2,
  name: 'Two Faced Pack',
  format: 'brawl',
  criteria: [{ kind: 'format', text: 'Brawl on Arena' }],
  categories: [{ name: 'Commander', target: 1 }, { name: 'Spells', target: 8 }, { name: 'Lands', target: 35 }],
  cards: [
    laidOut(1201, 'Moorland Watcher // Moorland Howler', 'Commander', 'Legendary Creature — Human Werewolf // Legendary Creature — Werewolf', 'transform'),
    laidOut(1202, 'Sundering Eruption // Volcanic Fissure', 'Spells', 'Sorcery // Land', 'modal_dfc'),
    laidOut(1203, 'Ember Giant // Ember Strike', 'Spells', 'Creature — Giant // Instant — Adventure', 'adventure'),
    laidOut(1204, 'Tidecaller Adept // Tidal Lesson', 'Spells', 'Creature — Merfolk Wizard // Sorcery', 'prepare'),
    laidOut(1205, 'Fire // Ice', 'Spells', 'Instant // Instant', 'split'),
    laidOut(1206, 'Odd Shape // Other Shape', 'Spells', 'Sorcery // Sorcery', 'not_a_layout'),
    laidOut(1207, 'Night // Day', 'Spells', 'Instant // Instant'),
    laidOut(1208, 'Quick Shock', 'Spells', 'Instant', 'normal'),
    laidOut(1209, 'Mountain', 'Lands', 'Basic Land — Mountain', 'normal', { count: 5 }),
  ],
  approved: false,
};

const LINE_THE_PAGE_CANNOT_SPLIT = 'Rebuilt the mana base by hand';
const LINE_THE_PAGE_CANNOT_SPLIT_WITH_ID = `Traded Faded Rat (${scryfallId(701)}) for a cheaper printing`;

// The several deck with one thing written in a shape the page cannot draw.
const SEVERAL_LEDGER = [['2026-11-05', 'in', `Smoke Tyrant (${scryfallId(201)})`, 'the commander']];
const misdrawn = over => ({ ...several, ...over });
const misdrawnScene = misdrawn({ scenes: [
  { title: 'A later step with one thing', steps: [
    { caption: 'Smoke Tyrant waits.', things: [{ card: 'Smoke Tyrant' }] },
    { caption: 'Its things are one object.', things: { card: 'Smoke Tyrant' } },
  ] },
  { title: 'A first step with one thing', steps: [{ caption: 'Its things are one object.', things: { card: 'Quick Shock' } }] },
] });
const misdrawnBlock = misdrawn({ handbook: [{ title: 'A list written as one string', blocks: [{ list: 'Keep Quick Shock.' }] }] });
const halfManaValue = misdrawn({ cards: [...several.cards, card(206, 'Half Spark', 'Spells', '{½}', 'Instant', { manaValue: 0.5 })] });

// Names with one long word, in every place the page shows a card name or handbook prose.
const LONG_WORD = 'Asmoranomardicadaistinaculdacar';
const longNames = {
  ...several,
  name: 'Long Word Deck',
  cards: [
    card(901, `${LONG_WORD} Tyrant`, 'Commander', '{B}{R}', 'Legendary Creature — Elemental', { why: `${LONG_WORD} leads.` }),
    card(902, LONG_WORD, 'Spells', '{R}', 'Instant', { text: `${LONG_WORD} deals 2 damage to any target.`, why: `${LONG_WORD} answers ${LONG_WORD}.` }),
    card(903, 'Swamp', 'Lands', '', 'Basic Land — Swamp', { count: 9 }),
  ],
  handbook: [{ title: `${LONG_WORD} wins`, blocks: [
    { text: `Cast ${LONG_WORD} early. ${LONG_WORD}${LONG_WORD} is not a card.` },
    { list: [`Keep ${LONG_WORD} for a blocker.`] },
    { note: `${LONG_WORD} answers a ${LONG_WORD}.` },
    { turns: [{ turn: 'T1', text: `Play ${LONG_WORD} and a Swamp.` }] },
    { pairs: [{ cards: [`${LONG_WORD} Tyrant`, LONG_WORD], text: `${LONG_WORD} and ${LONG_WORD}.` }] },
  ] }],
};

// A deck name with a space before, after and inside it.
const spacedName = { ...several, name: '  Ash and  Shadow Pack ' };

// A deck whose shared creature type is the only one it has, at four copies.
const tribe = (n, type) => ({
  version: 2,
  name: `${type} Test Deck`,
  format: 'standard',
  criteria: [{ kind: 'format', text: 'Standard on Arena' }],
  categories: [{ name: 'Creatures', target: 4 }, { name: 'Lands', target: 24 }],
  cards: [card(n, `${type} Test Creature`, 'Creatures', '{1}{U}', `Creature — ${type}`, { count: 4 }), card(n + 1, 'Island', 'Lands', '', 'Basic Land — Island', { count: 20 })],
  approved: false,
});
const TRIBES = { Merfolk: 'Merfolk', Kithkin: 'Kithkin', Kor: 'Kor', Elf: 'Elves' };
const TRIBES_WITHOUT_S = ['Eldrazi', 'Myr', 'Vedalken', 'Aetherborn', 'Deer'];

// Scenes with damage and drawn cards: a draw of three and of more than five,
// damage with a label and without.
const drawnScenes = name => [
  { title: 'Damage and cards', steps: [
    { caption: `${name} waits.`, things: [{ card: name }] },
    { caption: `${name} deals 3 damage to each opponent and you draw 3 cards.`, things: [{ card: name }, { damage: 3, label: 'Each opponent' }, { draw: 3 }] },
  ] },
  { title: 'A big draw', steps: [
    { caption: 'Before the big draw.', things: [{ card: name }] },
    { caption: 'You draw seven and the opponent takes 4.', things: [{ draw: 7, label: 'Seven cards' }, { damage: 4 }] },
  ] },
];

const drawnBrawl = {
  version: 2,
  name: 'Ash Keeper Draws',
  format: 'brawl',
  criteria: [{ kind: 'format', text: 'Brawl on Arena' }],
  categories: [{ name: 'Commander', target: 1 }, { name: 'Lands', target: 35 }],
  cards: [
    card(1001, 'Ash Keeper', 'Commander', '{2}{B}{R}', 'Legendary Creature — Snail Warlock'),
    card(1002, 'Swamp', 'Lands', '', 'Basic Land — Swamp', { count: 9 }),
  ],
  tokens: [],
  scenes: drawnScenes('Ash Keeper'),
  approved: false,
};

const drawnStandard = {
  version: 2,
  name: 'Blaze Imp Draws',
  format: 'standard',
  criteria: [{ kind: 'format', text: 'Standard on Arena' }],
  categories: [{ name: 'Creatures', target: 4 }, { name: 'Lands', target: 24 }],
  cards: [
    card(1101, 'Blaze Imp', 'Creatures', '{1}{R}', 'Creature — Imp', { count: 4 }),
    card(1102, 'Mountain', 'Lands', '', 'Basic Land — Mountain', { count: 20 }),
  ],
  tokens: [],
  scenes: drawnScenes('Blaze Imp'),
  approved: false,
};

// Damage and drawn cards written as a scene writer might: with a motion, with a
// badge, and with X for the amount.
const drawnOddly = {
  ...drawnBrawl,
  name: 'Ash Keeper Odd Draws',
  scenes: [
    { title: 'Damage and drawn cards that move', steps: [
      { caption: 'Nothing moves but the hit and the deal.', things: [{ damage: 3 }, { draw: 3 }] },
      { caption: 'The life total and the fan leave.', things: [{ damage: 3, does: 'leaves' }, { draw: 3, does: 'leaves' }] },
      { caption: 'The life total and the fan glow.', things: [{ damage: 3, does: 'glows' }, { draw: 3, does: 'glows' }] },
    ] },
    { title: 'A badge given', steps: [
      { caption: 'Damage and a draw, each given a badge.', things: [{ damage: 3, badge: 'x2' }, { draw: 3, badge: 'x2' }] },
    ] },
    { title: 'X damage and X cards', steps: [
      { caption: 'Ash Keeper deals X damage and you draw X cards.', things: [{ damage: 'X' }, { draw: 'X' }] },
    ] },
  ],
};

// The format written with a capital, and a word that is not a format.
const drawnCapitalBrawl = { ...drawnBrawl, format: 'Brawl' };
const drawnNoFormat = { ...drawnBrawl, format: 'constructor' };

const drawsCards = deck => (deck.scenes || []).some(s => (s.steps || []).some(st => Array.isArray(st.things) && st.things.some(t => t.draw !== undefined)));
const savesCardBack = folder => folder.back ?? (typeof folder.deck === 'object' && drawsCards(folder.deck));

const ledgerFile = entries => '# Ledger\n\n' + entries.map(([date, kind, subject, why]) => `- ${date} · ${kind} · ${subject} · ${why}`).join('\n') + '\n';

const offeredCards = deck => (Array.isArray(deck.offer?.groups) ? deck.offer.groups : []).flatMap(g => Array.isArray(g?.cards) ? g.cards : []);

function pictureIds(deck) {
  const ids = new Set();
  for (const c of [...(deck.cards || []), ...(deck.maybeboard || []), ...(deck.tokens || []), ...offeredCards(deck)]) if (c.scryfall_id) ids.add(c.scryfall_id);
  return ids;
}

// name -> {deck (object or raw text), ledger (text or absent), pictures (ids), art (ids),
// back (whether cards/back.jpg is saved; by default when a scene draws cards)}
function deckFolders() {
  const example = JSON.parse(fs.readFileSync(EXAMPLE, 'utf8'));
  const all = deck => ({ pictures: pictureIds(deck), art: deck.hero ? [deck.hero] : [] });
  return {
    rich: { deck: rich, ledger: ledgerFile(RICH_LEDGER), ...all(rich) },
    mono: { deck: mono, ...all(mono) },
    several: { deck: several, ledger: ledgerFile(SEVERAL_LEDGER), ...all(several) },
    'misdrawn-scene': { deck: misdrawnScene, ledger: ledgerFile(SEVERAL_LEDGER), ...all(misdrawnScene) },
    'misdrawn-block': { deck: misdrawnBlock, ledger: ledgerFile(SEVERAL_LEDGER), ...all(misdrawnBlock) },
    'half-mana-value': { deck: halfManaValue, ledger: ledgerFile(SEVERAL_LEDGER), ...all(halfManaValue) },
    'long-names': { deck: longNames, ...all(longNames),
      ledger: ledgerFile([['2026-11-08', 'in', `${LONG_WORD} (${scryfallId(902)})`, `${LONG_WORD} answers ${LONG_WORD}`]]) },
    'spaced-name': { deck: spacedName, ...all(spacedName) },
    colourless: { deck: colourless, ledger: ledgerFile([['2026-11-05', 'in', `Iron Golem Sovereign (${scryfallId(301)})`, 'the commander']]), ...all(colourless) },
    stray: { deck: stray, pictures: new Set([scryfallId(402)]), art: [] },
    'version-one': { deck: versionOne, ledger: '', ...all(versionOne) },
    unreadable: { deck: '{ "version": 2, "name": ', ledger: '', pictures: new Set(), art: [] },
    'deck-null': { deck: 'null', ledger: '', pictures: new Set(), art: [] },
    'deck-number': { deck: '42', ledger: '', pictures: new Set(), art: [] },
    'deck-array': { deck: '[]', ledger: '', pictures: new Set(), art: [] },
    'second-thoughts': { deck: secondThoughts, ...all(secondThoughts),
      ledger: ledgerFile([['2026-11-06', 'in', `Marsh Warden (${scryfallId(601)})`, 'the commander'], ['2026-11-06', 'out', `Maybe Rat (${scryfallId(604)})`, 'moved to the maybeboard']]) },
    'lost-files': { deck: lostFiles, pictures: new Set([scryfallId(702)]), art: [],
      ledger: ledgerFile([['2026-11-07', 'in', `Faded Rat (${scryfallId(701)})`, 'the commander']]) + `- ${LINE_THE_PAGE_CANNOT_SPLIT}\n- ${LINE_THE_PAGE_CANNOT_SPLIT_WITH_ID}\n` },
    ...Object.fromEntries([...Object.keys(TRIBES), ...TRIBES_WITHOUT_S].map((type, i) => [`tribe-${type.toLowerCase()}`, { deck: tribe(800 + 10 * i, type), ...all(tribe(800 + 10 * i, type)) }])),
    'drawn-brawl': { deck: drawnBrawl, ...all(drawnBrawl) },
    'drawn-standard': { deck: drawnStandard, ...all(drawnStandard) },
    'drawn-no-back': { deck: drawnBrawl, ...all(drawnBrawl), back: false },
    'drawn-oddly': { deck: drawnOddly, ...all(drawnOddly) },
    'drawn-capital-brawl': { deck: drawnCapitalBrawl, ...all(drawnCapitalBrawl) },
    'drawn-no-format': { deck: drawnNoFormat, ...all(drawnNoFormat) },
    // The rich deck with every file given to the page in window.DECK_FILES and none in the folder.
    packed: { deck: rich, packedFrom: 'rich', pictures: new Set(), art: [] },
    'packed-drawn': { deck: drawnBrawl, packedFrom: 'drawn-brawl', pictures: new Set(), art: [] },
    offered: { deck: offeredDeck, ledger: ledgerFile(RICH_LEDGER), art: [rich.hero],
      pictures: new Set([...pictureIds(offeredDeck)].filter(id => id !== MISSING_OFFERED_PICTURE)) },
    'offered-unheaded': { deck: offeredUnheaded, ledger: ledgerFile(SEVERAL_LEDGER), ...all(offeredUnheaded) },
    'offer-no-groups': { deck: offerNoGroups, ledger: ledgerFile(SEVERAL_LEDGER), ...all(offerNoGroups) },
    'offer-no-cards': { deck: offerNoCards, ledger: ledgerFile(SEVERAL_LEDGER), ...all(offerNoCards) },
    'nameless-with-theme': { deck: namelessWithTheme, ...all(namelessWithTheme) },
    'nameless-empty-name': { deck: namelessEmptyName, ...all(namelessEmptyName) },
    'nameless-without-theme': { deck: namelessWithoutTheme, ...all(namelessWithoutTheme) },
    layouts: { deck: layouts, ...all(layouts) },
    example: { deck: example, ledger: ledgerFile([['2026-11-10', 'in', 'An example card', 'the example ledger']]), ...all(example) },
  };
}

// ---------- server ----------

const TYPES = { '.html': 'text/html; charset=utf-8', '.json': 'application/json', '.md': 'text/markdown; charset=utf-8', '.jpg': 'image/jpeg' };

async function jpeg(browser, width, height, colour) {
  const page = await browser.newPage({ viewport: { width, height } });
  await page.setContent(`<body style="margin:0;background:${colour}"></body>`);
  const bytes = await page.screenshot({ type: 'jpeg', quality: 40 });
  await page.close();
  return bytes;
}

// The page with the deck folder's files set in window.DECK_FILES by a script
// before the page's own: text files as text, pictures as data URLs.
function packedPage(page, folder, cardPicture, artCrop, cardBack) {
  const dataUrl = bytes => `data:image/jpeg;base64,${Buffer.from(bytes).toString('base64')}`;
  const files = { 'deck.json': JSON.stringify(folder.deck) };
  if (folder.ledger !== undefined) files['LEDGER.md'] = folder.ledger;
  for (const id of folder.pictures) files[`cards/${id}.jpg`] = dataUrl(cardPicture);
  for (const id of folder.art) files[`art/${id}.jpg`] = dataUrl(artCrop);
  if (savesCardBack(folder)) files['cards/back.jpg'] = dataUrl(cardBack);
  const script = `<script>window.DECK_FILES = ${JSON.stringify(files).replace(/</g, '\\u003c')};</script>\n`;
  const at = page.indexOf('<script>');
  if (at < 0) throw new Error('the page has no inline script to put DECK_FILES before');
  return page.slice(0, at) + script + page.slice(at);
}

// The three pictures every test deck saves: a card, an artwork crop and the card back.
async function testPictures(browser) {
  return {
    cardPicture: await jpeg(browser, 488, 680, '#3b5a7a'),
    artCrop: await jpeg(browser, 626, 457, '#7a5a3b'),
    cardBack: await jpeg(browser, 488, 680, '#4a2f1c'),
  };
}

// The files a save writes into a deck folder: deck.json, LEDGER.md and the pictures.
function writeSavedFiles(dir, f, { cardPicture, artCrop, cardBack }) {
  fs.mkdirSync(path.join(dir, 'cards'), { recursive: true });
  fs.mkdirSync(path.join(dir, 'art'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'deck.json'), typeof f.deck === 'string' ? f.deck : JSON.stringify(f.deck, null, 2));
  if (f.ledger !== undefined) fs.writeFileSync(path.join(dir, 'LEDGER.md'), f.ledger);
  for (const id of f.pictures) fs.writeFileSync(path.join(dir, 'cards', `${id}.jpg`), cardPicture);
  for (const id of f.art) fs.writeFileSync(path.join(dir, 'art', `${id}.jpg`), artCrop);
  if (savesCardBack(f)) fs.writeFileSync(path.join(dir, 'cards', 'back.jpg'), cardBack);
}

async function startDeckServer(browser) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'deck-page-'));
  const saved = await testPictures(browser);
  const page = fs.readFileSync(PAGE);
  const folders = deckFolders();
  for (const [name, f] of Object.entries(folders)) {
    const dir = path.join(root, name);
    if (f.packedFrom) {
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, 'index.html'), packedPage(page.toString('utf8'), folders[f.packedFrom], saved.cardPicture, saved.artCrop, saved.cardBack));
      continue;
    }
    writeSavedFiles(dir, f, saved);
    fs.writeFileSync(path.join(dir, 'index.html'), page);
  }
  const server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    if (pathname === '/favicon.ico') { res.writeHead(204); res.end(); return; }
    const file = path.join(root, pathname.endsWith('/') ? pathname + 'index.html' : pathname);
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream', 'cache-control': 'no-store' });
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  return {
    origin,
    folders,
    close: () => { server.close(); fs.rmSync(root, { recursive: true, force: true }); },
  };
}

// ---------- opening a deck page ----------

// Opens one test deck in a fresh context. Requests to the font hosts are answered
// with nothing so the test stays offline; any other request off the served origin
// is refused and recorded.
async function openDeck(browser, server, name, options = {}) {
  const { viewport = { width: 1280, height: 800 }, reducedMotion = 'no-preference', clock = false, clipboard = true, refuse = [] } = options;
  const context = await browser.newContext({ viewport, reducedMotion });
  if (clipboard) await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: server.origin });
  const outside = [], fonts = [], errors = [], requested = [], missing = [];
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin === server.origin) {
      requested.push(url.pathname);
      // A refused path fails as a network error does, not as a 404.
      return refuse.some(p => url.pathname.endsWith(p)) ? route.abort('failed') : route.continue();
    }
    if (FONT_HOSTS.includes(url.hostname)) {
      fonts.push(url.href);
      return route.fulfill({ status: 200, contentType: url.hostname === 'fonts.googleapis.com' ? 'text/css' : 'font/woff2', body: '' });
    }
    outside.push(url.href);
    return route.abort();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(4000);
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push(String(e)));
  page.on('response', r => { if (r.status() === 404) missing.push(new URL(r.url()).pathname); });
  // The clock is paused from the start, so a scene moves only when a test runs the clock.
  if (clock) {
    await page.clock.install({ time: CLOCK_START });
    await page.clock.pauseAt(CLOCK_START + 1);
  }
  await page.goto(`${server.origin}/${name}/`, { waitUntil: 'load' });
  await untilDrawn(page);
  return { page, context, outside, fonts, errors, requested, missing, deck: server.folders[name].deck, close: () => context.close() };
}

// Returns once the page has drawn all it draws from its files: the ledger, read
// last, is drawn or left out, or the hero says deck.json could not be read. The
// page is watched rather than polled, since a paused clock stops its timers.
async function untilDrawn(page, ms = 4000) {
  const watched = page.evaluate(() => new Promise(done => {
    const finished = () => /Could not read deck\.json/.test(document.getElementById('top')?.textContent || '')
      || (l => l && (l.childElementCount > 0 || l.hidden))(document.getElementById('ledger'));
    if (finished()) return done();
    new MutationObserver((_, observer) => { if (finished()) { observer.disconnect(); done(); } })
      .observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true });
  }));
  let timer;
  const late = new Promise((_, fail) => { timer = setTimeout(() => fail(new Error(`the page did not finish drawing within ${ms} ms`)), ms); });
  try { await Promise.race([watched, late]); } finally { clearTimeout(timer); }
}

async function withDeck(browser, server, name, options, use) {
  if (typeof options === 'function') { use = options; options = {}; }
  const opened = await openDeck(browser, server, name, options);
  try { return await use(opened); } finally { await opened.close(); }
}

module.exports = {
  REPO, PAGE, EXAMPLE, FONT_HOSTS, UUID, chromium, scryfallId, RICH_LEDGER, OFFER, MISSING_OFFERED_PICTURE, offeredCards, deckFolders, testPictures, writeSavedFiles, TRIBES, TRIBES_WITHOUT_S, LINE_THE_PAGE_CANNOT_SPLIT, LINE_THE_PAGE_CANNOT_SPLIT_WITH_ID,
  LONG_WORD, startDeckServer, withDeck, untilDrawn,
};
