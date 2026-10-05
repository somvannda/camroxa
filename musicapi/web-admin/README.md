# Camxora Admin Console (`web-admin`)

Operator console for the Camxora Music API. Next.js 16 (App Router), React 19,
Tailwind 4. Runs on **:4002**; production at `admin.musicapi.camxora.com`.

## Run

```bash
npm install
npm run dev            # http://localhost:4002
```

The console talks to the core API (`musicapi`, :4003) through a same-origin
`/backend/*` rewrite. `BACKEND_URL` (see `.env.example`) is read at build time by
`next.config.ts`; if unset it falls back to `http://localhost:4003`. The browser
never hardcodes the backend origin.

## Scripts

| Script | Purpose |
|---|---|
| `npm run dev` | Dev server on :4002 |
| `npm run build` / `npm start` | Production build / serve |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint (must stay clean) |

## Auth

- Admin-only, email/password → JWT in the httpOnly `sunosession_admin` cookie set
  by the API. The console only caches non-sensitive profile fields.
- `proxy.ts` (Next 16 `proxy` convention, formerly `middleware`) guards `/` and
  `/admin/:path*`: it forwards the cookie to `/auth/me` and bounces
  non-admins/inactive users to `/login` before rendering. The API remains the
  real authority — every `/admin/*` route re-checks `role` **and** `status`.

## Architecture

| Path | Role |
|---|---|
| `app/admin/**` | Pages (client components) |
| `components/AppShell.tsx` | Responsive sidebar + mobile drawer + topbar |
| `components/ui/*` | Shared primitives (see below) |
| `lib/useResource.ts` | Fetch-on-mount / reload hook |
| `lib/format.ts` | Number/date formatters |
| `lib/api.ts` | `apiFetch()` (401 → login) and `logout()` |
| `lib/auth.ts` | Caches only the non-sensitive profile |

### UI kit (`components/ui`)

`Button`, `Card`/`StatCard`, `Badge`, `Field` + `Input`/`Select`/`Textarea`,
`Feedback` (`Spinner`, `LoadingState`, `EmptyState`, `ErrorState`, `PageHeader`),
`Modal`, `ConfirmDialog`, `Toast` (`ToastProvider` + `useToast`).

## Conventions

- Never hardcode the backend origin — use `apiFetch` and the relative `/backend/*`
  path.
- Prefer the `components/ui` primitives over raw elements and repeated class
  strings.
- Load data with `useResource`; render `LoadingState` / `EmptyState` /
  `ErrorState`; confirm destructive actions with `ConfirmDialog`; report outcomes
  with `useToast`.
- List endpoints paginate and filter **server-side** and return
  `{ rows, total, page, page_size }`; tables render the shared pager.
- `useResource` never writes state synchronously inside an effect (satisfies
  `react-hooks/set-state-in-effect`).

## Security headers

`next.config.ts` sets `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, a strict-origin-when-cross-origin `Referrer-Policy`, a
restrictive `Permissions-Policy`, and — in production — `Strict-Transport-Security`
and a `Content-Security-Policy`; it also disables the `x-powered-by` header.
