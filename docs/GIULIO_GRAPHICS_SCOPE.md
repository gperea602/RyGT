# Giulio Graphics Enhanced — scope and baseline audit (2026-11-28)

Target: GT7 PS4 1.71 CUSA24769. Work only in the independent feat/giulio-graphics-enhanced branches of gperea602/RyGT and gperea602/shadGT. Extend the existing renderer and launcher; do not recreate existing settings, algorithms or menus. Preserve original user choices and baseline functionality.

## Existing functionality: reuse, do not reimplement

Audit sources: RyGT loader/Gt7Pages.cs, loader/AdvancedPage.cs; shadGT src/video_core/rygt_switches.cpp and texture_cache/sampler.cpp. Recheck against the exact renderer pin and upstream changes before each new feature.

- FSR 1, FSR 3.1, DLSS (including GT7 temporal path), DLAA renderer mode, sharpening RCAS, existing quality/output settings and texture MIP-bias controls.
- AMD FSR 3.1 and NVIDIA DLSS frame generation; NVIDIA multi-frame options subject to GPU/SDK support. Do not create another frame generator.
- HDR output, peak and paper-white controls.
- PS4 Pro modes including 3200x1800 checkerboard, 4K UI, motion blur, 60 fps replays/photo/garage, 1.3x LOD.
- Existing wet-road reflections. Do not create a second toggle for the original pass.
- Existing experimental ENV_SCALE / ENV_SET, UPSCALE_RATIO, FSR_UPSCALER (FSR 4/XeSS), and temporal FSR flags. Availability does not establish GT7 compatibility; some explicitly target GT Sport. Validate and reuse before extending.
- Shader preparation, caches, renderer diagnostics: reuse and preserve. No parallel implementation.

## Additive visual priorities

1. Audit actual internal render targets and scaling path; pursue true scene-resolution enhancement beyond existing checkerboard/output scaling only where not already supported.
2. GFX-001: existing new optional anisotropic quality floor (not MIP bias); verify native recorder sampler path coverage, actual visual benefit and absence of another override in upstream before retaining. No effect by default. Remove if duplicated upstream.
3. Original/local texture replacement infrastructure with content IDs and resource lifetime checks, excluding dynamic render targets, depth, HUD and incompatible texture formats. No redistribution of proprietary assets.
4. Extend existing environment and shadow controls only for genuinely new validated visual capabilities: resolution/quality, not duplicate LOD sliders.
5. Improve original reflection probe/mirror/wet-road quality beyond stock; optional hybrid hardware ray tracing research contingent on scene geometry/material extraction, device support and profiling.
6. Weather visual rendering (clouds, fog, spray, rain shading), never simulation, wetness, traction or progression.
7. Put only new features into the existing launcher UI or switch catalog; no separate duplicate graphics menu.

Each change: inspect upstream and exact pin, document gap, default off unless already baseline behavior, ensure rollback, isolate shader cache if shader variants differ, run tests and CI, and request A/B screenshots/frametimes/VRAM/compilation data when actual gameplay validation is needed. No claims of validated game performance without real measurements. No automatic enablement or merging into the core or AI branches.
