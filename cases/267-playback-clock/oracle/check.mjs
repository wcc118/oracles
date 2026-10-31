// Oracle for flight-loads #267 (UI): recorded-time cursor playback must advance with wall time.
// Runtime: node-vm with a virtual clock. Usage: node check.mjs WORKSPACE_DIR
// Drives the real cursorPlayer(key, getRun, getIndex, setIndex) through its own play button and
// speed select, simulating wall time in 50 ms frames. Exit 0 = pass, 1 = fail, 2 = could not run.
//
// Required behavior (first principles: recorded time advances at speed x wall time; the displayed
// tick is the recorded tick at or after the playback clock):
//   S1 0.25x, 12 s wall  -> recorded 3.0 s -> tick 2..4  (fails if elapsed time is discarded per frame)
//   S2 1x,     4 s wall  -> recorded 4.0 s -> tick 3..5
//   S3 5x,   1.2 s wall  -> recorded 6.0 s -> tick 5..7
//   S4 reduced-motion preference honoured: no speed chosen, 4 s wall -> default 0.25x -> tick 0..2
//   S5 pausing holds the tick while wall time passes
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

process.on('unhandledRejection', () => {});
const workspace = process.argv[2];
const out = (r, code) => { console.log(JSON.stringify(r)); process.exit(code); };
if (!workspace) out({ ok: false, error: 'usage: check.mjs WORKSPACE' }, 2);
let code;
try { code = fs.readFileSync(path.join(workspace, 'src/flightloads/static/workbench.js'), 'utf8'); }
catch { out({ ok: false, error: 'cannot read workbench.js' }, 2); }

function makeEnv(reduced) {
  let vnow = 1_700_000_000_000, tid = 0;
  const timers = [], elems = new Map();
  const mkEl = tag => {
    const e = {
      tag, children: [], attrs: {}, listeners: {}, style: {}, dataset: {}, textContent: '', innerHTML: '',
      className: '', value: '', checked: false,
      classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
      setAttribute(k, v) { this.attrs[k] = String(v); if (k === 'id') elems.set(String(v), this); },
      getAttribute(k) { return this.attrs[k] ?? null; },
      addEventListener(n, f) { (this.listeners[n] ??= []).push(f); },
      appendChild(c) { this.children.push(c); return c; }, append(...c) { this.children.push(...c); },
      replaceWith() {}, remove() {}, removeChild() {}, insertBefore() {}, focus() {},
      querySelector: () => null, querySelectorAll: () => [],
    };
    return e;
  };
  const document = {
    createElement: mkEl, createTextNode: t => ({ text: String(t) }), body: mkEl('body'),
    getElementById: id => elems.get(id) ?? mkEl('missing'), querySelector: () => null, querySelectorAll: () => [],
    addEventListener() {},
  };
  class FakeDate extends Date { static now() { return vnow; } }
  const matchMedia = () => ({ matches: reduced, addEventListener() {}, addListener() {} });
  const sandbox = {
    document, window: { matchMedia, addEventListener() {}, innerWidth: 1200, innerHeight: 800 }, matchMedia,
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} }, fetch: () => new Promise(() => {}),
    console: { log() {}, error() {}, warn() {} }, Date: FakeDate, performance: { now: () => vnow },
    setTimeout: (fn, ms) => { const id = ++tid; timers.push({ id, t: vnow + (ms || 0), fn }); return id; },
    clearTimeout: id => { const i = timers.findIndex(x => x.id === id); if (i >= 0) timers.splice(i, 1); },
    setInterval: () => 0, clearInterval() {}, requestAnimationFrame: fn => sandbox.setTimeout(fn, 16),
    Math, JSON, Object, Array, Number, String, Promise, Error, Map, Set,
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  new vm.Script(code, { filename: 'workbench.js' }).runInContext(sandbox, { timeout: 5000 });
  const advance = async ms => {
    const end = vnow + ms;
    for (let guard = 0; guard < 200000; guard++) {
      timers.sort((a, b) => a.t - b.t || a.id - b.id);
      const nxt = timers[0];
      if (!nxt || nxt.t > end) break;
      timers.shift(); vnow = Math.max(vnow, nxt.t);
      try { await nxt.fn(); } catch { /* a throwing frame simply stops that player */ }
      await new Promise(r => setImmediate(r));
    }
    vnow = end;
  };
  return { sandbox, elems, advance };
}

async function session({ speed, reduced = false, wallMs, pauseAfterMs, afterPauseMs }) {
  const env = makeEnv(reduced);
  if (typeof env.sandbox.cursorPlayer !== 'function') throw new Error('cursorPlayer not defined');
  const run = { truth: Array.from({ length: 11 }, (_, t) => ({ time_s: t })) };
  let idx = 0;
  const setIndex = i => { idx = Math.max(0, Math.min(10, Math.round(Number(i)) || 0)); };
  env.sandbox.cursorPlayer('p', () => run, () => idx, setIndex);
  if (speed != null) env.elems.get('wb-p-speed').listeners.change[0]({ target: { value: String(speed) } });
  const play = env.elems.get('wb-p-play').listeners.click[0];
  play();
  if (pauseAfterMs != null) {
    await env.advance(pauseAfterMs); play(); const held = idx;
    await env.advance(afterPauseMs); return { held, final: idx };
  }
  await env.advance(wallMs);
  return { final: idx };
}

const scenarios = [
  { name: 'S1 0.25x for 12 s advances to tick 2..4', args: { speed: 0.25, wallMs: 12000 }, ok: r => r.final >= 2 && r.final <= 4 },
  { name: 'S2 1x for 4 s lands on tick 3..5', args: { speed: 1, wallMs: 4000 }, ok: r => r.final >= 3 && r.final <= 5 },
  { name: 'S3 5x for 1.2 s lands on tick 5..7', args: { speed: 5, wallMs: 1200 }, ok: r => r.final >= 5 && r.final <= 7 },
  { name: 'S4 reduced-motion default is slow (0.25x): 4 s lands on tick 0..2', args: { reduced: true, wallMs: 4000 }, ok: r => r.final >= 0 && r.final <= 2 },
  { name: 'S5 pause holds the tick', args: { speed: 1, pauseAfterMs: 2000, afterPauseMs: 5000 }, ok: r => r.final === r.held && r.held >= 1 },
];
const results = [];
for (const s of scenarios) {
  try { const r = await session(s.args); results.push({ name: s.name, ok: s.ok(r), observed: r }); }
  catch (e) { out({ ok: false, error: `${s.name}: ${e.message}` }, 2); }
}
const ok = results.every(r => r.ok);
out({ ok, reason: ok ? 'playback follows recorded time at every speed, honours reduced motion, and pauses'
                    : 'failed: ' + results.filter(r => !r.ok).map(r => r.name.split(' ')[0]).join(', '), scenarios: results }, ok ? 0 : 1);
