#!/usr/bin/env bash
# Fase 3: clona VCGLib + OpenMVS e compila da sorgente per Linux ARM64.
# Nessun binario precompilato disponibile per questa architettura (a differenza di Windows/Linux x64).
# Richiede che 02_openmvs_deps.sh sia già stato eseguito.
set -e

SRC_DIR="$HOME/openmvs_src"
mkdir -p "$SRC_DIR"
cd "$SRC_DIR"

echo "=== 1/5: Clona VCGLib ==="
if [ ! -d "vcglib" ]; then
  git clone https://github.com/cdcseacave/VCG.git vcglib
else
  echo "vcglib già presente, salto."
fi

echo "=== 2/5: Clona, compila e installa TinyEXIF ==="
# Non pacchettizzata su apt: nessun binario precompilato, va compilata (piccola libreria,
# pochi secondi). Richiede libtinyxml2-dev (installata in 02_openmvs_deps.sh).
if [ ! -d "TinyEXIF" ]; then
  git clone https://github.com/cdcseacave/TinyEXIF.git
fi
mkdir -p TinyEXIF/build
cd TinyEXIF/build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc)"
sudo make install
sudo ldconfig
cd "$SRC_DIR"

echo "=== 2b/5: Clona, compila e installa TinyNPY ==="
if [ ! -d "TinyNPY" ]; then
  git clone https://github.com/cdcseacave/TinyNPY.git
fi
mkdir -p TinyNPY/build
cd TinyNPY/build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc)"
sudo make install
sudo ldconfig
cd "$SRC_DIR"

echo "=== 2c/5: Clona, compila e installa PoseLib ==="
if [ ! -d "PoseLib" ]; then
  git clone https://github.com/PoseLib/PoseLib.git
fi
mkdir -p PoseLib/build
cd PoseLib/build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc)"
sudo make install
sudo ldconfig
cd "$SRC_DIR"

echo "=== 2d/5: Installa CGAL 6.x da sorgente (quello di apt e' 5.6, troppo vecchio) ==="
# Il codice usa header introdotti in CGAL 6 (es. AABB_traits_3.h, rinominato rispetto a
# CGAL 5). CGAL e' quasi interamente header-only quindi l'installazione e' veloce (non e'
# una vera compilazione pesante). Installato in /usr/local cosi' ha priorita' su quello di
# apt in /usr senza doverlo disinstallare.
if [ ! -d "cgal6" ]; then
  git clone --depth 1 --branch v6.0.1 https://github.com/CGAL/cgal.git cgal6
fi
mkdir -p cgal6/build
cd cgal6/build
cmake .. -DCMAKE_BUILD_TYPE=Release
sudo make install
cd "$SRC_DIR"

echo "=== 3/5: Clona OpenMVS ==="
if [ ! -d "openMVS" ]; then
  git clone https://github.com/cdcseacave/openMVS.git
else
  echo "openMVS già presente, salto (git pull manuale se serve aggiornare)."
fi

echo "=== 3b/5: Patch compatibilita' OpenCV 4.6 (IMWRITE_JPEGXL_QUALITY non esiste in questa versione) ==="
# OpenMVS assume una versione di OpenCV con supporto JPEG-XL; quella disponibile via apt su
# Ubuntu 24.04 (4.6.0) non ce l'ha (coerente con "libjxl not found" durante la configurazione).
# Rimuove il branch di salvataggio .jxl (mai usato dalla nostra pipeline).
TYPES_INL="$SRC_DIR/openMVS/libs/Common/Types.inl"
if grep -q "IMWRITE_JPEGXL_QUALITY" "$TYPES_INL"; then
  python3 - "$TYPES_INL" << 'PYEOF'
import sys
path = sys.argv[1]
with open(path, "r") as f:
    content = f.read()
old = '''\tif (ext == ".jxl") {
\t\tcompression_params.push_back(cv::IMWRITE_JPEGXL_QUALITY);
\t\tcompression_params.push_back(95);
\t} else
'''
if old in content:
    content = content.replace(old, "", 1)
    with open(path, "w") as f:
        f.write(content)
    print("Patch OpenCV/JPEG-XL applicata.")
else:
    print("ATTENZIONE: blocco atteso non trovato, patch saltata (verifica manualmente).")
PYEOF
else
  echo "Patch già applicata in precedenza, salto."
fi

