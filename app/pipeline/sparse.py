import shutil
from pathlib import Path

import pycolmap


def run_sparse_reconstruction(image_dir: Path, workspace_dir: Path) -> Path:
    """SfM sparso via pycolmap: pose delle camere + point cloud sparsa. Gira su CPU."""
    database_path = workspace_dir / "database.db"
    sfm_path = workspace_dir / "sparse"

    if database_path.exists():
        database_path.unlink()
    if sfm_path.exists():
        shutil.rmtree(sfm_path)
    sfm_path.mkdir(parents=True)

    pycolmap.extract_features(database_path, image_dir)
    pycolmap.match_exhaustive(database_path)
    reconstructions = pycolmap.incremental_mapping(database_path, image_dir, sfm_path)

    if not reconstructions:
        raise RuntimeError(
            "Ricostruzione sparsa fallita: nessun modello generato. "
            "Servono piu' frame con overlap sufficiente tra loro."
        )

    best_idx = max(reconstructions, key=lambda idx: reconstructions[idx].num_reg_images())
    return sfm_path / str(best_idx)
