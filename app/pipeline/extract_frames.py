from pathlib import Path

import cv2


def extract_frames(video_path: Path, output_dir: Path, target_frame_count: int = 60) -> Path:
    """Estrae un numero di frame all'incirca costante da un video, pronti per COLMAP.

    Si mira a un numero di frame totali (non a un fps fisso): un video corto
    di test e un video reale di 30s vengono campionati entrambi in modo
    ragionevole, invece di dover indovinare l'fps giusto caso per caso.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Impossibile aprire il video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or target_frame_count
    frame_interval = max(1, total_frames // target_frame_count)

    frame_idx = 0
    saved_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % frame_interval == 0:
            out_path = output_dir / f"frame_{saved_idx:05d}.jpg"
            cv2.imwrite(str(out_path), frame)
            saved_idx += 1
        frame_idx += 1
    cap.release()

    if saved_idx == 0:
        raise RuntimeError("Nessun frame estratto dal video.")
    return output_dir
