// Oracle for flight-loads #264 (UI): the root hand check must reproduce the table total.
// Runtime: node-vm. Usage: node check.mjs WORKSPACE_DIR   (reads src/flightloads/static/workbench.js)
// Prints one JSON result on stdout; exit 0 = pass, 1 = fail, 2 = oracle could not run.
//
// Convention (flight-loads docs, #264 fix 2d7a513): station contributions are already reaction-signed,
// body z down, so the table total Fz = applied(all sources) + gravity + inertia, component by component.
// Plane cuts (backend station_loads.py: force = -total_f, each contribution negated; level flight):
// reaction Fz at the cut = lift acting inside the free body - retained weight (L - W).
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
const leaves = (o, p = '', acc = {}) => {
  if (typeof o === 'number' && Number.isFinite(o)) acc[p] = o;
  else if (typeof o === 'string' && o.trim() !== '' && Number.isFinite(Number(o))) acc[p] = Number(o);
  else if (o && typeof o === 'object') for (const [k, v] of Object.entries(o)) leaves(v, p ? `${p}.${k}` : k, acc);
  return acc;
};
const zero = [0, 0, 0];
const mk = z => ({ force_B_lbf: v3(z), moment_B_in_lbf: zero });

// Root probe: balanced wing-root station; displayed total must be +1 sensitive to every contribution.
const rootBase = { wing: -12.0, other: -0.5, gravity: 3.25, inertia: 1.0 };
const rootTotal = rootBase.wing + rootBase.other + rootBase.gravity + rootBase.inertia; // -8.25
const rootBuild = c => ({
  id: 'wing-root-left', kind: 'part', number: 9, title: 'Wing root (left)', force_B_lbf: v3(rootTotal), moment_B_in_lbf: zero,
  contributions: {
    applied: mk(c.wing + c.other),
    applied_by_source: { 'wing-left': mk(c.wing), propulsion: mk(c.other) },
    gravity: mk(c.gravity), inertia: mk(c.inertia), retained: { masses: [] },
  },
});

// Plane probe: level-flight cut. Reaction convention: lift inside is +L, gravity is -W, table total is L - W.
const planeBase = { w1: 20.0, w2: 8.0, liftL: 12.5, liftR: 12.0 };
const planeTotal = planeBase.liftL + planeBase.liftR - (planeBase.w1 + planeBase.w2); // -3.5
const planeBuild = c => ({
  id: 'fuselage-aft-of-wing', kind: 'plane', number: 9, title: 'Cut', force_B_lbf: v3(planeTotal), moment_B_in_lbf: zero,
  contributions: {
    applied: mk(c.liftL + c.liftR),
    applied_by_source: { 'wing-left': mk(c.liftL), 'wing-right': mk(c.liftR) },
    gravity: mk(-(c.w1 + c.w2)), inertia: mk(0),
    retained: { masses: [{ id: 'a', name: 'a', weight_lbf: c.w1 }, { id: 'b', name: 'b', weight_lbf: c.w2 }] },
  },
});

function probe(name, build, base, target, expect) {
  const run = c => { try { return leaves(hand(build(c), { geometry: {} })); } catch (e) { return { __error: String(e.message) }; } };
  const b = run(base);
  if (b.__error !== undefined) return { name, ok: false, threw: b.__error };
  const sens = {};
  for (const comp of Object.keys(base)) {
    const p = run({ ...base, [comp]: base[comp] + DELTA });
    for (const k of Object.keys(b)) (sens[k] ??= {})[comp] = ((p[k] ?? NaN) - b[k]) / DELTA;
  }
  const qualifies = k => Math.abs(b[k] - target) < TOL && Object.entries(expect).every(([c, e]) => Math.abs(sens[k][c] - e) < TOL);
  const winners = Object.keys(b).filter(qualifies);
  return { name, ok: winners.length > 0, table_total: target, computed_total_paths: winners,
    outputs: Object.fromEntries(Object.keys(b).map(k => [k, { value: b[k], sensitivity: sens[k] }])) };
}

const results = [
  probe('root', rootBuild, rootBase, rootTotal, { wing: 1, other: 1, gravity: 1, inertia: 1 }),
  probe('plane', planeBuild, planeBase, planeTotal, { w1: -1, w2: -1, liftL: 1, liftR: 1 }),
];
const ok = results.every(r => r.ok);
out({
  ok,
  reason: ok ? 'root and plane hand checks reproduce the table total with the correct sign for every contribution'
             : 'failed: ' + results.filter(r => !r.ok).map(r => r.name).join(', ') +
               ' (no displayed value equals the table total with the required sensitivities)',
  probes: results,
}, ok ? 0 : 1);
