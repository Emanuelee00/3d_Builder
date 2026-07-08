from pathlib import Path

import trimesh
from PIL import Image


def finalize_glb(raw_glb_path: Path, output_path: Path) -> Path:
    """Corregge i limiti del glb esportato da OpenMVS:

    - la texture e' referenziata come file .png esterno anche dentro un .glb
      (non valido per il formato: un .glb dovrebbe essere autosufficiente) ->
      qui viene incorporata nel file.
    - manca l'attributo NORMAL sui vertici e il materiale e' marcato "unlit"
      (KHR_materials_unlit), quindi il modello appare piatto/senza colori
      ovunque tranne che nella stessa cartella dei file sorgente -> qui si
      ricalcolano le normali e si riesporta con un materiale PBR standard.
    """
    scene = trimesh.load(raw_glb_path, process=False)
    texture_path = raw_glb_path.parent / f"{raw_glb_path.stem}_0.png"

    for geom in scene.geometry.values():
        if texture_path.exists():
            geom.visual.material.baseColorTexture = Image.open(texture_path)
        geom.vertex_normals  # forza il calcolo e la cache delle normali

    output_path.parent.mkdir(parents=True, exist_ok=True)
    scene.export(output_path)
    return output_path
