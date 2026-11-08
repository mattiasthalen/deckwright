// Applies a case's deterministic graders (regex, tool_used, file_exists) to a kept run's trace and page,
// without a new run: for checking a grader change against real traces, and a hand-edited copy of one.
//
//   node evals/tools/grade-trace.mjs evals/<case>/graders <trace.jsonl> [<deck.html>]
//
// The runner is a Bun binary, so its regexes run on JavaScriptCore, which gives up on a match that
// backtracks too much and reports no match, where V8 (node) finds one. Run from node, this script
// runs itself again under `bun` (on PATH, or $BUN) and prints Bun's verdicts, which are the runner's,
// marking `ENGINES DIFFER` where V8's differ: such a grader is past JavaScriptCore's limit and must be
// made cheaper. Without bun it prints V8's verdicts and says so on stderr.
//
// It reads graders as the runner was seen to on 2026-11-07, which its documentation does not state:
// a regex is a JavaScript RegExp with only the grader's flags (no m, so ^ is the start of the trace);
// a trace regex sees the whole trace.jsonl as one string; tool_used counts the tool_use blocks of the
// trace's assistant lines whose input, serialised as compact JSON, matches input_match (min 1, max
// unbounded by default); last_message is the result line's text. llm graders are listed, not judged.
// The frontmatter reader takes only this suite's one-line forms; a pattern is single-quoted YAML.
import { spawnSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const [graderDir, tracePath, pagePath] = process.argv.slice(2);
if (!graderDir || !tracePath) {
  console.error('usage: node grade-trace.mjs <graders dir> <trace.jsonl> [<deck.html>]');
  process.exit(2);
}
const trace = fs.readFileSync(tracePath, 'utf8');
const page = pagePath && fs.existsSync(pagePath) ? fs.readFileSync(pagePath, 'utf8') : null;

function frontmatter(source) {
  const fields = {};
  for (const line of source.match(/^---\n([\s\S]*?)\n---/)[1].split('\n')) {
    if (!line.trim() || line.startsWith('#')) continue;
    const colon = line.indexOf(':');
    const key = line.slice(0, colon).trim();
    let value = line.slice(colon + 1).trim();
    if (value.startsWith("'") && value.endsWith("'")) value = value.slice(1, -1).replace(/''/g, "'");
    else if (value.startsWith('{')) value = { path: value.match(/path:\s*([^ }]+)/)[1] };
    fields[key] = value;
  }
  return fields;
}

const toolCalls = [];
let lastMessage = '';
for (const line of trace.split('\n')) {
  let record;
  try { record = JSON.parse(line); } catch { continue; }
  if (record.type === 'assistant') {
    for (const block of record.message.content || []) if (block.type === 'tool_use') toolCalls.push(block);
  }
  if (record.type === 'result') lastMessage = record.result ?? '';
}

const results = [];
for (const file of fs.readdirSync(graderDir).filter((f) => f.endsWith('.md')).sort()) {
  const grader = frontmatter(fs.readFileSync(path.join(graderDir, file), 'utf8'));
  const name = file.replace(/\.md$/, '');
  let passed;
  let evidence;
  if (grader.type === 'regex') {
    const target = grader.target === 'trace' ? trace
      : grader.target === 'last_message' ? lastMessage
      : grader.target.path === 'deck.html' ? page : null;
    if (target === null) { results.push(`skip  ${name}  (no ${grader.target.path})`); continue; }
    const match = new RegExp(grader.pattern, grader.flags || '').exec(target);
    passed = grader.match === 'not_contains' ? !match : Boolean(match);
    evidence = match ? `matched …${JSON.stringify(match[0].slice(-120))}` : 'no match';
  } else if (grader.type === 'tool_used') {
    const inputMatch = grader.input_match ? new RegExp(grader.input_match) : null;
    const count = toolCalls.filter((call) => call.name === grader.tool
      && (!inputMatch || inputMatch.test(JSON.stringify(call.input)))).length;
    const min = grader.min === undefined ? 1 : Number(grader.min);
    const max = grader.max === undefined ? Infinity : Number(grader.max);
    passed = count >= min && count <= max;
    evidence = `${count} call(s)`;
  } else if (grader.type === 'file_exists') {
    if (grader.path !== 'deck.html' && grader.path !== '*.html') { results.push(`skip  ${name}`); continue; }
    passed = page !== null;
    evidence = page !== null ? 'page given' : 'no page given';
  } else {
    results.push(`llm   ${name}`);
    continue;
  }
  results.push(`${passed ? 'pass' : 'FAIL'}  ${name}  ${evidence}`);
}

let shown = results;
if (typeof Bun === 'undefined' && !process.env.GRADE_TRACE_CHILD) {
  const bun = spawnSync(process.env.BUN || 'bun', [fileURLToPath(import.meta.url), ...process.argv.slice(2)], {
    encoding: 'utf8', env: { ...process.env, GRADE_TRACE_CHILD: '1' }, maxBuffer: 1 << 26,
  });
  if (bun.error || bun.status > 1) {
    console.error('grade-trace: bun not found; these are V8\'s verdicts, which can pass a regex the runner fails');
  } else {
    const v8 = new Map(results.map((line) => [line.split(/\s+/)[1], line.split(/\s+/)[0]]));
    shown = bun.stdout.trimEnd().split('\n').map((line) => {
      const [verdict, name] = line.split(/\s+/);
      return v8.get(name) === verdict ? line : `${line}  ENGINES DIFFER: V8 says ${v8.get(name)}`;
    });
  }
}
for (const line of shown) console.log(line);
process.exit(shown.some((line) => line.startsWith('FAIL') || line.includes('ENGINES DIFFER')) ? 1 : 0);
