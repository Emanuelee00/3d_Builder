from pathlib import Path

from PIL import Image
from rembg import new_session, remove

# u2netp (~4.5MB) invece del default u2net (~170MB): molto piu' leggero da eseguire
# su CPU senza GPU, qualita' sufficiente per isolare un oggetto in primo piano da
# uno sfondo relativamente semplice (non serve la precisione di un modello grande).
_MODEL_NAME = "u2netp"


def generate_masks(image_dir: Path, mask_dir: Path) -> Path:
    """Genera una maschera di primo piano per ogni immagine in image_dir.

    Le maschere finiscono in mask_dir con la convenzione attesa da OpenMVS
    (<nome_immagine_senza_estensione>.mask.png, 0 = sfondo da ignorare,
    255 = primo piano da tenere) cosi' la ricostruzione densa produce una
    mesh contenente solo l'oggetto, non lo sfondo intorno.
    """
    mask_dir.mkdir(parents=True, exist_ok=True)
    session = new_session(_MODEL_NAME)

    image_paths = sorted(image_dir.glob("*.jpg")) + sorted(image_dir.glob("*.png"))
    for i, image_path in enumerate(image_paths, start=1):
        print(f"Rimozione sfondo: {i}/{len(image_paths)} ({image_path.name})")
        img = Image.open(image_path)
        mask = remove(img, session=session, only_mask=True)
        mask_path = mask_dir / f"{image_path.stem}.mask.png"
        mask.save(mask_path)

    return mask_dir
