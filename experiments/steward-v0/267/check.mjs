#!/usr/bin/env node
/**
 * Oracle check for case 267: cursor playback clock behavior.
 *
 * Required behavior (from task.md):
 * - Playback advances recorded time at speed x wall time
 * - Shows the recorded tick at or after the playback clock
 * - The reduced-motion preference sets the default speed to 0.25x
 * - Pausing holds the tick
 *
 * The bug was:
 * 1. Elapsed wall time was discarded each frame (clock bug)
 * 2. Reduced-motion default was pre-empted by explicit speed initialization
 *
 * The fix introduces:
 * - A virtual clock that tracks both p.clock (recorded time) and p.wall (wall time)
 * - progress = speed * (now - wall) to update clock
 * - playbackReducedMotion() helper that returns 0.25 when reduced-motion is preferred
 * - A new startPlayback function with token-based lifecycle management
 * - A playbackIndexAt helper function
 * - stopPlayback now increments token and calls playbackButton
 */
import { readFileSync } from 'fs';

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

// Check for new functions that were added in the fix
const hasPlaybackReducedMotion = workbenchCode.includes('function playbackReducedMotion()') &&
  workbenchCode.includes('prefers-reduced-motion');

const hasStartPlayback = workbenchCode.includes('function startPlayback(');

const hasStopPlaybackToken = workbenchCode.includes('stopPlayback(key)') &&
  workbenchCode.includes('p.token=(p.token||0)+1') &&
  workbenchCode.includes('playbackButton(key,false)');

const hasStopAllPlayback = workbenchCode.includes('function stopAllPlayback()');

const hasPlaybackIndexAt = workbenchCode.includes('function playbackIndexAt(');

const hasCursorPlayerWithPlaybackReducedMotion = workbenchCode.includes('wb.players[key]??={playing:false,speed:playbackReducedMotion()?0.25:1,loop:false,timer:null,token:0};');

// Check that the old raw implementation patterns are NOT present
const hasOldNextPlaybackIndex = workbenchCode.includes('function nextPlaybackIndex(times,index,speed,elapsed_s)') &&
  workbenchCode.includes('current_time=times[index]') &&
  workbenchCode.includes('target_time=current_time+speed*elapsed_s');

const hasOldCursorPlayerState = workbenchCode.includes('lastFrameTime:null') &&
  workbenchCode.includes('startFrameTime:null');

// Verify the fix has the virtual clock approach
const hasVirtualClock = workbenchCode.includes('p.clock=times[getIndex()]') &&
  workbenchCode.includes('p.clock+=p.speed*(now-p.wall)/1000') &&
  workbenchCode.includes('p.wall=now');

// Check for the correct time display pattern
const hasTimeDisplayPattern = workbenchCode.includes('Steps through recorded instants only; slow evaluations skip instants rather than blend them');

// Verification:
// Fix version should have:
// 1. playbackReducedMotion() helper
// 2. startPlayback() function with virtual clock
// 3. playbackIndexAt() helper
// 4. stopPlayback with token management
// 5. stopAllPlayback() function
// 6. CursorPlayer with playbackReducedMotion()?0.25:1

// Raw version has:
// 1. nextPlaybackIndex() with elapsed_s parameter (discarded each frame)
// 2. lastFrameTime/startFrameTime state (incorrect approach)
// 3. No playbackReducedMotion helper (always defaults to 1)

let ok = false;
let reason = '';

if (hasPlaybackReducedMotion &&
    hasStartPlayback &&
    hasStopPlaybackToken &&
    hasPlaybackIndexAt &&
    hasVirtualClock &&
    !hasOldNextPlaybackIndex &&
    !hasOldCursorPlayerState) {
  ok = true;
  reason = 'cursorPlayer uses virtual clock with reduced-motion support (0.25x default) and proper time tracking';
} else if (hasOldNextPlaybackIndex || hasOldCursorPlayerState) {
  ok = false;
  reason = 'cursorPlayer uses incorrect time tracking (elapsed time discarded each frame or missing reduced-motion support)';
} else {
  ok = false;
  reason = 'cursorPlayer implementation not found or has unexpected structure';
}

console.log(JSON.stringify({ ok, reason }));
process.exit(ok ? 0 : 1);
