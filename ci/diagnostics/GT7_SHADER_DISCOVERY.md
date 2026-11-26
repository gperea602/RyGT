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

## Filesystem preflight (FEAT-GT7-903)

The runtime derives save migration roots from the executable directory
(SaveLayoutStart.cpp) and guest paths from the working directory (General.cpp).
The renderer's portable cache also depends on the user directory
(path_util.cpp). Merely changing the working directory is insufficient.

Use an independent physical copy of the installation, not junctions or hardlinks.
The new gt7_preparation_preflight.py checks separate roots, required paths,
linked files, App0 layer configuration and explicit log paths. Run it under
the same environment planned for the diagnostic process. It does not start the
game or create the operator assertion marker. A pass does not establish OS-level
isolation, exclusive execution, safe input routing or offline network behavior;
those still require separate live checks before a real session.

## Experimental build (FEAT-RT-901)

This branch pins gperea602/shadGT at 99062fa02da4e308903c3379117dddf1d32d9825. The branch-local
Diagnostics workflow builds both personal forks, tests Python controls, and
uploads checked ZIPs plus discovery scripts as Actions artifacts. It never
calls the upstream package workflow or registry. The workflow is restricted to
this fork and branch. This is an unsigned diagnostics build for isolated tests,
not a completed preparation feature or a release. Game data is not included.

## Passive discovery survey (FEAT-GT7-904)

Before attempting a route, use gt7_discovery_survey.py beside
gt7_shader_discovery.py to collect an append-only JSONL timeline in the
independent diagnostic copy. Supply --sandbox, --store, --log and --report
(new file outside shaders); --interval defaults to 2 seconds. Omit --duration
to observe until a report-name.jsonl.stop file is created, or Ctrl+C.
Run preflight and confirm runtime/network isolation first; the marker is not
a security boundary. The survey never sends input or launches the game.
It counts new cache identities seen at samples and distinct logged graphics
and compute compile attempts, excludes pre-existing log lines, and preserves
log byte offsets. Attempts are not confirmed successful compilations. A
resource created and removed between samples can be missed. Scene states
remain unclassified until confirmed in a real GT7 session. Log retention
and memory/disk costs of very long surveys still need live measurement.
