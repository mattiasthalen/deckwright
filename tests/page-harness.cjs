// Shared harness for the deck page test: a static server over a temp folder of
// test decks, each beside a copy of the production template, and a way to open one.

const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const { chromium } = require('playwright');

const REPO = path.resolve(__dirname, '..');
const TEMPLATE = process.env.DECK_PAGE_TEMPLATE
  || path.join(REPO, 'plugins/deckwright/skills/deckwright/page/index.html');
const EXAMPLE = path.join(REPO, 'plugins/deckwright/skills/deckwright/page/deck.example.json');
const FONT_HOSTS = ['fonts.googleapis.com', 'fonts.gstatic.com'];
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

const scryfallId = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;

// ---------- test decks ----------

function card(n, name, category, cost, type, extra = {}) {
  const { count = 1, rarity, text = '', why, bends = null, checked = true } = extra;
  const copy = { mana_cost: cost, type_line: type, text, taken: '2026-11-10' };
  if (rarity) copy.rarity = rarity;
  const c = { scryfall_id: scryfallId(n), name, count, category, tags: [], checked, bends, copy };
  if (why) c.why = why;
  return c;
}

const RICH_CARDS = [
  card(1, 'Vesk, the Burrow Mind', 'Commander', '{3}{B}', 'Legendary Creature — Rat Warlock',
    { rarity: 'mythic', text: 'Whenever another Rat you control enters, put a +1/+1 counter on a Snail you control.', why: 'The engine: every Rat that enters grows the Snail.' }),
  card(2, 'Gutter Scout', 'Ramp', '{B}', 'Creature — Rat Scout', { rarity: 'common', text: 'Menace.', why: 'A Rat on the first turn.' }),
  card(3, 'Sewer Captain', 'Ramp', '{1}{B}', 'Creature — Rat Soldier', { rarity: 'uncommon', text: 'Other Rats you control get +1/+0.', why: 'Makes every Rat hit harder.' }),
  card(4, 'Plague Herald', 'Ramp', '{2}{B}', 'Creature — Rat Cleric', { rarity: 'rare', text: 'When this creature enters, each opponent loses 2 life.', why: 'Drains the opponent as the swarm grows.' }),
  card(5, 'Tunnel Brute', 'Removal', '{3}{R}', 'Creature — Rat Berserker', { rarity: 'common', text: 'Trample.', why: 'A big Rat to close the game.' }),
  card(6, 'Ash Drake', 'Removal', '{4}{R}{R}', 'Creature — Dragon', { rarity: 'rare', text: 'Flying.', why: 'A flyer the opponent must answer.' }),
  card(7, 'Clockwork Beetle', 'Ramp', '{0}', 'Artifact Creature — Insect', { rarity: 'common', text: 'Defender.', why: 'A free body for the sacrifice outlets.' }),
  card(8, 'Ember Hound', 'Removal', '{1}{R}', 'Creature — Dog', { rarity: 'common', text: 'Haste.', why: 'Early pressure.' }),
  card(9, 'Burrow Signet', 'Ramp', '{2}', 'Artifact', { rarity: 'common', text: 'Tap: add one mana of any colour in your commander\'s colour identity.', why: 'Puts Vesk out a turn early.' }),
  card(10, 'Grim Bargain', 'Removal', '{1}{B}', 'Instant', { rarity: 'uncommon', text: 'Destroy target creature with power 2 or less.', why: 'Cheap removal for early blockers.' }),
  card(11, 'Fire Lash', 'Removal', '{R}', 'Instant', { rarity: 'common', text: 'Fire Lash deals 2 damage to any target.' }),
  card(12, 'Cinder Pact', 'Removal', '{3}{B}{R}', 'Sorcery', { rarity: 'rare', text: 'Destroy all creatures that are not Rats.', why: 'A sweeper that spares the swarm.', bends: 'Not a Bloomburrow card, kept on the player\'s word' }),
  card(13, 'Doom of Ages', 'Removal', '{8}{B}', 'Sorcery', { rarity: 'mythic', text: 'Each opponent sacrifices three creatures.', why: 'A late finisher.' }),
  card(14, 'Prism Totem', 'Ramp', '{2}{W}{U}{B}{R}{G}', 'Artifact', { rarity: 'uncommon', text: '{T}: Add {B}.', why: 'Shows every colour of mana.' }),
  card(15, 'Swamp', 'Lands', '', 'Basic Land — Swamp', { count: 8, rarity: 'common' }),
  card(16, 'Mountain', 'Lands', '', 'Basic Land — Mountain', { count: 6, rarity: 'common' }),
  card(17, 'Smoldering Tunnels', 'Lands', '', 'Land', { rarity: 'uncommon', text: '{T}: Add {B} or {R}.' }),
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

const ledgerFile = entries => '# Ledger\n\n' + entries.map(([date, kind, subject, why]) => `- ${date} · ${kind} · ${subject} · ${why}`).join('\n') + '\n';

function pictureIds(deck) {
  const ids = new Set();
  for (const c of [...(deck.cards || []), ...(deck.maybeboard || []), ...(deck.tokens || [])]) if (c.scryfall_id) ids.add(c.scryfall_id);
  return ids;
}

// name -> {deck (object or raw text), ledger (text or absent), pictures (ids), art (ids)}
function deckFolders() {
  const example = JSON.parse(fs.readFileSync(EXAMPLE, 'utf8'));
  const all = deck => ({ pictures: pictureIds(deck), art: deck.hero ? [deck.hero] : [] });
  return {
    rich: { deck: rich, ledger: ledgerFile(RICH_LEDGER), ...all(rich) },
    mono: { deck: mono, ...all(mono) },
    several: { deck: several, ledger: ledgerFile([['2026-11-05', 'in', `Smoke Tyrant (${scryfallId(201)})`, 'the commander']]), ...all(several) },
    colourless: { deck: colourless, ledger: ledgerFile([['2026-11-05', 'in', `Iron Golem Sovereign (${scryfallId(301)})`, 'the commander']]), ...all(colourless) },
    stray: { deck: stray, pictures: new Set([scryfallId(402)]), art: [] },
    'version-one': { deck: versionOne, ledger: '', ...all(versionOne) },
    unreadable: { deck: '{ "version": 2, "name": ', ledger: '', pictures: new Set(), art: [] },
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

async function startDeckServer(browser) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'deck-page-'));
  const cardPicture = await jpeg(browser, 488, 680, '#3b5a7a');
  const artCrop = await jpeg(browser, 626, 457, '#7a5a3b');
  const template = fs.readFileSync(TEMPLATE);
  const folders = deckFolders();
  for (const [name, f] of Object.entries(folders)) {
    const dir = path.join(root, name);
    fs.mkdirSync(path.join(dir, 'cards'), { recursive: true });
    fs.mkdirSync(path.join(dir, 'art'), { recursive: true });
    fs.writeFileSync(path.join(dir, 'index.html'), template);
    fs.writeFileSync(path.join(dir, 'deck.json'), typeof f.deck === 'string' ? f.deck : JSON.stringify(f.deck, null, 2));
    if (f.ledger !== undefined) fs.writeFileSync(path.join(dir, 'LEDGER.md'), f.ledger);
    for (const id of f.pictures) fs.writeFileSync(path.join(dir, 'cards', `${id}.jpg`), cardPicture);
    for (const id of f.art) fs.writeFileSync(path.join(dir, 'art', `${id}.jpg`), artCrop);
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
  const { viewport = { width: 1280, height: 800 }, reducedMotion = 'no-preference', clock = false } = options;
  const context = await browser.newContext({ viewport, reducedMotion });
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: server.origin });
  const outside = [], fonts = [], errors = [];
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin === server.origin) return route.continue();
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
  if (clock) await page.clock.install();
  await page.goto(`${server.origin}/${name}/`, { waitUntil: 'networkidle' });
  return { page, context, outside, fonts, errors, deck: server.folders[name].deck, close: () => context.close() };
}

