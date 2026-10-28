# Font Awesome 7.3.1 — local Classic set

The app now uses the provided **Font Awesome Free 7.3.1** web package locally.

```
sample-1/
  fontawesome/
    css/all.min.css
    webfonts/
```

Every page links to:

```html
<link rel="stylesheet" href="fontawesome/css/all.min.css" />
```

There is **no CDN dependency**.

## Classic family

Font Awesome 7 Free includes the `fa-classic` family. The app emits:

```html
<i class="fa-classic fa-solid fa-house"></i>
```

- `fa-classic` selects the Classic style family
- `fa-solid` selects the solid weight
- Real icon classes: `fa-house`, `fa-users`, `fa-play`, etc.

## Icon mapping

`app.js` maps the prototype's existing SVG IDs to Font Awesome classes at runtime:

| SVG id | Font Awesome |
|---|---|
| `i-home` | `fa-house` |
| `i-users` | `fa-users` |
| `i-play` | `fa-play` |
| `i-search` | `fa-magnifying-glass` |
| `i-settings` | `fa-gear` |
| `i-music` | `fa-music` |
| `i-folder` | `fa-folder` |
| `i-calendar` | `fa-calendar-days` |
| `i-bar` | `fa-chart-column` |
| `i-video` | `fa-clapperboard` |
| `i-grid` | `fa-table-cells-large` |

The full map is in `app.js`.

## Pro Classic

If you later move to the Font Awesome **Pro Classic** kit, replace the local
`fontawesome/css/all.min.css` link with your kit script. The `fa-classic fa-solid`
classes stay the same.
