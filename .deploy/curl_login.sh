: "${CAMXORA_ADMIN_PASSWORD:?set CAMXORA_ADMIN_PASSWORD}"
: "${CAMXORA_ADMIN_EMAIL:=duke@camxora.com}"
cat > /tmp/login.json <<EOF
{"email":"${CAMXORA_ADMIN_EMAIL}","password":"${CAMXORA_ADMIN_PASSWORD}"}
EOF
curl -sS -w "\nHTTP:%{http_code}\n" -X POST http://127.0.0.1:8100/api/v1/auth/login -H "Content-Type: application/json" --data-binary @/tmp/login.json
