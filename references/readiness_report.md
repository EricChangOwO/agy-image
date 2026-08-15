# agy-image readiness report

Audit date: 2026-08-15
Lifecycle stage: draft

## Scope

The skill generates one verified raster image through local agy and now includes
automatic routing for missing osu! storyboard assets. It remains out of scope for
editing/analysing existing images and for requests naming another generator.

## Mechanical checks

| Check | Result |
|---|---|
| Agent Skills `quick_validate.py` | PASS |
| Python compile: generation wrapper, runtime probe, and installer | PASS |
| Eval and regression-gate JSON parsing | PASS |
| `git diff --check` | PASS |
| Frontmatter portability | PASS: only `name` and `description` |
| Codex `agents/openai.yaml` generation | PASS |

## Functional checks

| Check | Evidence |
|---|---|
| Permission command | Dry-run includes plural `--dangerously-skip-permissions` and `--disable-slash-commands` |
| Installer | Project-scope `--agent all` produced valid copies for `.agents`, `.claude`, `.gemini`, and `.github`; Codex and universal intentionally share `.agents` at project scope |
| Artifact materialization | Existing 1024x1024 agy JPEG became a genuine 854x480 PNG under WSL without ffmpeg, using Windows PowerShell System.Drawing |
| Header verification | Materialized output parsed as PNG, 854x480 |
| Deterministic wrapper path | A fake agy executable created one new brain artifact; the full wrapper discovered it, produced a cropped 854x480 JPEG, and returned `status: completed`, `matched: true`, and `source_artifact` |
| Read-only forward test | An isolated agent selected the skill for a missing storybrew chorus panorama, inventoried assets, chose 1536x864 JPEG plus `SB/agy/` relative integration, and exposed a dry-run directory-write issue that was fixed |
| Live agy dispatch | Auth succeeded and exactly one native `generate_image` call was recorded |
| Live agy completion | INCONCLUSIVE: the 2026-08-15 request timed out server-side after 12 minutes and created no artifact; wrapper returned `status: failed` without fabricating output |
| Windows to WSL detection | Windows Python selected Ubuntu, found agy 1.1.13 at `/home/e0pwr/.local/bin/agy`, and translated repository/output paths to `/mnt/c/...` in about one second |
| WSL direct detection | WSL Python found agy through login-shell PATH even when the non-interactive process PATH omitted `~/.local/bin`; the probe returns the absolute executable for `--agy-bin` |
| Distro side effects | Probing stops after the first distro containing agy; the initially exposed extra-distro startup was avoided on retest and the test Kali distro was restored to Stopped |

An earlier direct agy test on the same host completed a 1024x1024 JPEG artifact
after adding the permission flag. The later wrapper test demonstrates correct
dispatch and failure handling but is not counted as a completed end-to-end pass.

## Trigger coverage

The bundled eval set covers:

- direct Chinese and English agy requests;
- indirect `.osb`, `.osu`, and storybrew missing-asset cases;
- reuse-only and simple-resize storyboard negatives;
- another named generator and image-analysis negatives;
- permission and artifact-discovery regressions.
- Windows-host/WSL runtime selection, login-shell discovery, and mixed-path
  rejection regressions.

## Compatibility

The root directory follows the Agent Skills `SKILL.md` layout. The installer has
targets for Codex, Claude Code, universal `.agents`, Gemini CLI, and GitHub
Copilot/VS Code. Client-specific prompt forks are intentionally avoided.

## Residual risks

- `--dangerously-skip-permissions` broadly auto-approves agy tools. The wrapper
  disables slash-command expansion and instructs agy to call only its image tool,
  but users should configure a permission allow-list when possible.
- Generation depends on Antigravity authentication, service availability, and
  account quota; timeouts are expected external failures.
- The native tool commonly returns JPEG and does not guarantee transparency.
- Artifact fallback discovery can be ambiguous if multiple agy sessions generate
  images concurrently; avoid concurrent generations.
- A completed live wrapper generation and paired benchmark remain required before
  promoting this skill beyond draft.
