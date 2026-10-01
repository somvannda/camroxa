-- 0019_admin_integrity — stop the admin console from creating ambiguous state.
--
-- 1. `credit_packs` has no unique key on (amount, currency), so the same pack can
--    be created twice (0014 had to repair exactly that). Two active rows of the
--    same size make the "cheapest active pack" rate helper
--    (`ORDER BY amount LIMIT 1`) pick arbitrarily, so identical-looking packs can
--    quote different prices. Collapse existing duplicates — repointing payments
--    at the survivor first so purchase history keeps its pack reference — then
--    add a partial unique index over *active* rows. Inactive rows stay free to
--    repeat so a retired pack can coexist with its replacement.
-- 2. `suno_accounts.label` is the account's identity in the routing pool
--    (src/pool.ts maps `id` to the label) and in the admin health views, so two
--    accounts sharing a label silently merge into one. Rename duplicates, then
--    make the label unique.

-- ---- credit_packs ---------------------------------------------------------
-- Prefer an active row as the survivor so a sellable pack is never dropped.
WITH ranked AS (
  SELECT
    id,
    first_value(id) OVER (PARTITION BY amount, currency ORDER BY is_active DESC, id) AS keeper
  FROM credit_packs
)
UPDATE payment_transactions t
SET pack_id = d.keeper
FROM ranked d
WHERE d.id <> d.keeper AND t.pack_id = d.id;

WITH ranked AS (
  SELECT
    id,
    first_value(id) OVER (PARTITION BY amount, currency ORDER BY is_active DESC, id) AS keeper
  FROM credit_packs
)
DELETE FROM credit_packs WHERE id IN (SELECT id FROM ranked WHERE id <> keeper);

CREATE UNIQUE INDEX IF NOT EXISTS credit_packs_active_amount_currency_key
  ON credit_packs (amount, currency) WHERE is_active;

-- ---- suno_accounts --------------------------------------------------------
-- Rename duplicates rather than delete them: the cookie/device_id may still be
-- in use, and an operator should decide which to keep.
WITH ranked AS (
  SELECT
    id,
    row_number() OVER (PARTITION BY label ORDER BY created_at, id) AS rn
  FROM suno_accounts
)
UPDATE suno_accounts s
SET label = s.label || ' [' || left(s.id::text, 8) || ']'
FROM ranked r
WHERE s.id = r.id AND r.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS suno_accounts_label_key ON suno_accounts (label);
