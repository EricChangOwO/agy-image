---
name: agy-image
description: "Generate new raster image assets with the local agy (Antigravity) CLI, especially while authoring osu! storyboards (.osb, .osu, or storybrew) when a planned background, sprite, texture, transition plate, or character shot does not already exist. Use when the user explicitly asks for agy/Antigravity image generation, says 'agy 生圖', or asks an agent to build an osu! storyboard that needs new visual assets. Inspect and reuse existing beatmap assets before generating. Do not use for editing or analysing an existing image, or when the user names another generator."
---

# agy Image Generation

Generate one required image at a time with the local agy CLI, collect its real
artifact, and verify the delivered file. Treat agy as the generator; do not
substitute another backend.

## Step 0: detect the runtime and path domain

Do this before inspecting assets or invoking the generator. Windows paths,
WSL paths, and native POSIX paths are different domains; never assume the
agent's Python runtime is the runtime where `agy` is installed.

On Windows PowerShell:

```powershell
python "{baseDir}\scripts\runtime_probe.py" `
  --path "{baseDir}" `
  --path "<absolute Windows output path>" `
  --path "<absolute Windows reference path>"
```

Inside WSL, Linux, or macOS:

```bash
python3 "{baseDir}/scripts/runtime_probe.py" \
  --path "{baseDir}" \
  --path "<absolute output path>" \
  --path "<absolute reference path>"
```

The command emits JSON. Stop if it exits nonzero, `status` is not `ready`, or
any `translated_paths[].error` is non-null. Then:

1. Invoke `agy_image.py` with `generation.launcher`.
2. Use each `translated_paths[].generation_path` for the script location,
   `--out`, `--ref`, and `--refs-dir`.
3. Always pass `--agy-bin <generation.agy_path>`; a non-interactive WSL Python
   process may not inherit the login-shell `PATH` containing `agy`.
4. Never use Windows `pathlib` to reinterpret `/mnt/c/...`, or POSIX `pathlib`
   to reinterpret `C:\...`.
5. Keep paths written into storyboard source relative to the beatmap. Runtime
   conversion applies only to filesystem operations.

Read [runtime-paths.md](references/runtime-paths.md) for the environment matrix
and path examples.

## Decide whether to generate

For osu! storyboard work, trigger this skill when the storyboard plan needs an
image that is absent from the beatmap folder. Before spending quota:

1. Inventory existing PNG/JPEG files and image paths already referenced by
   `.osb`, `.osu`, or storybrew source.
2. Reuse a suitable existing asset when possible.
3. Generate only genuinely missing visual content. Do not use agy for simple
   crop, resize, recolour, compositing, or background removal of an existing file.
4. Generate one image first and review it before requesting a series or animation.

Read [osu-storyboard.md](references/osu-storyboard.md) whenever the output will
be used in an osu! beatmap. It defines asset roles, dimensions, formats, paths,
and integration checks.

## Resolve the image specification

Establish these fields before invoking agy:

- purpose and scene;
- exact width and height in pixels;
- final format (`.jpg` for opaque backgrounds, `.png` for lossless or alpha assets);
- writable output path;
- optional reference images and a short subject anchor;
- whether center-crop is acceptable if agy drifts from the requested ratio.

When only a ratio is given, choose explicit pixels:

| Ratio | Default pixels |
|---|---:|
| 1:1 | 1024x1024 |
| 4:5 | 1024x1280 |
| 2:3 or 9:16 portrait | 1024x1536 |
| 16:9 | 1536x864 |

For storyboard-specific targets, use the sizes in
[osu-storyboard.md](references/osu-storyboard.md), not this generic table.

## Run the bundled wrapper

After Step 0, run the wrapper in the selected generation runtime. For example,
inside Linux or WSL, use the probed absolute `agy` path:

```bash
python3 {baseDir}/scripts/agy_image.py \
  --agy-bin /home/<user>/.local/bin/agy \
  --prompt "<scene, style, lighting, composition; no text or watermark>" \
  --width <W> --height <H> \
  --out "/absolute/output/path.ext" \
  --crop
```

On Windows when the probe selects WSL, use its selected distro, translated
paths, and `generation.agy_path`:

```powershell
$probe = (python "{baseDir}\scripts\runtime_probe.py" `
  --path "{baseDir}" --path '<absolute Windows output path>' | Out-String) |
  ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $probe.status -ne 'ready') { throw 'agy runtime is not ready' }
$skillPath = $probe.translated_paths[0].generation_path
$outPath = $probe.translated_paths[1].generation_path
wsl.exe -d $probe.generation.distro -- python3 "$skillPath/scripts/agy_image.py" `
  --agy-bin $probe.generation.agy_path `
  --prompt '<scene prompt>' --width <W> --height <H> `
  --out $outPath --crop
```

The wrapper automatically uses agy's headless permission flag
`--dangerously-skip-permissions` (plural) and disables slash-command expansion.
This grants agy broad local tool access, so use only a reviewed prompt and trusted
local references. Set `AGY_REQUIRE_PERMISSIONS=1` to omit the flag when the local
agy permission allow-list is already configured.

The wrapper also handles agy 1.1.x artifact behavior: the native image tool may
save under `~/.gemini/antigravity-cli/brain/` instead of the requested output
path. The wrapper finds the newly created artifact, materializes it at `--out`,
converts formats when a supported local converter exists, and verifies dimensions.

Use `--dry-run` before consuming quota when validating paths or prompt composition.
Do not overwrite an existing asset unless the user explicitly requests it and
`--overwrite` is passed.

## Reference consistency

For a recurring character, pass one or two clear images with repeated `--ref`
arguments plus `--refs-dir`. Keep `--subject-anchor`, dimensions, and reference
set stable across the series. Let the reference define identity; keep facial,
ethnicity, skin-tone, and existing hair details out of the scene prompt. Read
[prompt-guide.md](references/prompt-guide.md) before generating a reference-locked
series.

## Verify and integrate

Require the wrapper JSON to report:

- `status: "completed"`;
- an existing `out` file;
- parsed `actual` dimensions;
- `matched: true`;
- the true `format` matching the intended storyboard use.

For osu! assets, then add the final relative path to the `.osb`, `.osu`, or
storybrew project and preview it in gameplay. Never put an absolute Windows or
WSL path in storyboard source.

If generation fails, report the included agy output tail and consult
[troubleshooting.md](references/troubleshooting.md). Do not fabricate a result or
claim an unverified size.

## Deliver

Return, in order:

1. completed or failed;
2. actual versus requested pixel size and whether cropping occurred;
3. actual container format and final absolute path;
4. inline image attachment when the client supports it;
5. for osu!, the relative beatmap path and intended `Sprite`/`Animation` role.

Installation locations for Codex, Claude Code, Gemini CLI, GitHub Copilot, and
other Agent Skills clients are documented in
[agent-compatibility.md](references/agent-compatibility.md). The portable installer
is [install_skill.py](scripts/install_skill.py).

## Maintainer references

- Read [agy-cli.md](references/agy-cli.md) when agy flags, artifact behavior, or
  size/format handling changes.
- Read [runtime-paths.md](references/runtime-paths.md) before changing runtime
  detection, WSL selection, or path translation.
- Read [readiness_report.md](references/readiness_report.md) before changing the
  lifecycle state in [skill_lifecycle.yaml](skill_lifecycle.yaml).
- Follow [migration-governance.md](references/migration-governance.md) for a rename,
  merge, split, or deprecation.
- Update [evals.json](assets/evals/evals.json) and
  [regression_gates.json](assets/evals/regression_gates.json) with behavior changes.
