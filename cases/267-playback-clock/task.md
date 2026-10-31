Source: wcc118/flight-loads, issue #267 (UI), workbench.js recorded-time cursor playback.
The original dispatched packet is not retained in this repository; this case is graded on
behavior only. Required behavior: playback advances recorded time at speed x wall time and shows
the recorded tick at or after the playback clock; the reduced-motion preference sets the default
speed to 0.25x; pausing holds the tick. Drives the real cursorPlayer through its own play button
and speed select with a virtual clock.
