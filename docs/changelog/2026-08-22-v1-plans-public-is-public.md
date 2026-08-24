# v1 `/plans/public` honors `is_public` (2026-08-22)

`GET /api/v1/plans/public` now returns subscription rows that are **active and public**. Hidden catalog rows (legacy channel plans, unpublished $79) stay in Admin and license-assign.

JSON shape is unchanged (still no `music_credits` / `monthly_credits`). Website and user portal will stop seeing unpublished plans.

v3 `/api/v3/plans/public` already filtered this way.
