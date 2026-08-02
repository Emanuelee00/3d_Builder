from pathlib import Path

import numpy as np
import trimesh
from PIL import Image
from rembg import new_session, remove as rembg_remove

# Modello piccolo (~100MB), qualita' relativa sufficiente per un rilievo 2.5D. Gira in
# inferenza pura su CPU (nessun training) in pochi secondi per una singola immagine -
# non c'entra nulla con la lentezza di COLMAP/OpenMVS (quella scala con il numero di
# immagini, qui c'e' un solo forward pass su una immagine sola).
_DEPTH_MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"
_MASK_MODEL_NAME = "u2netp"  # stesso modello usato in remove_background.py, per coerenza


def run_monocular_reconstruction(
    image_path: Path,
    workspace_dir: Path,
    max_dimension: int = 400,
    relief_strength: float = 0.35,
    remove_background: bool = True,
) -> Path:
    """Da una singola immagine, genera un rilievo 2.5D texturizzato (.glb).

    A differenza di run_dense_reconstruction (che triangola tra piu' viste), qui non
    c'e' nessuna vera geometria 3D ricostruita: un modello di stima depth monoculare
    (una rete neurale pre-addestrata, usata solo in inferenza) assegna a ogni pixel un
    valore di "vicinanza", che viene usato per spostare in avanti/indietro una griglia
    di vertici presa direttamente dalla griglia dei pixel dell'immagine.

    Risultato: un rilievo che sembra corretto visto dalla stessa angolazione della
    foto originale, ma senza retro ne' lati (e' letteralmente uno sbalzo della singola
    vista, tipo bassorilievo/moneta) - non un oggetto pieno. Adatto quando serve solo
    "il piatto" e non l'intero oggetto (vedi CONTEXT.md: una foto singola non basta per
    una ricostruzione 3D completa, ma qui non e' quello che si sta cercando di fare).

    max_dimension: lato piu' lungo a cui viene ridotta l'immagine per calcolare depth-map
    e griglia della mesh (controlla anche il numero di vertici: max_dimension=400 produce
    tipicamente qualche decina di migliaia di vertici, pochi secondi di calcolo). La
    texture finale usa comunque l'immagine originale a piena risoluzione, non quella
    ridotta - solo la geometria e' a risoluzione piu' bassa.

    relief_strength: quanto e' pronunciato lo sbalzo, relativo al lato piu' lungo della
    griglia (0.35 = lo sbalzo massimo e' il 35% del lato piu' lungo). La depth stimata e'
    solo relativa (nessuna unita' fisica reale), quindi questo e' un fattore empirico,
    non una misura vera.

    remove_background: se True (default, coerente con run_dense_reconstruction), rimuove
    dal rilievo i vertici di sfondo con lo stesso modello (rembg/u2netp) gia' usato per
    il resto della pipeline, cosi' il risultato e' solo l'oggetto in primo piano.
    """
    workspace_dir.mkdir(parents=True, exist_ok=True)

    img_orig = Image.open(image_path).convert("RGB")
    img_small = img_orig.copy()
    img_small.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
    width, height = img_small.size

    # Niente contatori "[n/m]" qui dentro: run_pipeline.py stampa gia' i propri
    # (es. "[1/2]") per questa modalita' - un secondo schema con un denominatore
    # diverso confonderebbe progressFromLog() nella webapp (regex sugli step).
    print(f"Stima depth monoculare ({width}x{height})")
    depth = _estimate_depth(img_small)
    depth_norm = (depth - depth.min()) / (depth.max() - depth.min() + 1e-8)

    mask = None
    if remove_background:
        print("Rimozione sfondo")
        mask = _estimate_foreground_mask(img_small)

    print("Costruzione mesh + texture")
    glb_path = workspace_dir / "scene_final.glb"
    _build_relief_mesh(
        depth_norm, img_orig, mask, relief_strength=relief_strength
    ).export(glb_path)
    return glb_path


