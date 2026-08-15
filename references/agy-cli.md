# agy CLI image generation

## Runtime model

`agy` is Google's Antigravity agentic CLI. It is not a direct image API: in print
mode an LLM calls its native `generate_image` tool, which normally stores the
result under:

```text
~/.gemini/antigravity-cli/brain/<conversation-id>/<image-name>.jpg
```

The bundled wrapper snapshots that artifact tree before the run, requests exactly
one generation, finds the new artifact after completion, and copies or converts it
to `--out`.

## Headless permissions

Print mode cannot show an interactive permission prompt. agy 1.1.13 reports an
auto-denial unless the needed command permission is configured or this exact flag
is present:

```text
--dangerously-skip-permissions
```

The flag is plural. The wrapper adds it by default and also adds
`--disable-slash-commands` to prevent installed skills from recursively invoking
another agy session. Because the permission flag auto-approves all agy tools, run
only reviewed prompts and trusted local reference files. Set
`AGY_REQUIRE_PERMISSIONS=1` to omit it when a local allow-list is configured.

## Print-mode flags

| Flag | Purpose |
|---|---|
| `--print "<prompt>"` | Run one non-interactive prompt |
| `--print-timeout 12m` | Allow enough time for image generation |
| `--add-dir <dir>` | Expose output/reference directories to the session |
| `--disable-slash-commands` | Prevent skill expansion and nested invocation |
| `--dangerously-skip-permissions` | Permit the native image tool in headless mode |

Print mode buffers output. Empty stdout while the process is alive is not by
itself evidence of a hang.

## Size and format behavior

- Aspect-ratio shorthand is inconsistent; always request explicit width and height.
- The native tool may return 1024x1024 even when another size is requested.
- `--crop` centre-crops and scales with ffmpeg. Under WSL, Windows PowerShell and
  System.Drawing provide a fallback for JPEG/PNG conversion and resizing.
- The native artifact is commonly JPEG. Never rename JPEG bytes to `.png`; the
  wrapper verifies file headers and performs a real conversion when possible.

Use `.jpg` for opaque osu! backgrounds when no PNG feature is needed. It avoids a
lossless transcode and keeps the beatmap package smaller.
