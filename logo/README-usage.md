# Using the cli-guru logo on GitHub

## README header (theme-aware, text-independent)

```html
<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="logo/lockup-dark-matched.png">
    <img src="logo/lockup-light-matched.png" alt="cli-guru" width="320">
  </picture>
</div>
```

> **Use the `-matched` pair for this.** The original `cli-guru-lockup-light.png`
> and `-dark.png` were exported with different amounts of canvas padding —
> 1068x272 (ratio 3.93) against 1292x496 (ratio 2.60) — so a single `width` on
> the `<img>` renders them at different sizes. At `width="320"` the mark came out
> 281px wide on light and 231px on dark, in boxes 81px and 123px tall, and the
> header visibly jumped when the reader switched theme. `<picture>` puts the
> width on the `<img>`, so it cannot be compensated per-source.
>
> `lockup-light-matched.png` / `lockup-dark-matched.png` are cropped from the
> full-resolution originals to the artwork bounds plus uniform padding of 25% of
> the artwork height. Both are 1021x266 with the artwork at 933x178, so they
> render identically in either theme. Nothing was rescaled — the artwork is at
> its original capture resolution.
>
> If you re-export the lockups from source, match the padding and this pair can
> be deleted.

GitHub honours `<picture>` + `prefers-color-scheme` in markdown, so the mark
stays visible in both themes. PNG is used here because GitHub proxies images and
will not load the webfont an SVG `<text>` element asks for.

## Mark only (SVG is safe — pure geometry, no text)

```html
<img src="logo/cli-guru-mark.svg" alt="" width="72">
```

Use `cli-guru-mark-reverse.svg` on dark grounds, or the same `<picture>` pattern.
Pair it with the ordinary markdown heading `# cli-guru` rather than a text SVG.

## Social preview

Settings → General → Social preview → upload `cli-guru-social.png` (1280×640).
PNG or JPG only; SVG is rejected there.

## Favicon (docs site)

```html
<link rel="icon" href="logo/cli-guru-favicon.svg">
```

## Files

| File | Use |
|---|---|
| `cli-guru-mark.svg` | mark, ink on light |
| `cli-guru-mark-reverse.svg` | mark, light on dark |
| `cli-guru-mark-mono.svg` | single-colour mark |
| `cli-guru-favicon.svg` | filled 32px tile, heavier stroke |
| `cli-guru-lockup-light.png` / `-dark.png` | mark + wordmark, 4x capture (~1070px / ~1290px wide) |
| `lockup-light-520.png` / `lockup-dark-520.png` | same, downsized to 520px |
| `cli-guru-social.png` | 1280×640 social preview |
| `lockup-light-matched.png` / `lockup-dark-matched.png` | **README header** — same aspect ratio and artwork size in both themes; derived from the full-res originals |
| `cli-guru-lockup.svg` / `cli-guru-social.svg` | editable sources — text needs JetBrains Mono installed |
