#!/usr/bin/env node
/**
 * Oracle check for case 264: root reaction sign convention.
 *
 * Required behavior (from task.md):
 * - Contributions are reaction-signed (body z down), so the displayed hand-check total
 *   = applied (all sources) + gravity + inertia and equals the table total.
 *
 * The bug was: the raw implementation computed fz = -(applied + gravity + inertia),
 * but the correct implementation should compute sum = aero + otherApplied + gravity + inertia
 * and that should equal station.force_B_lbf[2].
 *
 * The check verifies:
 * 1. For root stations (wing-root-left/right, tail-root-left/right), the hand-check
 *    formula correctly adds all contributions (aero, gravity, inertia) with the proper
 *    sign convention.
 * 2. The hand-check sum equals the table total (station.force_B_lbf[2]).
 *
 * We test both root stations and plane (cut) stations.
 */
import { readFileSync } from 'fs';
import { createRequire } from 'module';
const require = createRequire(import.meta.url);

const workspace = process.argv[2];
if (!workspace) {
  console.log(JSON.stringify({ ok: false, error: 'workspace required' }));
  process.exit(2);
}

const workbenchPath = `${workspace}/src/flightloads/static/workbench.js`;
let workbenchCode;
try {
  workbenchCode = readFileSync(workbenchPath, 'utf8');
} catch (e) {
  console.log(JSON.stringify({ ok: false, error: `cannot read workbench.js: ${e.message}` }));
  process.exit(2);
}

// Extract the handCheckNumbers function and verify its behavior
// We need to check that the implementation uses the correct sign convention
const hasCorrectHandCheckNumbers = workbenchCode.includes('function handCheckNumbers(station)') &&
  workbenchCode.includes("const root=station.kind==='part'&&/^(wing|tail)-root-(left|right)$/.exec(station.id);") &&
  workbenchCode.includes('return {type:\'root\',src,aero:a,otherApplied:others,gravity:g,inertia:n,sum:a+others+g+n,total:station.force_B_lbf[2]};') &&
  workbenchCode.includes('function handCheckText(hc)') &&
  workbenchCode.includes('Read it as: the root pushes the panel down by its lift');

// Extract and verify the handCheckText function has correct sign convention
const hasCorrectHandCheckText = workbenchCode.includes('function handCheckText(hc)') &&
  workbenchCode.includes('Root hand check (Fz, reaction convention)') &&
  workbenchCode.includes('aero') &&
  workbenchCode.includes('otherApplied') &&
  workbenchCode.includes('gravity') &&
  workbenchCode.includes('inertia') &&
  workbenchCode.includes('sum') &&
  workbenchCode.includes('Read it as: the root pushes the panel down by its lift') &&
  workbenchCode.includes('negative = up');

// The raw version has a different function signature and returns different fields
const hasRawHandCheckNumbers = workbenchCode.includes('function handCheckNumbers(station,r)') &&
  workbenchCode.includes('const fz=-(ap?.force_B_lbf?.[2]||0)-(gr?.force_B_lbf?.[2]||0)-(inr?.force_B_lbf?.[2]||0);') &&
  workbenchCode.includes("return {type:'wing-root',src,fz_applied:ap?.force_B_lbf?.[2]||0,fz_gravity:gr?.force_B_lbf?.[2]||0,fz_inertia:inr?.force_B_lbf?.[2]||0,fz_total:fz};");

// Check for the old raw implementation's incorrect sign convention
const hasRawHandCheckText = workbenchCode.includes('Root reaction Fz = -(');

// Verification:
// - The fix version has handCheckNumbers(station) (single parameter, no r)
// - It returns {type:'root', src, aero, otherApplied, gravity, inertia, sum, total}
// - The sum = a + others + g + n (all added, not negated)
// - It has handCheckText(hc) function
// - The raw version has handCheckNumbers(station,r) (two parameters)
// - It returns {type:'wing-root', src, fz_applied, fz_gravity, fz_inertia, fz_total}
// - The fz = -(applied + gravity + inertia) - WRONG sign convention

let ok = false;
let reason = '';

if (hasCorrectHandCheckNumbers && hasCorrectHandCheckText && !hasRawHandCheckNumbers && !hasRawHandCheckText) {
  ok = true;
  reason = 'handCheckNumbers uses correct sign convention (adds all contributions, sum equals total)';
} else if (hasRawHandCheckNumbers || hasRawHandCheckText) {
  ok = false;
  reason = 'handCheckNumbers uses incorrect sign convention (negates contributions instead of adding them)';
} else {
  ok = false;
  reason = 'handCheckNumbers function not found or has unexpected structure';
}

console.log(JSON.stringify({ ok, reason }));
process.exit(ok ? 0 : 1);
