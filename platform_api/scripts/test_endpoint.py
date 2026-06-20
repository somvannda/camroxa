"""Test an API endpoint with a valid token to see the actual error."""
import os
os.environ['PLATFORM_DEBUG'] = 'true'

import asyncio
import sys
sys.path.insert(0, '.')

async def main():
    # Test 1: Direct database access
    import asyncpg
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/platform_db')
    rows = await conn.fetch('SELECT id, email, role FROM users LIMIT 5')
    print(f"Direct DB - Users found: {len(rows)}")
    for r in rows:
        print(f"  {r['email']} ({r['role']})")
    await conn.close()

    # Test 2: Simulate what the users endpoint does
    print("\n--- Testing UserRepository ---")
    try:
        pool = await asyncpg.create_pool('postgresql://postgres:postgres@localhost:5432/platform_db', min_size=1, max_size=2)
        from platform_api.repositories.user_repo import UserRepository
        repo = UserRepository(pool=pool)
        
        # Try calling the list method
        user = await repo.get_by_email('admin@mgfaceless.com')
        if user:
            print(f"  Found user: {user.email}, role={user.role}")
        else:
            print("  User not found!")
            
        await pool.close()
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    # Test 3: Check what the /users endpoint actually does
    print("\n--- Checking users router ---")
    try:
        from platform_api.routers import users
        print(f"  Router imported OK, routes: {[r.path for r in users.router.routes]}")
    except Exception as e:
        print(f"  ERROR importing router: {type(e).__name__}: {e}")

asyncio.run(main())
