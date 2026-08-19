# Admin blog routes require Depends(require_admin)

**Date:** 2026-08-19  
**Branch:** `bugfix/admin-blog-auth-depends`

## Summary

Admin blog endpoints declared `_: Any = require_admin` without `Depends()`. FastAPI treated that as a default argument, not a dependency, so list/create/update/delete ran with no login. Public `/blog-posts/public` was already open and is unchanged.

## Product impact

- Unauthenticated callers can no longer read the full admin blog list (including unpublished posts and SEO fields) or mutate posts.
- Signed-in admins keep the same Blog Posts UI; they still send a bearer token.
- Public website blog listing is unchanged.

## Technical impact

- `platform_api/routers/blog_posts.py` uses `AdminDep = Annotated[AuthContext, Depends(require_admin)]` on all `/admin/blog-posts` handlers, matching other admin routers.
- A unit test walks route dependencies so this cannot regress to a bare default.

## Files touched

- `platform_api/routers/blog_posts.py`
- `platform_api/tests/test_blog_posts_admin_auth.py`
- `platform_api/CHANGELOG.md`

## Migration/deploy

No database migration. Sandbox API sync + `camxora-api` restart only. Production only on explicit request.

## Tests

- `python -m pytest platform_api/tests/test_blog_posts_admin_auth.py -q`
- After sandbox deploy: unauthenticated `GET /api/v1/admin/blog-posts` returns 401, not 200.

## Follow-ups

- Production deploy when asked.
- Logged-in admin Blog Posts UI smoke still needs a sandbox admin password.
