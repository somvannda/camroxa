set -e
REPO=/opt/camxora/repo
# ensure source present (redeploy may have raced extract)
if [ ! -d "$REPO/user_portal/src" ]; then
  echo "user_portal missing, waiting for extract..."
  sleep 2
fi
ls -la "$REPO/user_portal" || true
cat > $REPO/user_portal/.env.production <<'ENVEOF'
# Same-origin /api/v1 via nginx — leave NEXT_PUBLIC_PLATFORM_API_BASE_URL unset
NEXT_PUBLIC_CAMXORA_ENV=sandbox
NEXT_PUBLIC_WEBSITE_URL=https://sandbox.camxora.com
NEXT_PUBLIC_USER_PORTAL_URL=https://app.sandbox.camxora.com
ENVEOF
chown camxora:camxora $REPO/user_portal/.env.production
sudo -u camxora bash -lc "cd $REPO/user_portal && npm ci || npm install --no-audit --no-fund && npm run build"
systemctl restart camxora-portal
systemctl is-active camxora-portal
echo DONE
