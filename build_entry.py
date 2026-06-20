import sys
import os
from pathlib import Path

# Add project root so all imports resolve as absolute paths
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def _load_env_for_exe() -> None:
    """Load .env file into os.environ before the app starts.
    
    Searches multiple locations in order (later wins, then os.environ overrides):
    1. Project root (source tree)
    2. python_app subdirectory
    3. Directory containing the EXE (frozen mode)
    4. Current working directory
    """
    candidates: list[Path] = []
    
    # Source tree paths (development mode)
    root = Path(project_root)
    candidates.append(root / ".env")
    candidates.append(root / "python_app" / ".env")
    
    # Frozen mode: EXE directory and PyInstaller bundle dir (_internal / _MEIPASS)
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / ".env")
        # PyInstaller onedir: bundled datas live in _internal (sys._MEIPASS)
        meipass = getattr(sys, '_MEIPASS', '')
        if meipass:
            candidates.append(Path(meipass) / ".env")
        candidates.append(exe_dir / "_internal" / ".env")
    
    # Always check current working directory last (highest priority before os.environ)
    candidates.append(Path.cwd() / ".env")
    
    loaded: dict[str, str] = {}
    for path in candidates:
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                text = line.strip()
                if not text or text.startswith("#") or "=" not in text:
                    continue
                if text.lower().startswith("export "):
                    text = text[7:].strip()
                key, value = text.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key:
                    continue
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]
                loaded[key] = value
        except Exception:
            continue
    
    # os.environ takes precedence (already set vars win)
    for key, value in loaded.items():
        if key not in os.environ:
            os.environ[key] = value

_load_env_for_exe()

# When PyInstaller exe is invoked with `-m python_app.visualizer.main`,
# route directly to the visualizer subprocess instead of launching the full app.
if len(sys.argv) >= 3 and sys.argv[1] == "-m" and sys.argv[2] == "python_app.visualizer.main":
    # Strip the `-m module` args so argparse in main() sees only the real arguments
    sys.argv = [sys.argv[0]] + sys.argv[3:]
    from python_app.visualizer.main import main as _visualizer_main
    raise SystemExit(_visualizer_main())

from python_app.app.bootstrap import run

raise SystemExit(run())
