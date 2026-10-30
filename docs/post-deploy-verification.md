# Post-deploy verification — credits-only

Run after the production deploy completes.

## 1. Services

```bash
systemctl is-active camxora-api camxora-website camxora-music nginx postgresql redis-server
systemctl is-active camxora-portal || echo "portal retired (expected)"
curl -sf https://api.camxora.com/health
curl -sf -o /dev/null -w "%{http_code}\n" https://camxora.com
curl -sf -o /dev/null -w "%{http_code}\n" https://admin.camxora.com
curl -sf -o /dev/null -w "%{http_code}\n" https://music.camxora.com
```

## 2. Database

```sql
-- wallet invariant: expect 0
SELECT count(*) FROM credit_wallets w
WHERE w.balance <> COALESCE((
  SELECT SUM(remaining_units) FROM credit_wallet_lots l
  WHERE l.user_id = w.user_id AND l.remaining_units > 0
    AND (l.expires_at IS NULL OR l.expires_at > now())
), 0);

-- tier split: expect 11 pro / 228 free
SELECT CASE WHEN EXISTS (
  SELECT 1 FROM credit_wallet_lots l
  WHERE l.user_id = w.user_id AND l.tag='pack'
    AND l.remaining_units > 0
    AND (l.expires_at IS NULL OR l.expires_at > now())
) THEN 'pro' ELSE 'free' END AS tier, count(*)
FROM credit_wallets w GROUP BY 1 ORDER BY 1;

-- plan tables gone: expect 0 rows
SELECT table_name FROM information_schema.tables
WHERE table_schema='public'
  AND table_name IN ('plans','licenses','plan_usage','plan_offers','web_subscriptions');

-- payments intact: expect 25
SELECT count(*) FROM billing_payments;

-- V6 pricing: expect 10.00 for V6 / V6_MINI / V6_WILD and the default row
SELECT coalesce(sub_model,'(default)'), credits_per_operation/10000.0
FROM credit_pricing
WHERE ai_service='suno' AND operation_type='music'
ORDER BY 1;

-- every live lot has an expiry: expect 0
SELECT count(*) FROM credit_wallet_lots
WHERE remaining_units > 0 AND expires_at IS NULL;
```

## 3. Functional smoke

1. Sign in as a Free user → balance 50, tier Free.
2. Generate V6-Pro → 10 credits debited, 60s preview.
3. Generate V6-Wild → 10 credits, 60s preview.
4. Generate V6-Mini → 10 credits, full track.
5. Buy a pack → tier Pro, pack lot with 30-day expiry.
6. Force a provider failure → refund returns the 10 credits and the preview slot.
7. Admin adjustment → admin lot with a 30-day expiry.

## 4. Rollback

Restore the fresh snapshot taken before deploy:

```
/opt/camxora/backups/camxora_platform_predeploy_<timestamp>.dump
```

`alembic downgrade 173` only renames archive tables back; it does not restore
the rebuilt lots or the dropped FK columns. Restore the snapshot for a full rollback.
