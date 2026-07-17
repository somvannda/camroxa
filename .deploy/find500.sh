grep "auth/login.* 500" /var/log/nginx/access.log | tail -3
journalctl -u camxora-api --since "2026-07-15 22:19:00" --until "2026-07-15 22:21:00" --no-pager | grep -iE "column|email_confirmed|ProgrammingError|asyncpg" | head -20