echo "=== 3c/5: Patch compatibilita' OpenCV 4.6 (cv::SIFT::setContrastThreshold non esiste) ==="
# Aggiunto in una versione di OpenCV piu' recente della 4.6.0 disponibile via apt su Ubuntu
# 24.04. Ricrea il detector SIFT con la soglia desiderata invece di usare il setter mancante
# (stesso comportamento, cv::SIFT::create() e' gia' usato altrove nel file con gli stessi default).
SIFT_CPP="$SRC_DIR/openMVS/libs/SFM/FeaturesExtractor.cpp"
if grep -q "setContrastThreshold" "$SIFT_CPP"; then
  python3 - "$SIFT_CPP" << 'PYEOF'
import sys
path = sys.argv[1]
with open(path, "r") as f:
    content = f.read()

start_marker = "case FeatureType::SIFT: {"
start = content.find(start_marker)
end_marker = "} break;"
end = content.find(end_marker, start) + len(end_marker)
line_start = content.rfind("\n", 0, start) + 1
indent = content[line_start:start]

old_block = content[start:end]
if "setContrastThreshold" not in old_block:
    print("Patch gia' applicata in precedenza, salto.")
    sys.exit(0)

new_block = (
    "case FeatureType::SIFT: {\n"
    + indent + "\tconst double contrastThresholds[] = {0.03, 0.02, 0.015, 0.01, 0.005};\n"
    + indent + "\t// OpenCV su questa piattaforma non ha SIFT::setContrastThreshold(): si ricrea\n"
    + indent + "\t// il detector con la soglia desiderata invece di mutare quello esistente.\n"
    + indent + "\tcv::Ptr<cv::SIFT> sift = cv::SIFT::create(0, 3, contrastThresholds[retry]);\n"
    + indent + "\tsift->detectAndCompute(cellImage, cv::noArray(), cellKeypoints, cellDescriptors);\n"
    + indent + "} break;"
)
content = content[:start] + new_block + content[end:]
with open(path, "w") as f:
    f.write(content)
print("Patch SIFT applicata con successo.")
PYEOF
else
  echo "Patch già applicata in precedenza, salto."
fi

echo "=== 4/5: Configura con CMake ==="
# La build va fatta FUORI dalla cartella del sorgente: openMVS/build/ e' gia' usata dal
# repo stesso per script CMake interni (Utils.cmake ecc.), non e' la cartella di output.
mkdir -p "$SRC_DIR/build_output"
cd "$SRC_DIR/build_output"
cmake "$SRC_DIR/openMVS" \
  -DCMAKE_BUILD_TYPE=Release \
  -DVCG_ROOT="$SRC_DIR/vcglib" \
  -DOpenMVS_USE_CUDA=OFF \
  -DOpenMVS_ENABLE_VIEWER=OFF \
  -DCGAL_DIR=/usr/local/lib/cmake/CGAL

echo "=== 5/5: Compila (può richiedere 20-40+ minuti su 4 OCPU ARM) ==="
# La libreria SFM interna di OpenMVS (usata solo dai suoi tool di SfM alternativi a COLMAP,
# es. InterfacePolycam/KeyframeExtractor) puo' fallire per un'incompatibilita' API con
# PoseLib (estimate_relative_pose_bearings rinominata in versioni piu' recenti). La nostra
# pipeline non la usa (usiamo COLMAP per lo sparse, vedi sparse.py), quindi non e' bloccante:
# non interrompiamo la build su un singolo target fallito, verifichiamo invece a valle che i
# binari che ci servono davvero esistano.
make -j"$(nproc)" || true

BIN_DIR="$SRC_DIR/build_output/bin"
echo ""
echo "=== Verifica binari richiesti dalla pipeline ==="
MISSING=0
for exe in InterfaceCOLMAP DensifyPointCloud ReconstructMesh TextureMesh; do
  if [ -x "$BIN_DIR/$exe" ]; then
    echo "OK: $exe"
  else
    echo "MANCANTE: $exe"
    MISSING=1
  fi
done

if [ "$MISSING" -ne 0 ]; then
  echo "ERRORE: uno o piu' binari richiesti dalla pipeline non sono stati compilati."
  exit 1
fi

echo ""
echo "=== FATTO: fase 3 ==="
echo "Binari compilati in: $BIN_DIR"
ls -la "$BIN_DIR"
