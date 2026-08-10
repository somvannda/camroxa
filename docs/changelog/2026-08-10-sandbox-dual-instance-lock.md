# Sandbox desktop can run alongside production

## Summary

The desktop single-instance guard used one shared local-server name for every build. Opening a second Camxora process (sandbox or production) focused the existing window and exited — so sandbox could not be tested next to a live production install.

## Change

- **Production** keeps the stable lock name: `Camxora.DesktopStudio.SingleInstance.v1` (unchanged for existing installs).
- **Sandbox** uses `Camxora.DesktopStudio.SingleInstance.v1.sandbox`, so one sandbox app and one production app can run at the same time.
- Within each environment, a second launch still focuses the primary window and exits.

## Files

- `camxora_python/shared/lib/single_instance.py`
- `camxora_python/tests/test_single_instance.py`
