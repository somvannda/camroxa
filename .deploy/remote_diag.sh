#!/bin/bash
sudo -u postgres psql -d camxora_platform -c "SELECT email, role, status, email_confirmed FROM users;"
sudo -u postgres psql -d camxora_platform -c "SELECT key, value FROM system_settings WHERE key='signup_mode';"
journalctl -u camxora-api --since "2026-07-15 22:18:00" --until "2026-07-15 22:51:00" --no-pager | grep -iE "Traceback|Error|email_confirmed|column" | tail -30
