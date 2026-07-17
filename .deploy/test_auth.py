import asyncio
import os
import sys
sys.path.insert(0, "/opt/camxora/repo")

async def main():
    for line in open("/opt/camxora/repo/platform_api/.env"):
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k,v=line.split("=",1)
        os.environ.setdefault(k, v.strip().strip('"'))

    from platform_api.database.session import get_session_factory
    from platform_api.services.auth_service import AuthService

    pw = "Iamduke168!!@@##$$"
    factory = get_session_factory()
    async with factory() as session:
        svc = AuthService(session)
        try:
            t = await svc.authenticate("duke@camxora.com", pw)
            print("OK", t.access_token[:30])
        except Exception as e:
            print("FAIL", type(e).__name__, e)

asyncio.run(main())
