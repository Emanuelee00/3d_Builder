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


def run(video_path: Path, job_name: str | None = None, target_frame_count: int = 60) -> Path:
    job_name = job_name or f"job_{int(time.time())}"
    workspace_dir = OUTPUT_ROOT / job_name
    images_dir = workspace_dir / "images"
    web_dir = workspace_dir / "web"

    print(f"[1/5] Estrazione frame da {video_path} -> {images_dir}")
    extract_frames(video_path, images_dir, target_frame_count=target_frame_count)

    print("[2/5] Ricostruzione sparsa (pycolmap, CPU)")
    sparse_model_path = run_sparse_reconstruction(images_dir, workspace_dir)

    resolution_level = _resolution_level_for(target_frame_count)
    print(f"[3/5] Ricostruzione densa + mesh + texture (OpenMVS, CPU, resolution-level={resolution_level})")
    raw_glb_path = run_dense_reconstruction(
        images_dir, sparse_model_path, workspace_dir, resolution_level=resolution_level
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
    parser = argparse.ArgumentParser(description="Video -> ricostruzione 3D -> componente Three.js")
    parser.add_argument("video", type=Path, help="Percorso del file video di input")
    parser.add_argument("--job-name", type=str, default=None, help="Nome della cartella di output")
    parser.add_argument(
        "--frames", type=int, default=60, help="Numero di frame totali da estrarre dal video"
    )
    args = parser.parse_args()

    run(args.video, job_name=args.job_name, target_frame_count=args.frames)


if __name__ == "__main__":
    main()
