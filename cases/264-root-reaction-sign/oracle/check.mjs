// Oracle for flight-loads #264 (UI): the root hand check must reproduce the table total.
// Runtime: node-vm. Usage: node check.mjs WORKSPACE_DIR   (reads src/flightloads/static/workbench.js)
// Prints one JSON result on stdout; exit 0 = pass, 1 = fail, 2 = oracle could not run.
//
// Convention (flight-loads docs, #264 fix 2d7a513): station contributions are already reaction-signed,
// body z down, so the table total Fz = applied(all sources) + gravity + inertia, component by component.
// The check is behavioral and name-agnostic: some number the hand check exposes must (a) equal the
// table total on a balanced station and (b) rise by exactly +delta when any single contribution rises
// by delta with the table total held fixed. A wrong sign or a dropped term breaks (b) for every output.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const TOL = 1e-9, DELTA = 1.0;
const workspace = process.argv[2];
const out = (r, code) => { console.log(JSON.stringify(r)); process.exit(code); };
if (!workspace) out({ ok: false, error: 'usage: check.mjs WORKSPACE' }, 2);

const file = path.join(workspace, 'src/flightloads/static/workbench.js');
let code;
try { code = fs.readFileSync(file, 'utf8'); } catch (e) { out({ ok: false, error: `cannot read ${file}` }, 2); }

// Universal DOM stub: any property is a callable/chainable stub; network calls never resolve.
const stub = () => new Proxy(function () {}, {
  get: (t, k) => (k === Symbol.toPrimitive ? () => '' : k === 'then' ? undefined : stub()),
  apply: () => stub(), construct: () => stub(), set: () => true,
});
const sandbox = {
  document: stub(), window: stub(), localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  fetch: () => new Promise(() => {}), console: { log() {}, error() {}, warn() {} },
  setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {},
  requestAnimationFrame: () => 0, Math, JSON, Object, Array, Number, String, Date, Promise, Error, Map, Set,
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
try { new vm.Script(code, { filename: 'workbench.js' }).runInContext(sandbox, { timeout: 5000 }); }
catch (e) { out({ ok: false, error: 'workbench.js failed to load: ' + e.message }, 2); }
const hand = sandbox.handCheckNumbers;
if (typeof hand !== 'function') out({ ok: false, error: 'handCheckNumbers not defined' }, 2);

const v3 = z => [0, 0, z];
// Balanced synthetic wing-root station. Distinct, nonzero components so no coincidences.
const base = { wing: -12.0, other: -0.5, gravity: 3.25, inertia: 1.0 };
const total = base.wing + base.other + base.gravity + base.inertia; // -8.25
const build = c => ({
  id: 'wing-root-left', kind: 'part', number: 9, title: 'Wing root (left)',
  force_B_lbf: v3(total),                                   // table total held fixed
  moment_B_in_lbf: [0, 0, 0],
  contributions: {
    applied: { force_B_lbf: v3(c.wing + c.other), moment_B_in_lbf: [0, 0, 0] },
    applied_by_source: {
      'wing-left': { force_B_lbf: v3(c.wing), moment_B_in_lbf: [0, 0, 0] },
      propulsion: { force_B_lbf: v3(c.other), moment_B_in_lbf: [0, 0, 0] },
    },
    gravity: { force_B_lbf: v3(c.gravity), moment_B_in_lbf: [0, 0, 0] },
    inertia: { force_B_lbf: v3(c.inertia), moment_B_in_lbf: [0, 0, 0] },
    retained: { masses: [] },
  },
});
const leaves = (o, p = '', acc = {}) => {
  if (typeof o === 'number' && Number.isFinite(o)) acc[p] = o;
  else if (o && typeof o === 'object') for (const [k, v] of Object.entries(o)) leaves(v, p ? `${p}.${k}` : k, acc);
  return acc;
};
const run = c => { try { return leaves(hand(build(c), { geometry: {} })); } catch (e) { return { __error: String(e.message) }; } };

const b = run(base);
if (b.__error !== undefined) out({ ok: false, error: 'handCheckNumbers threw: ' + b.__error }, 2);
const sens = {};
for (const comp of Object.keys(base)) {
  const p = run({ ...base, [comp]: base[comp] + DELTA });
  for (const k of Object.keys(b)) (sens[k] ??= {})[comp] = (p[k] ?? NaN) - b[k];
}
const qualifies = k => Math.abs(b[k] - total) < TOL &&
  Object.keys(base).every(c => Math.abs(sens[k][c] / DELTA - 1) < TOL);
const winners = Object.keys(b).filter(qualifies);
const ok = winners.length > 0;
out({
  ok, table_total: total, computed_total_paths: winners,
  reason: ok ? 'a displayed value reproduces the table total with +1 sensitivity to every contribution'
             : 'no displayed value equals the table total with +1 sensitivity to applied, other applied, gravity and inertia',
  outputs: Object.fromEntries(Object.keys(b).map(k => [k, { value: b[k], sensitivity: sens[k] }])),
}, ok ? 0 : 1);
