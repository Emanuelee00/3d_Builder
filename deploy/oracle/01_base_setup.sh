#!/usr/bin/env bash
# Fase 1: sistema base, Node.js, firewall locale, clone del repo.
# Da eseguire sulla VM Oracle (Ubuntu 24.04 Minimal aarch64) come utente ubuntu.
set -e
export DEBIAN_FRONTEND=noninteractive

echo "=== 1/5: Aggiornamento sistema ==="
sudo -E apt update && sudo -E apt upgrade -y

echo "=== 2/5: Pacchetti base ==="
sudo -E apt install -y build-essential cmake git curl wget unzip pkg-config \
  python3 python3-venv python3-pip \
  libgl1 libglib2.0-0 ufw

echo "=== 3/5: Node.js LTS ==="
if ! command -v node >/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
  sudo -E apt install -y nodejs
else
  echo "Node.js già installato: $(node --version)"
fi

echo "=== 4/5: Firewall locale (ufw) ==="
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 3000/tcp
sudo ufw --force enable

echo "=== 5/5: Clona il repository ==="
if [ ! -d "$HOME/3D_visualizer" ]; then
  git clone https://github.com/Emanuelee00/3d_Builder.git "$HOME/3D_visualizer"
else
  echo "Cartella 3D_visualizer già esistente, salto il clone (fai 'git pull' se vuoi aggiornarla)."
fi

echo ""
echo "=== FATTO: fase 1 ==="
python3 --version
node --version
npm --version
