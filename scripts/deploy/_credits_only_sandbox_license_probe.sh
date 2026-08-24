#!/bin/bash
set -euo pipefail
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT status, count(*) FROM licenses GROUP BY status ORDER BY 1;
"
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT l.status, p.name, p.price_cents, count(*)
FROM licenses l
JOIN plans p ON p.id = l.plan_id
GROUP BY 1, 2, 3
ORDER BY 1, 2;
"
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT u.email, l.status, p.name, l.expires_at, l.activated_at
FROM licenses l
JOIN users u ON u.id = l.user_id
JOIN plans p ON p.id = l.plan_id
WHERE l.user_id IS NOT NULL
ORDER BY l.status, u.email
LIMIT 40;
"
