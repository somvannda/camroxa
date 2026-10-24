# Camxora design reference

Static snapshot of the approved new Camxora templates.

## Source

Imported from the prototype at `C:\Users\Kong Somvannda\Downloads\camxora_website\sample-1`.

Included:

- Product HTML pages
- `app.css`
- `app.js`
- Logo, hero image
- Niradei fonts
- Font Awesome 7.3.1 CSS + webfonts + license

Excluded:

- Screenshots and preview PNGs
- Button/sidebar concept studies
- Build/generator scripts

## Important

This folder is a design reference. It is not served by the Next.js app and is not production code.

Known items to replace or resolve during porting:

- Google Fonts links for Inter must become self-hosted.
- Unsplash image URLs must become owned/B2 assets.
- Static prices, packs, and generations must come from the API.
- The prototype player is a UI simulation; production uses the existing player engines.
- `app.css` still contains dead light-mode and glass-button overrides; the port keeps only the dark system.
- Auth pages are visual references; production uses existing auth endpoints.
