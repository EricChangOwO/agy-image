# Troubleshooting agy generation

## Tool permission was auto-denied

Confirm the command contains the exact plural flag
`--dangerously-skip-permissions`. The wrapper adds it unless
`AGY_REQUIRE_PERMISSIONS=1` is set. If broad auto-approval is unacceptable,
configure agy's local permission allow-list and use that environment variable.

## agy generated an artifact but `--out` is missing

agy 1.1.x normally saves native output below
`~/.gemini/antigravity-cli/brain/<id>/`. The wrapper discovers newly created
artifacts and materializes them at `--out`. If discovery fails:

1. inspect `agy_stdout_tail` and `agy_stderr_tail`;
2. inspect the newest brain conversation and transcript;
3. confirm no other concurrent agy session generated a competing image;
4. verify the artifact has a PNG, JPEG, or WEBP file header.

## Output already exists

The wrapper refuses to replace files by default. Choose a new filename or pass
`--overwrite` only after the user explicitly approves replacement.

## Wrong size or square fallback

Use explicit `--width` and `--height`, then `--crop`. The wrapper centre-crops and
scales through ffmpeg or, under WSL on Windows, PowerShell System.Drawing.

## Format conversion failed

Use `.jpg` for an opaque generated background, install ffmpeg, or run under WSL
with `powershell.exe` available. Do not disguise JPEG bytes with a `.png` suffix.

## Reference image was ignored

- Use one or two front-facing, well-lit references.
- Pass each path with `--ref` and expose its folder with `--refs-dir`.
- Remove facial, ethnicity, skin-tone, and existing hair descriptors from the
  scene prompt so the reference owns identity.

## Timeout or empty output

Print mode buffers until completion. Image generation commonly takes several
minutes. The default timeout is 12 minutes; increase it for a complex request.

## Inspect without quota use

Pass `--dry-run` to see the command, exposed directories, composed prompt, output
path, and exact requested dimensions without invoking agy.
