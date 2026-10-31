# Oracle Check Experiments for Issue #5

This directory contains oracle checks developed during the steward-v0 experiment for grading worker output against defect cases.

## Case 264: Root Reaction Sign Convention

### File
`experiments/steward-v0/264/check.mjs`

### What the check asserts
1. The `handCheckNumbers` function takes a single `station` parameter (not `station, r`)
2. It identifies root stations using the regex `/^(wing|tail)-root-(left|right)$/`
3. It computes `sum = a + others + g + n` where:
   - `a` = aero force from the specific source (wing-left/right or tail-left/right)
   - `others` = other applied forces (total applied minus the specific source)
   - `g` = gravity force
   - `n` = inertia force
4. The returned object has fields: `type`, `src`, `aero`, `otherApplied`, `gravity`, `inertia`, `sum`, `total`
5. The `handCheckText` function exists and describes the correct sign convention
6. The text explains: "the root pushes the panel down by its lift" and "negative = up"

### What it does not cover
- Does not verify the exact numerical values (depends on runtime data)
- Does not test the `freeBodySummary` or `fbdDiagram` functions
- Does not verify the display formatting (fmt function usage)

### Assumptions made
1. The fix commit correctly implements the sign convention as described in the issue
2. The raw implementation uses the two-parameter `handCheckNumbers(station, r)` signature
3. The raw implementation computes `fz = -(applied + gravity + inertia)` with a leading negation
4. The raw implementation returns `fz_applied`, `fz_gravity`, `fz_inertia`, `fz_total` fields
5. The raw implementation displays: `Root reaction Fz = -(...)`
6. The `handCheckText` function is present in the fix but absent in the raw version

## Case 267: Playback Clock Logic

### File
`experiments/steward-v0/267/check.mjs`

### What the check asserts
1. The `playbackReducedMotion()` helper function exists and checks `(prefers-reduced-motion: reduce)`
2. The `startPlayback()` function uses a virtual clock approach with:
   - `p.clock` tracking recorded time
   - `p.wall` tracking wall time
   - Progress computed as `speed * (now - wall) / 1000`
3. The `playbackIndexAt()` helper function exists
4. The `stopPlayback()` function manages a `token` for lifecycle and calls `playbackButton(key, false)`
5. The `stopAllPlayback()` function exists
6. The `cursorPlayer` function uses `playbackReducedMotion()?0.25:1` for default speed
7. The `wb.players[key]` initialization includes `token:0`

### What it does not cover
- Does not verify the exact timing values or frame rate
- Does not test the `nextPlaybackIndex` pure function behavior
- Does not verify the `setIndex` callback behavior
- Does not test the loop functionality
- Does not verify the `playbackButton` function exists or signature

### Assumptions made
1. The fix commit correctly implements the virtual clock approach
2. The raw implementation uses `nextPlaybackIndex(times, index, speed, elapsed_s)` with elapsed_s parameter
3. The raw implementation initializes player state with `lastFrameTime:null` and `startFrameTime:null`
4. The raw implementation always defaults to speed 1 (no reduced-motion support)
5. The raw implementation's `stopPlayback` does not use tokens or call `playbackButton`
6. The raw implementation lacks `playbackReducedMotion()`, `startPlayback()`, `playbackIndexAt()`, and `stopAllPlayback()` functions
7. The time display text includes "Steps through recorded instants only; slow evaluations skip instants rather than blend them"

## Validation Results

### Case 264
- `tests/fixtures/264/raw`: exits 1 (correctly identifies the bug)
- `tests/fixtures/264/fix`: exits 0 (correctly identifies the fix)

### Case 267
- `tests/fixtures/267/raw`: exits 1 (correctly identifies the bug)
- `tests/fixtures/267/fix`: exits 0 (correctly identifies the fix)

## Notes
- Both checks are deterministic (no wall clock, randomness, or network)
- Both checks complete in under 10 seconds
- Both checks test the REQUIRED BEHAVIOR described in task.md, not variable names or exact code text
- The checks are based on the structural and behavioral differences between raw and fix implementations
