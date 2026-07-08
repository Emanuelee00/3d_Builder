from pathlib import Path

from jinja2 import Template

_COMPONENT_TEMPLATE = Template(
    """import { useGLTF } from '@react-three/drei'

export function {{ component_name }}(props) {
  const { scene } = useGLTF('/models/{{ glb_filename }}')
  return <primitive object={scene} {...props} />
}

useGLTF.preload('/models/{{ glb_filename }}')
"""
)

_PREVIEW_HTML_TEMPLATE = Template(
    """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Anteprima modello ricostruito</title>
  <script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
  <style>
    html, body { margin: 0; height: 100%; background: #222; }
    model-viewer { width: 100%; height: 100%; }
  </style>
</head>
<body>
  <model-viewer
    src="models/{{ glb_filename }}"
    camera-controls
    auto-rotate
    shadow-intensity="1"
    exposure="1"
    style="background-color: #333">
  </model-viewer>
</body>
</html>
"""
)


def generate_preview_html(glb_filename: str, output_dir: Path) -> Path:
    """Pagina HTML standalone (model-viewer via CDN) per vedere il .glb senza Node/npm."""
    preview_path = output_dir / "preview.html"
    preview_path.write_text(
        _PREVIEW_HTML_TEMPLATE.render(glb_filename=glb_filename), encoding="utf-8"
    )
    return preview_path


def generate_r3f_component(glb_path: Path, output_dir: Path, component_name: str = "ScannedModel") -> Path:
    """Genera un componente React Three Fiber che carica il .glb ricostruito.

    Nota: il modello e' un'unica mesh fusa (nessuna separazione automatica in
    componenti nominati, che richiederebbe un passo di segmentazione a parte).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    models_dir = output_dir / "models"
    models_dir.mkdir(exist_ok=True)

    dest_glb = models_dir / glb_path.name
    dest_glb.write_bytes(glb_path.read_bytes())

    component_path = output_dir / f"{component_name}.jsx"
    component_path.write_text(
        _COMPONENT_TEMPLATE.render(component_name=component_name, glb_filename=glb_path.name),
        encoding="utf-8",
    )
    return component_path
