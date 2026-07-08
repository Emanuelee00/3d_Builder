import subprocess
from pathlib import Path

import pycolmap

from .config import OPENMVS_BIN


def _run_openmvs(exe_name: str, args: list[str], cwd: Path) -> None:
    exe_path = OPENMVS_BIN / exe_name
    result = subprocess.run(
        [str(exe_path), *args], cwd=cwd, capture_output=True, text=True
    )
    if result.returncode != 0:
        log_files = sorted(cwd.glob(f"{exe_path.stem}-*.log"))
        log_tail = ""
        if log_files:
            log_tail = log_files[-1].read_text(encoding="utf-8", errors="ignore")[-2000:]
        raise RuntimeError(
            f"{exe_name} fallito (exit {result.returncode}).\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\nLOG:\n{log_tail}"
        )


def run_dense_reconstruction(image_dir: Path, sparse_model_path: Path, workspace_dir: Path) -> Path:
    """Point cloud densa + mesh + texture via OpenMVS (CPU-only, nessuna GPU NVIDIA richiesta)."""
    mvs_path = workspace_dir / "mvs"
    mvs_path.mkdir(parents=True, exist_ok=True)

    # OpenMVS richiede immagini non distorte e camere in formato PINHOLE.
    pycolmap.undistort_images(mvs_path, sparse_model_path, image_dir)

    _run_openmvs(
        "InterfaceCOLMAP.exe",
        ["-i", str(mvs_path), "-o", "scene.mvs", "--image-folder", str(mvs_path / "images")],
        cwd=mvs_path,
    )

    # Niente -o / --cuda-device qui: con questi flag il binario esce con un errore
    # silenzioso (nessun log, nessun output). Senza, usa i nomi di default e la CPU
    # in automatico (non essendoci una GPU NVIDIA disponibile).
    # max-threads limitato: con tutti i core in parallelo si e' osservato un crash
    # intermittente (access violation) durante la stima delle depth-map.
    _run_openmvs(
        "DensifyPointCloud.exe",
        ["-i", "scene.mvs", "--max-threads", "4"],
        cwd=mvs_path,
    )

    # Decimazione aggressiva: senza, la mesh densa (centinaia di migliaia di facce)
    # genera troppe micro-patch di texture e TextureMesh va in crash (access violation).
    _run_openmvs(
        "ReconstructMesh.exe",
        ["-i", "scene_dense.mvs", "-o", "scene_mesh.ply", "--decimate", "0.2"],
        cwd=mvs_path,
    )

    _run_openmvs(
        "TextureMesh.exe",
        ["-i", "scene_dense.mvs", "-m", "scene_mesh.ply", "-o", "scene_textured.glb", "--export-type", "glb"],
        cwd=mvs_path,
    )

    glb_path = mvs_path / "scene_textured.glb"
    if not glb_path.exists():
        raise RuntimeError(f"File glb finale non trovato in {glb_path}")
    return glb_path
