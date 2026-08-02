#!/usr/bin/env bash
# Fase 4: virtualenv Python + dipendenze della pipeline, sul repo clonato in fase 1
# ($HOME/3D_visualizer). pycolmap non ha wheel precompilate per Linux ARM64: se pip
# fallisce, si installa il binario CLI 'colmap' via apt (pacchetto ufficiale Ubuntu,
# compilato nativamente per arm64) e il codice della pipeline usa automaticamente
# quel fallback (vedi app/pipeline/sparse.py).
set -e
export DEBIAN_FRONTEND=noninteractive

cd "$HOME/3D_visualizer/app"

echo "=== 1/3: Crea virtualenv ==="
if [ ! -d "venv" ]; then
  python3 -m venv venv
else
  echo "venv già presente, salto la creazione."
fi
./venv/bin/pip install --upgrade pip -q

echo "=== 2/3: pycolmap (wheel) o colmap (CLI via apt) ==="
if ./venv/bin/pip install pycolmap -q 2>/dev/null; then
  echo "pycolmap installato via pip (wheel disponibile per questa architettura)."
else
  echo "Nessuna wheel pycolmap per questa architettura: installo il CLI 'colmap' via apt."
  sudo -E apt install -y colmap
  colmap --version || true
fi

echo "=== 3/3: Altre dipendenze della pipeline ==="
./venv/bin/pip install numpy opencv-python pillow trimesh jinja2

echo ""
echo "=== FATTO: fase 4 ==="
./venv/bin/python -c "
try:
    import pycolmap
    print('Sparse reconstruction: pycolmap Python', pycolmap.__version__)
except ImportError:
    print('Sparse reconstruction: CLI colmap (fallback)')
"
