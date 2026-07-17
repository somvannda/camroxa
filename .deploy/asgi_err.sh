journalctl -u camxora-api --since "2026-07-15 22:30:00" --until "2026-07-15 22:50:00" --no-pager | grep -A15 "Exception in ASGI" | head -40