def _estimate_depth(image: Image.Image) -> np.ndarray:
    from transformers import pipeline

    depth_pipe = pipeline(task="depth-estimation", model=_DEPTH_MODEL_ID)
    result = depth_pipe(image)
    return result["predicted_depth"].squeeze().cpu().numpy().astype(np.float32)


def _estimate_foreground_mask(image: Image.Image) -> np.ndarray:
    session = new_session(_MASK_MODEL_NAME)
    mask_img = rembg_remove(image, session=session, only_mask=True)
    return np.array(mask_img) > 127


def _build_relief_mesh(
    depth_norm: np.ndarray,
    texture_image: Image.Image,
    mask: np.ndarray | None,
    relief_strength: float,
) -> trimesh.Trimesh:
    height, width = depth_norm.shape
    long_side = max(width, height)

    ys, xs = np.meshgrid(np.arange(height), np.arange(width), indexing="ij")
    # Griglia centrata nell'origine, normalizzata cosi' che il lato piu' lungo
    # dell'immagine misuri 1 unita' (scala arbitraria ma coerente in se stessa).
    x = (xs / (width - 1) - 0.5) * (width / long_side)
    # Y invertita: la riga 0 dell'immagine (in alto) deve corrispondere a "su" nel
    # mondo 3D (Y positiva), non a Y negativa come sarebbe con le righe immagine.
    y = -(ys / (height - 1) - 0.5) * (height / long_side)
    z = depth_norm * relief_strength

    vertices_all = np.stack([x, y, z], axis=-1).reshape(-1, 3).astype(np.float32)
    # Convenzione glTF: UV (0,0) e' l'angolo in alto a sinistra dell'immagine
    # sorgente, quindi v = riga/altezza senza flip verticale.
    uv_all = np.stack([xs / (width - 1), ys / (height - 1)], axis=-1).reshape(-1, 2).astype(np.float32)

    faces_all = _grid_faces(width, height)
    if mask is not None:
        mask_flat = mask.ravel()
        faces_all = faces_all[mask_flat[faces_all].all(axis=1)]
        if len(faces_all) == 0:
            raise RuntimeError(
                "Nessun pixel di primo piano rilevato: la rimozione sfondo ha scartato "
                "l'intera immagine. Riprova con una foto dove l'oggetto si distingue "
                "chiaramente dallo sfondo."
            )

    # Tiene solo i vertici effettivamente usati da qualche faccia (scarta lo sfondo
    # tagliato via sopra), rimappando gli indici delle facce di conseguenza.
    used = np.unique(faces_all)
    remap = -np.ones(len(vertices_all), dtype=np.int64)
    remap[used] = np.arange(len(used))
    vertices = vertices_all[used]
    uv = uv_all[used]
    faces = remap[faces_all]

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    if mesh.face_normals.mean(axis=0)[2] < 0:
        # Le normali guardano lontano dalla camera invece che verso di essa:
        # verso di percorrenza dei triangoli invertito rispetto all'atteso.
        faces = faces[:, ::-1]
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

    # Senza questo, il bordo della sagoma e' uno spigolo vivo a spessore zero: visto
    # di lato sembra un ritaglio di carta piatto invece che un rilievo solido. Aggiunge
    # una piccola "parete" di spessore uniforme lungo tutto il contorno (non un foglio
    # sospeso nel vuoto).
    vertices, uv, faces = _add_rim(vertices, uv, faces)

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    material = trimesh.visual.material.PBRMaterial(baseColorTexture=texture_image)
    mesh.visual = trimesh.visual.texture.TextureVisuals(uv=uv, image=texture_image, material=material)
    mesh.vertex_normals  # forza il calcolo (altrimenti il materiale risulta "unlit")
    return mesh