async function withDeck(browser, server, name, options, use) {
  if (typeof options === 'function') { use = options; options = {}; }
  const opened = await openDeck(browser, server, name, options);
  try { return await use(opened); } finally { await opened.close(); }
}

// ---------- reading what the page shows ----------

const arenaList = deck => {
  const live = deck.cards.filter(c => (c.count ?? 1) > 0);
  const line = c => `${c.count ?? 1} ${c.name}`;
  const commander = live.filter(c => c.category === 'Commander'), rest = live.filter(c => c.category !== 'Commander');
  return (commander.length ? `Commander\n${commander.map(line).join('\n')}\n\n` : '') + `Deck\n${rest.map(line).join('\n')}`;
};

function rgb(css) {
  const m = String(css).match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/);
  if (!m) throw new Error(`not an rgb colour: ${css}`);
  return m.slice(1, 4).map(Number);
}

function hsl([r, g, b]) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2, d = max - min;
  if (d === 0) return { h: 0, s: 0, l };
  const s = d / (1 - Math.abs(2 * l - 1));
  const h = max === r ? 60 * (((g - b) / d) % 6) : max === g ? 60 * ((b - r) / d + 2) : 60 * ((r - g) / d + 4);
  return { h: (h + 360) % 360, s, l };
}

// Resolves any CSS colour expression (a custom property included) to rgb() in the page.
const resolveColour = (page, expression) => page.evaluate(expr => {
  const probe = document.createElement('div');
  probe.style.color = expr;
  document.body.append(probe);
  const out = getComputedStyle(probe).color;
  probe.remove();
  return out;
}, expression);

// Scrolls an element into view and waits for every picture inside it to finish loading.
async function settlePictures(locator) {
  await locator.scrollIntoViewIfNeeded();
  await locator.evaluate(async root => {
    const imgs = [...root.querySelectorAll('img')];
    imgs.forEach(i => { i.loading = 'eager'; });
    await Promise.all(imgs.map(i => i.complete ? null : new Promise(r => { i.addEventListener('load', r, { once: true }); i.addEventListener('error', r, { once: true }); setTimeout(r, 3000); })));
  });
}

const pictures = locator => locator.evaluate(root => [...root.querySelectorAll('img')].map(i => ({
  src: new URL(i.currentSrc || i.src, location.href).pathname, loaded: i.complete && i.naturalWidth > 0, broken: i.complete && i.naturalWidth === 0,
  width: i.getBoundingClientRect().width, top: i.getBoundingClientRect().top, bottom: i.getBoundingClientRect().bottom,
})));

const until = async (check, ms = 4000, every = 50) => {
  const end = Date.now() + ms;
  let last;
  while (Date.now() < end) { last = await check(); if (last) return last; await new Promise(r => setTimeout(r, every)); }
  return check();
};

module.exports = {
  REPO, EXAMPLE, UUID, chromium, scryfallId, RICH_LEDGER,
  startDeckServer, openDeck, withDeck, arenaList, rgb, hsl, resolveColour, settlePictures, pictures, until,
};
