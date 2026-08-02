import os
import platform
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "output"


def _default_openmvs_bin() -> Path:
    if platform.system() == "Windows":
        return PROJECT_ROOT / "tools" / "OpenMVS" / "vc17" / "x64" / "Release"
    # Linux: compilato da sorgente, nessuna build precompilata per ARM64 (vedi deploy/oracle/).
    return Path.home() / "openmvs_src" / "build_output" / "bin"


OPENMVS_BIN = Path(os.environ.get("OPENMVS_BIN", _default_openmvs_bin()))
