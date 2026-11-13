// Playwright is pinned to one exact version, the one installed and the one locked.
//
// Run: node --test tests/*.test.cjs

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const REPO = path.resolve(__dirname, '..');

const readJson = name => {
  const file = path.join(REPO, name);
  assert.ok(fs.existsSync(file), `no ${name} at the repo root`);
  return JSON.parse(fs.readFileSync(file, 'utf8'));
};

test('Playwright is pinned to the exact version installed and locked', () => {
  const pinned = readJson('package.json').devDependencies?.playwright;
  assert.match(String(pinned), /^\d+\.\d+\.\d+$/, `package.json asks for Playwright ${pinned}, not one exact version`);
  const installed = require('playwright/package.json').version;
  assert.equal(installed, pinned, `Playwright ${installed} is installed, package.json pins ${pinned}`);
  const locked = readJson('package-lock.json').packages?.['node_modules/playwright']?.version;
  assert.equal(locked, pinned, `package-lock.json locks Playwright ${locked}, package.json pins ${pinned}`);
});

// The name is put together here so that this file does not hold it.
const REAL_TIME_WAIT = ['waitFor', 'Timeout'].join('');

test(`P12: No file under tests/ calls ${REAL_TIME_WAIT}: the scene tests drive the page's clock`, () => {
  const files = fs.readdirSync(path.join(REPO, 'tests'), { recursive: true, withFileTypes: true })
    .filter(f => f.isFile()).map(f => path.relative(REPO, path.join(f.parentPath, f.name)));
  assert.ok(files.length > 1, 'no test files were read, so this test proves nothing');
  const waiting = files.filter(f => fs.readFileSync(path.join(REPO, f), 'utf8').includes(REAL_TIME_WAIT));
  assert.deepEqual(waiting, [], `${REAL_TIME_WAIT} is called in ${waiting.join(', ')}`);
});
