# GT7 shader discovery experiment (FEAT-GT7-901)

Goal: discover shaders and pipeline state before the first human race. The
existing shadGT diagnostics input bridge supports a file of pad actions and
screenshots. Regaliant's internal level automation is game-specific; no
equivalent GT7 level loader or complete route has yet been verified.

The diagnostic route runner uses fresh log events to advance, stops on missing
events and records newly observed manifest program/variant identities, graphics
keys and compute recipe files. Counts are not compilation success or coverage
of all possible game states. A route completion is not a "shaders ready" marker.

First integration test: use an independently isolated offline GT7 installation
and diagnostics renderer; verify the runtime's save, trophy, data, input and
network isolation before starting it. Set RYTY_TEST_SCRIPT_FILE to a new empty
command file in that sandbox and enable SHADGT_MANIFEST_RECORD=1. Record the
active cache store and log path. The sandbox marker is an explicit operator
assertion, not a sandboxing mechanism. Do not run on a normal player installation.
The runner does not launch the game, copy user saves, inject host input or
decrypt archives. It currently allows only momentary pad presses and screenshots.

Build the first route from real observations: boot/title, menu entry, track
selection, vehicle selection, pre-race screen, loading confirmation, race and
return. Use verified game-state log events, not guessed screen names or just
input acknowledgments. Capture screenshots for states with no usable signal.
Then add automatic state recognition, steering/AI or replay traversal, camera,
weather, time-of-day and material variants. Track newly discovered identities per
route, measure warm replays separately, and record remaining cold pipeline builds
and visual misses during a held-out race. Do not claim exhaustive coverage until
a defensible independent inventory exists.

The route runner is deliberately not wired to the launcher yet. Need explicit
save/network isolation and a validated diagnostics build before live execution.
