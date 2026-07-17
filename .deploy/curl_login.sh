cat > /tmp/login.json <<'EOF'
{"email":"duke@camxora.com","password":"Iamduke168!!@@##$$"}
EOF
curl -sS -w "\nHTTP:%{http_code}\n" -X POST http://127.0.0.1:8100/api/v1/auth/login -H "Content-Type: application/json" --data-binary @/tmp/login.json
