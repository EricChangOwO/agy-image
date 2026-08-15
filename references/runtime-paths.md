# Runtime and path handling

Run `scripts/runtime_probe.py` before `scripts/agy_image.py`. The probe decides
which Python environment must launch the wrapper, locates `agy`, and translates
filesystem paths into that environment's syntax.

## Environment matrix

| Agent runtime | Where `agy` is found | Wrapper runtime | Paths passed to wrapper |
|---|---|---|---|
| Windows | Native Windows | Current Windows Python | Absolute Windows paths |
| Windows | WSL distro | Selected distro's `python3` | Absolute POSIX/WSL paths |
| WSL | Current or login-shell PATH | Current WSL Python | Absolute POSIX paths |
| Native Linux/macOS | Current or login-shell PATH | Current Python | Absolute POSIX paths |

The probe reports the decision in `generation.launcher`, the executable in
`generation.agy_path`, and one normalized value per input in
`translated_paths[].generation_path`.

## Keep path domains separate

These strings can refer to related locations, but they are not interchangeable:

| Domain | Example | Used by |
|---|---|---|
| Windows filesystem | `C:\Maps\Song\SB\bg.jpg` | Windows Python and PowerShell |
| WSL mounted filesystem | `/mnt/c/Maps/Song/SB/bg.jpg` | WSL Python and Linux commands |
| WSL home | `/home/user/agy_images/bg.jpg` | WSL only |
| Storyboard-relative | `SB/bg.jpg` | `.osb`, `.osu`, or storybrew source |

Do not pass `C:\...` to a WSL Python process. Do not pass `/mnt/c/...` to a
Windows Python process. Do not use `pathlib.Path` from one runtime to normalize
the other runtime's syntax. Use the probe result instead of manually replacing
slashes or assuming the distro name is `Ubuntu`.

## Windows agent with WSL agy

Pass every path used by the wrapper to the probe, including the installed skill
directory, output file, references, and reference directory:

```powershell
$probe = (python scripts/runtime_probe.py `
  --path (Resolve-Path '.').Path `
  --path 'C:\Maps\Song\SB\agy\chorus-city.jpg' `
  --path 'C:\Maps\Song\references\character.png' | Out-String) |
  ConvertFrom-Json

if ($LASTEXITCODE -ne 0 -or $probe.status -ne 'ready') {
  throw 'No usable agy runtime or path conversion'
}
if ($probe.translated_paths.error | Where-Object { $_ }) {
  throw 'At least one path could not be converted'
}
```

If the probe chooses WSL, use `generation.distro`, run the translated script
path through that distro's `python3`, pass `generation.agy_path` via
`--agy-bin`, and use only translated paths for wrapper arguments.

## WSL and login-shell PATH

`wsl.exe -d <distro> -- python3 ...` does not necessarily load the user's shell
profile. An `agy` installed in `~/.local/bin` can therefore exist even when
`shutil.which("agy")` returns nothing. The probe checks a login shell and returns
the resolved executable. Always pass that absolute path to `--agy-bin` so the
wrapper does not depend on inherited `PATH`.

## Storyboard integration

Path conversion is only for reading and writing files. After generation, write a
beatmap-relative path such as `SB/agy/chorus-city.jpg` into storyboard source.
Never put `C:\...`, `/mnt/c/...`, or `/home/...` in the storyboard.
