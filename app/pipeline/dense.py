import os
import platform
import subprocess
from pathlib import Path

try:
    import pycolmap
except ImportError:
    # Nessuna wheel pycolmap per Linux ARM64: fallback al binario CLI 'colmap' (vedi sparse.py).
    pycolmap = None

from .config import OPENMVS_BIN
from .remove_background import generate_masks

_EXE_SUFFIX = ".exe" if platform.system() == "Windows" else ""

# Il pacchetto 'colmap' di apt e' compilato con supporto GUI (Qt): anche i comandi CLI
# provano ad inizializzare un'interfaccia grafica e crashano (SIGABRT) su un server
# headless senza display. 'offscreen' forza Qt a girare senza una vera finestra.
_CLI_ENV = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}


def _undistort_images(sparse_model_path: Path, image_dir: Path, mvs_path: Path) -> None:
    if pycolmap is not None:
        pycolmap.undistort_images(mvs_path, sparse_model_path, image_dir)
        return
    subprocess.run(
        [
            "colmap", "image_undistorter",
            "--image_path", str(image_dir),
            "--input_path", str(sparse_model_path),
            "--output_path", str(mvs_path),
            "--output_type", "COLMAP",
        ],
        check=True, env=_CLI_ENV,
    )


def _run_openmvs(exe_name: str, args: list[str], cwd: Path) -> None:
    exe_path = OPENMVS_BIN / f"{exe_name}{_EXE_SUFFIX}"
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


def run_dense_reconstruction(
    image_dir: Path,
    sparse_model_path: Path,
    workspace_dir: Path,
    resolution_level: int = 1,
    remove_background: bool = True,
) -> Path:
    """Point cloud densa + mesh + texture via OpenMVS (CPU-only, nessuna GPU NVIDIA richiesta).

    resolution_level: quante volte dimezzare le immagini per il calcolo delle depth-map
    (fase piu' lenta della pipeline). 0 = risoluzione piena, 1 = default OpenMVS, 2+ = piu'
    veloce ma meno dettagliato. Vedi mappatura in run_pipeline.py in base al preset scelto.

    remove_background: se True, segmenta ogni immagine con rembg (CPU) e passa le
    maschere a OpenMVS in modo che la point-cloud densa (e quindi la mesh finale)
    contenga solo l'oggetto in primo piano, non lo sfondo/superficie intorno.
    """
    mvs_path = workspace_dir / "mvs"
    mvs_path.mkdir(parents=True, exist_ok=True)

    # OpenMVS richiede immagini non distorte e camere in formato PINHOLE.
    _undistort_images(sparse_model_path, image_dir, mvs_path)

    _run_openmvs(
        "InterfaceCOLMAP",
        ["-i", str(mvs_path), "-o", "scene.mvs", "--image-folder", str(mvs_path / "images")],
        cwd=mvs_path,
    )

    # Niente -o / --cuda-device qui: con questi flag il binario esce con un errore
    # silenzioso (nessun log, nessun output). Senza, usa i nomi di default e la CPU
    # in automatico (non essendoci una GPU NVIDIA disponibile).
    # max-threads limitato: con tutti i core in parallelo si e' osservato un crash
    # intermittente (access violation) durante la stima delle depth-map.
    densify_args = ["-i", "scene.mvs", "--max-threads", "4", "--resolution-level", str(resolution_level)]
    if remove_background:
        # Le maschere vanno generate sulle immagini NON distorte (quelle che OpenMVS usa
        # davvero), altrimenti la corrispondenza pixel-per-pixel con la distorsione della
        # lente non e' piu' valida. Convenzione nome file richiesta da OpenMVS (vedi
        # DensifyPointCloud.cpp): "<mask-path>/<nome_immagine_senza_estensione>.mask.png".
        # --ignore-mask-label 0: nella maschera generata, 0 = sfondo (da ignorare),
        # 255 = primo piano (da tenere); di default il masking e' disattivato (<0).
        mask_dir = generate_masks(mvs_path / "images", mvs_path / "masks")
        densify_args += ["--mask-path", f"{mask_dir}{os.sep}", "--ignore-mask-label", "0"]
    _run_openmvs("DensifyPointCloud", densify_args, cwd=mvs_path)

    # Decimazione aggressiva: senza, la mesh densa (centinaia di migliaia di facce)
    # genera troppe micro-patch di texture e TextureMesh va in crash (access violation).
    _run_openmvs(
        "ReconstructMesh",
        ["-i", "scene_dense.mvs", "-o", "scene_mesh.ply", "--decimate", "0.2"],
        cwd=mvs_path,
    )

    _run_openmvs(
        "TextureMesh",
        ["-i", "scene_dense.mvs", "-m", "scene_mesh.ply", "-o", "scene_textured.glb", "--export-type", "glb"],
        cwd=mvs_path,
    )

    glb_path = mvs_path / "scene_textured.glb"
    if not glb_path.exists():
        raise RuntimeError(f"File glb finale non trovato in {glb_path}")
    return glb_path
