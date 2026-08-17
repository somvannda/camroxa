#!/usr/bin/env python3
"""
Clean Next.js cache and rebuild music_web on sandbox.
Fixes Turbopack font loading issues.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from sync_platform_api_sandbox import resolve_sandbox_ssh, run_remote_command

def main():
    host, ssh_args = resolve_sandbox_ssh()
    
    print("Target sandbox host:", host)
    print("\nStep 1: Cleaning Next.js cache...")
    
    # Clean .next and node_modules cache
    clean_result = run_remote_command(
        host, ssh_args,
        "cd /opt/camxora/repo/music_web && rm -rf .next node_modules/.cache && echo 'Cache cleaned'"
    )
    
    if clean_result != 0:
        print("Warning: Cache cleaning failed, continuing anyway...")
    else:
        print("✓ Cache cleaned successfully")
    
    print("\nStep 2: Rebuilding music_web...")
    
    # Now run the normal rebuild
    from rebuild_music_web_sandbox import main as rebuild_main
    return rebuild_main()

if __name__ == "__main__":
    sys.exit(main())
