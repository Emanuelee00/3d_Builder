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


# Sotto questa soglia (assoluta o relativa al totale delle immagini fornite) la point
# cloud sparsa e' cosi' povera che la fase densa/mesh crasha piu' avanti in modo criptico
# (es. "invalid PLY file" in OpenMVS) dopo aver gia' speso 1-2 minuti di CPU. Meglio
# fermarsi subito con un messaggio comprensibile: quasi sempre e' overlap insufficiente
# tra le viste (video troppo veloce, o foto scattate con angolazioni troppo distanti).
_MIN_REGISTERED_IMAGES = 3
_MIN_REGISTERED_RATIO = 0.25


def _check_registration_quality(num_registered: int, total_images: int) -> None:
    if num_registered >= _MIN_REGISTERED_IMAGES and num_registered >= total_images * _MIN_REGISTERED_RATIO:
        return
    raise RuntimeError(
        f"Solo {num_registered} immagini su {total_images} sono state registrate: "
        "troppo poca sovrapposizione tra le viste per una ricostruzione affidabile. "
        "Riprova girando piu' lentamente intorno all'oggetto (video) o scattando foto "
        "piu' ravvicinate tra loro, con buona sovrapposizione (foto)."
    )


def run_sparse_reconstruction(image_dir: Path, workspace_dir: Path, sequential: bool = True) -> Path:
    """SfM sparso: pose delle camere + point cloud sparsa. Gira su CPU.

    sequential: True per frame video (ordine = adiacenza spaziale, matcher sequenziale
    molto piu' veloce di quello esaustivo). False per foto scattate singolarmente, dove
    l'ordine di scatto non garantisce che due foto vicine nell'elenco siano vicine anche
    nello spazio - il matcher esaustivo (ogni coppia possibile) trova molte piu' coppie
    valide in quel caso, al costo di O(n^2) invece di O(n), accettabile per poche decine
    di foto.
    """
    database_path = workspace_dir / "database.db"
    sfm_path = workspace_dir / "sparse"

    if database_path.exists():
        database_path.unlink()
    if sfm_path.exists():
        shutil.rmtree(sfm_path)
    sfm_path.mkdir(parents=True)

    if pycolmap is not None:
        return _run_with_pycolmap(image_dir, database_path, sfm_path, sequential)
    return _run_with_cli(image_dir, database_path, sfm_path, sequential)


def _run_with_pycolmap(image_dir: Path, database_path: Path, sfm_path: Path, sequential: bool) -> Path:
    pycolmap.extract_features(database_path, image_dir)
    if sequential:
        pycolmap.match_sequential(database_path)
    else:
        pycolmap.match_exhaustive(database_path)
    reconstructions = pycolmap.incremental_mapping(database_path, image_dir, sfm_path)

    if not reconstructions:
        raise RuntimeError(
            "Ricostruzione sparsa fallita: nessun modello generato. "
            "Servono piu' frame con overlap sufficiente tra loro."
        )

    best_idx = max(reconstructions, key=lambda idx: reconstructions[idx].num_reg_images())
    total_images = len(list(image_dir.glob("*")))
    _check_registration_quality(reconstructions[best_idx].num_reg_images(), total_images)
    return sfm_path / str(best_idx)


def _run_with_cli(image_dir: Path, database_path: Path, sfm_path: Path, sequential: bool) -> Path:
    # use_gpu=0: niente GPU/OpenGL su questo server headless (SiftGPU richiede un
    # contesto OpenGL, che fallisce senza display: "Check failed: context_.create()").
    # Forza il fallback CPU (VLFeat) per estrazione e matching delle feature SIFT.
    subprocess.run(
        ["colmap", "feature_extractor",
         "--database_path", str(database_path), "--image_path", str(image_dir),
         "--SiftExtraction.use_gpu", "0"],
        check=True, env=_CLI_ENV,
    )
    # sequential_matcher per i video (l'ordine dei frame e' anche adiacenza spaziale,
    # molto piu' veloce di confrontare ogni coppia possibile). exhaustive_matcher per le
    # foto: l'ordine di scatto non garantisce vicinanza spaziale tra scatti consecutivi,
    # quindi serve confrontare tutte le coppie per trovare l'overlap che c'e' davvero.
    matcher_cmd = "sequential_matcher" if sequential else "exhaustive_matcher"
    subprocess.run(
        ["colmap", matcher_cmd,
         "--database_path", str(database_path),
         "--SiftMatching.use_gpu", "0"],
        check=True, env=_CLI_ENV,
    )
    try:
        subprocess.run(
            ["colmap", "mapper", "--database_path", str(database_path), "--image_path", str(image_dir), "--output_path", str(sfm_path)],
            check=True, env=_CLI_ENV,
        )
    except subprocess.CalledProcessError as e:
        # Con overlap troppo scarso tra le immagini, "colmap mapper" non trova nemmeno
        # una coppia iniziale valida e fallisce subito (way prima del controllo sotto
        # su candidates/num_reg_images) - stesso messaggio comprensibile, non il
        # CalledProcessError grezzo.
        raise RuntimeError(
            "Ricostruzione sparsa fallita: nessuna coppia di immagini con sovrapposizione "
            "sufficiente. Riprova girando piu' lentamente intorno all'oggetto (video) o "
            "scattando foto piu' ravvicinate tra loro, con buona sovrapposizione (foto)."
        ) from e

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

    best_path = max(candidates, key=num_reg_images)
    total_images = len(list(image_dir.glob("*")))
    _check_registration_quality(num_reg_images(best_path), total_images)
    return best_path
