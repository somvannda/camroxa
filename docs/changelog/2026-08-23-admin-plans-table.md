# 2026-08-23 — Admin Plans table

Sandbox only. Production not touched.

`/plans` drops the live-generate-path banner and the stacked card groups. Active credit plans are one table with lyric / title / album / music / style / image / video / merge amounts. ≈ Songs is display-only (`floor(grant / 10)`), not a quota. Profile add-on SKUs are collapsed; they sell slots only. Sandbox add-on rows now store the same per-op amounts as paid plans (music = 10) so they no longer show Credits-page fallback. Old 6-channel / 10-channel / term SKUs stay in the database so leftover licenses still resolve, but they are hidden behind **Show leftover channel SKUs**.
