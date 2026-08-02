#!/usr/bin/env bash
# Fase 2: dipendenze di build per OpenMVS (Eigen, Boost, OpenCV, CGAL, Ceres).
# Nessuna build precompilata di OpenMVS esiste per Linux ARM64: va compilato da sorgente (fase 3).
# Nota: serve libboost-all-dev (non i singoli pacchetti libboost-*-dev) perché CMake cerca
# anche componenti header-only come boost_exception, il cui file *Config.cmake è incluso
# solo nel pacchetto Boost completo.
set -e
export DEBIAN_FRONTEND=noninteractive

echo "=== Installazione dipendenze OpenMVS ==="
sudo -E apt install -y \
  libeigen3-dev \
  libboost-all-dev \
  libopencv-dev \
  libcgal-dev \
  libceres-dev \
  libnanoflann-dev \
  libtinyxml2-dev

echo ""
echo "=== FATTO: fase 2 ==="
