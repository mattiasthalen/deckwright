import js from '@eslint/js';
import html from 'eslint-plugin-html';
import globals from 'globals';

const PAGE = 'plugins/deckwright/skills/deckwright/page/index.html';

export default [
  { ignores: ['evals/runs/'] },
  js.configs.recommended,
  {
    files: ['tests/**/*.cjs'],
    // The functions handed to page.evaluate run in the page, so the browser's names are defined there too.
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
    rules: {
      // A test drops a key with ({ name, ...card }) => card, and lets an animation that cannot finish go.
      'no-unused-vars': ['error', { ignoreRestSiblings: true }],
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },
  {
    files: [PAGE],
    plugins: { html },
    languageOptions: { globals: globals.browser },
  },
];
