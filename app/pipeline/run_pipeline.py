import argparse
import time
from pathlib import Path

from .codegen import generate_preview_html, generate_r3f_component
from .config import OUTPUT_ROOT
from .dense import run_dense_reconstruction
from .extract_frames import extract_frames
from .finalize_mesh import finalize_glb
from .sparse import run_sparse_reconstruction


# Lega il preset di qualita' gia' scelto in UI (che sceglie il numero di frame) anche
# al resolution-level di OpenMVS: la fase densa (depth-map su ogni frame) e' quella piu'
# lenta della pipeline, quindi "Veloce" deve alleggerire anche quella, non solo i frame.
def _resolution_level_for(target_frame_count: int) -> int:
    if target_frame_count <= 30:
        return 2  # immagini a 1/4 risoluzione: molto piu' veloce, meno dettaglio
    if target_frame_count <= 60:
        return 1  # default OpenMVS: meta' risoluzione
    return 0  # risoluzione piena: piu' lento, massimo dettaglio


def run(
    video_path: Path | None = None,
    job_name: str | None = None,
    target_frame_count: int = 60,
    images_dir: Path | None = None,
) -> Path:
    """video_path (estrazione frame) e images_dir (foto gia' pronte, una per scatto)
    sono alternativi tra loro: specificare esattamente uno dei due."""
    if (video_path is None) == (images_dir is None):
        raise ValueError("Specificare esattamente uno tra video_path e images_dir")

    job_name = job_name or f"job_{int(time.time())}"
    workspace_dir = OUTPUT_ROOT / job_name
    web_dir = workspace_dir / "web"

    if video_path is not None:
        images_dir_final = workspace_dir / "images"
        print(f"[1/5] Estrazione frame da {video_path} -> {images_dir_final}")
        extract_frames(video_path, images_dir_final, target_frame_count=target_frame_count)
    else:
        images_dir_final = images_dir
        n_photos = len(list(images_dir_final.glob("*")))
        print(f"[1/5] Uso {n_photos} foto gia' pronte da {images_dir_final} (nessuna estrazione da video)")

    print("[2/5] Ricostruzione sparsa (pycolmap, CPU)")
    sparse_model_path = run_sparse_reconstruction(images_dir_final, workspace_dir)

    resolution_level = _resolution_level_for(target_frame_count)
    print(f"[3/5] Ricostruzione densa + mesh + texture (OpenMVS, CPU, resolution-level={resolution_level})")
    raw_glb_path = run_dense_reconstruction(
        images_dir_final, sparse_model_path, workspace_dir, resolution_level=resolution_level
    )

    print("[4/5] Correzione glb (texture incorporata + normali)")
    glb_path = finalize_glb(raw_glb_path, workspace_dir / "scene_final.glb")

    print("[5/5] Generazione componente React Three Fiber + anteprima HTML")
    component_path = generate_r3f_component(glb_path, web_dir)
    preview_path = generate_preview_html(glb_path.name, web_dir)

    print(f"\nFatto. Componente generato in: {component_path}")
    print(f"Anteprima (apri nel browser via server locale): {preview_path}")
    return component_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Video/foto -> ricostruzione 3D -> componente Three.js")
    parser.add_argument(
        "video", type=Path, nargs="?", default=None,
        help="Percorso del file video di input (alternativo a --images-dir)",
    )
    parser.add_argument(
        "--images-dir", type=Path, default=None,
        help="Cartella con foto gia' pronte (una per scatto), alternativa al video",
    )
    parser.add_argument("--job-name", type=str, default=None, help="Nome della cartella di output")
    parser.add_argument(
        "--frames", type=int, default=60,
        help="Numero di frame totali da estrarre dal video (con --images-dir, usato solo per "
        "scegliere la risoluzione di ricostruzione: 30/60/90 = veloce/bilanciato/dettagliato)",
    )
    args = parser.parse_args()

    if (args.video is None) == (args.images_dir is None):
        parser.error("specificare esattamente uno tra 'video' e --images-dir")

    run(
        video_path=args.video,
        job_name=args.job_name,
        target_frame_count=args.frames,
        images_dir=args.images_dir,
    )


if __name__ == "__main__":
    main()
