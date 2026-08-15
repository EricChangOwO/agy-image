# osu! storyboard image assets

Read this file when agy output will be referenced by `.osb`, `.osu`, or storybrew.

## Asset decision table

| Role | Suggested final size | Format | Notes |
|---|---:|---|---|
| 16:9 full-screen background or transition plate | 854x480 | JPEG | Opaque; compact; centre at `(320,240)` |
| 4:3 full-screen background | 640x480 | JPEG | Opaque legacy canvas |
| Large source for zoom/pan | 1536x864 | JPEG | Scale down in storyboard; check package size |
| Character cut-in or foreground object | 512x768 or scene-specific | PNG | Requires real alpha after background removal |
| Texture, light card, abstract overlay | 512x512 | PNG/JPEG | PNG only when transparency/lossless edges matter |
| Animation frame | Match every frame | PNG/JPEG | Use numbered names such as `pulse0.png`, `pulse1.png` |

osu! accepts PNG and JPEG storyboard objects. JPEG is suitable for opaque
backgrounds; PNG is appropriate for foreground edges and alpha. A generated JPEG
renamed to `.png` is not a PNG—verify the real container.

## Workflow

1. Locate the beatmap root containing `.osu`, `.osb`, and audio files.
2. Search storyboard source for existing image paths and inventory PNG/JPEG files.
3. Write a small asset manifest with role, prompt, dimensions, format, relative
   beatmap path, layer, origin, and first use time.
4. Generate only missing assets. Prefer one reviewed key image over a batch.
5. Store generated files in a concise relative directory such as `SB/agy/`.
6. Verify container, dimensions, alpha expectation, filename case, and file size.
7. Reference only the relative beatmap path, for example:

```text
Sprite,Background,Centre,"SB/agy/intro-space.jpg",320,240
 F,0,12000,12500,0,1
 F,0,18000,18500,1,0
```

8. Preview in gameplay, not only in the editor. Check 4:3 and 16:9 framing,
   storyboard layering, hit-object readability, and timing.

## Prompting for motion

Ask agy for a clean, motion-friendly composition:

- keep the main subject separated from edges when it will pan or zoom;
- request extra visual margin in the direction of movement;
- avoid text, logos, watermarks, UI glyphs, and tiny high-frequency detail;
- maintain a stable palette and subject anchor across related shots;
- generate animation keyframes one at a time and review continuity.

agy does not guarantee a transparent background. For a foreground cut-out,
generate against a plain contrasting background, then use an image-editing or
matting workflow and verify that the final PNG contains a real alpha channel.

## Coordinate facts

- Storyboard coordinates use a 640x480 4:3 canvas with centre `(320,240)`.
- On 16:9 screens the visible horizontal range is approximately `-107..747`,
  producing an 854x480 in-bounds area while retaining centre `(320,240)`.
- Image paths are relative to the beatmap folder; never write `C:\...`, `/home/...`,
  or `file://...` into storyboard source.
- A storyboard object is declared as
  `Sprite,(layer),(origin),"(filepath)",(x),(y)` or as an `Animation` with numbered
  frames.

Official references:

- <https://osu.ppy.sh/wiki/en/Storyboard/Scripting/General_Rules>
- <https://osu.ppy.sh/wiki/en/Storyboard/Scripting/Objects>
- <https://osu.ppy.sh/wiki/en/Client/Playfield#storyboards>
