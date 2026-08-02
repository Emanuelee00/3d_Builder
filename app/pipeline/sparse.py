import os
import shutil
import subprocess
from pathlib import Path

# Il pacchetto 'colmap' di apt e' compilato con supporto GUI (Qt): anche i comandi CLI
# provano ad inizializzare un'interfaccia grafica e crashano (SIGABRT) su un server
# headless senza display. 'offscreen' forza Qt a girare senza una vera finestra.
_CLI_ENV = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}

try:
    import pycolmap
except ImportError:
    # Nessuna wheel pycolmap per Linux ARM64: fallback al binario CLI 'colmap'
    # (pacchetto apt, disponibile precompilato per arm64 a differenza del binding Python).
    pycolmap = None


def run_sparse_reconstruction(image_dir: Path, workspace_dir: Path) -> Path:
    """SfM sparso: pose delle camere + point cloud sparsa. Gira su CPU."""
    database_path = workspace_dir / "database.db"
    sfm_path = workspace_dir / "sparse"

    if database_path.exists():
        database_path.unlink()
    if sfm_path.exists():
        shutil.rmtree(sfm_path)
    sfm_path.mkdir(parents=True)

    if pycolmap is not None:
        return _run_with_pycolmap(image_dir, database_path, sfm_path)
    return _run_with_cli(image_dir, database_path, sfm_path)


def _run_with_pycolmap(image_dir: Path, database_path: Path, sfm_path: Path) -> Path:
    pycolmap.extract_features(database_path, image_dir)
    # I frame vengono da un video (sequenza ordinata), non da foto sparse: il matching
    # esaustivo (ogni coppia possibile, O(n^2)) confronta anche frame lontanissimi tra loro
    # che non condividono nulla. Il matcher sequenziale confronta solo frame vicini nel
    # tempo (adiacenti nella sequenza) - stesso approccio raccomandato da COLMAP per video.
    pycolmap.match_sequential(database_path)
    reconstructions = pycolmap.incremental_mapping(database_path, image_dir, sfm_path)

    if not reconstructions:
        raise RuntimeError(
            "Ricostruzione sparsa fallita: nessun modello generato. "
            "Servono piu' frame con overlap sufficiente tra loro."
        )

    best_idx = max(reconstructions, key=lambda idx: reconstructions[idx].num_reg_images())
    return sfm_path / str(best_idx)


def _run_with_cli(image_dir: Path, database_path: Path, sfm_path: Path) -> Path:
    # use_gpu=0: niente GPU/OpenGL su questo server headless (SiftGPU richiede un
    # contesto OpenGL, che fallisce senza display: "Check failed: context_.create()").
    # Forza il fallback CPU (VLFeat) per estrazione e matching delle feature SIFT.
    subprocess.run(
        ["colmap", "feature_extractor",
         "--database_path", str(database_path), "--image_path", str(image_dir),
         "--SiftExtraction.use_gpu", "0"],
        check=True, env=_CLI_ENV,
    )
    # sequential_matcher invece di exhaustive_matcher: i frame vengono da un video
    # (sequenza ordinata), quindi confrontare solo frame vicini nel tempo e' sufficiente
    # e molto piu' veloce di confrontare ogni coppia possibile (O(n^2)).
    subprocess.run(
        ["colmap", "sequential_matcher",
         "--database_path", str(database_path),
         "--SiftMatching.use_gpu", "0"],
        check=True, env=_CLI_ENV,
    )
    subprocess.run(
        ["colmap", "mapper", "--database_path", str(database_path), "--image_path", str(image_dir), "--output_path", str(sfm_path)],
        check=True, env=_CLI_ENV,
    )

    candidates = sorted(p for p in sfm_path.iterdir() if p.is_dir())
    if not candidates:
        raise RuntimeError(
            "Ricostruzione sparsa fallita: nessun modello generato. "
            "Servono piu' frame con overlap sufficiente tra loro."
        )

    def num_reg_images(path: Path) -> int:
        result = subprocess.run(
            ["colmap", "model_analyzer", "--path", str(path)],
            capture_output=True, text=True, env=_CLI_ENV,
        )
        for line in (result.stderr + result.stdout).splitlines():
            if "Registered images" in line:
                return int(line.split(":")[-1].strip())
        return 0

    return max(candidates, key=num_reg_images)