def _add_rim(
    vertices: np.ndarray, uv: np.ndarray, faces: np.ndarray, rim_depth: float = 0.05
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Chiude il contorno aperto del rilievo con una parete di spessore uniforme.

    Il rilievo di partenza e' una superficie singola (niente retro): il suo contorno
    (dove la maschera taglia via lo sfondo) e' un bordo aperto a spessore zero. Qui si
    trovano gli spigoli di quel bordo (quelli usati da un solo triangolo, non condiviso
    tra due) e per ognuno si aggiunge un vertice "gemello" leggermente dietro (stessa
    X/Y, Z spostata indietro di rim_depth rispetto a QUEL punto - non verso un'unica
    base piatta comune: un oggetto come un mouse ha punti del contorno ad altezze molto
    diverse, dalla cupola al piano d'appoggio, e una base condivisa creerebbe pareti a
    "pettine" invece di un bordo sottile e uniforme). Non e' lo spessore vero di un
    oggetto pieno (quello richiederebbe di conoscere anche il retro, che qui non esiste).
    """
    directed_edges = faces[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2)
    edge_set = {(int(a), int(b)) for a, b in directed_edges}
    boundary = np.array(
        [(a, b) for a, b in directed_edges if (int(b), int(a)) not in edge_set]
    )
    if len(boundary) == 0:
        return vertices, uv, faces  # bordo chiuso (non dovrebbe succedere qui), niente da fare

    boundary_verts = np.unique(boundary.ravel())
    back_of = -np.ones(len(vertices), dtype=np.int64)
    back_of[boundary_verts] = np.arange(len(boundary_verts)) + len(vertices)

    # Spessore fisso relativo a OGNI vertice del bordo (non un'unica base piatta
    # globale): un oggetto come un mouse ha punti del contorno ad altezze molto
    # diverse (in alto sulla cupola, in basso sul piano d'appoggio) - una base
    # comune li collegherebbe tutti a distanze diversissime, creando pareti a
    # "pettine" invece di un bordo sottile e uniforme.
    back_vertices = vertices[boundary_verts].copy()
    back_vertices[:, 2] -= rim_depth
    back_uv = uv[boundary_verts]

    a, b = boundary[:, 0], boundary[:, 1]
    a_back, b_back = back_of[a], back_of[b]
    wall_faces = np.concatenate(
        [np.stack([a, b, a_back], axis=1), np.stack([b, b_back, a_back], axis=1)], axis=0
    )

    # Il verso di percorrenza del bordo (e quindi la vera direzione "verso l'esterno"
    # della parete) dipende dalla forma della sagoma - invece di derivarlo a mano,
    # si prova un verso e si controlla se le normali risultanti puntano lontano dal
    # centro della sagoma (proiettato su XY); se puntano verso l'interno, si inverte.
    all_vertices = np.concatenate([vertices, back_vertices], axis=0)
    wall_normals = trimesh.Trimesh(vertices=all_vertices, faces=wall_faces, process=False).face_normals
    outward_xy = all_vertices[wall_faces].mean(axis=1)[:, :2] - vertices[:, :2].mean(axis=0)
    if (wall_normals[:, :2] * outward_xy).sum(axis=1).mean() < 0:
        wall_faces = wall_faces[:, ::-1]

    all_uv = np.concatenate([uv, back_uv], axis=0)
    all_faces = np.concatenate([faces, wall_faces], axis=0)
    return all_vertices, all_uv, all_faces


def _grid_faces(width: int, height: int) -> np.ndarray:
    ys, xs = np.meshgrid(np.arange(height - 1), np.arange(width - 1), indexing="ij")
    v00 = (ys * width + xs).ravel()
    v01 = (ys * width + xs + 1).ravel()
    v10 = ((ys + 1) * width + xs).ravel()
    v11 = ((ys + 1) * width + xs + 1).ravel()
    tri_a = np.stack([v00, v10, v01], axis=1)
    tri_b = np.stack([v01, v10, v11], axis=1)
    return np.concatenate([tri_a, tri_b], axis=0)
