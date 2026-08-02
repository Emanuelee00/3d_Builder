#!/usr/bin/env bash
# Fase 5: installa le dipendenze della webapp Next.js e la avvia in background con pm2
# (riparte da solo se crasha o dopo un riavvio della VM, se configurato con pm2 startup).
set -e
export DEBIAN_FRONTEND=noninteractive

cd "$HOME/3D_visualizer/webapp"

echo "=== 1/3: npm install ==="
npm install

echo "=== 2/3: Build produzione ==="
npm run build

echo "=== 3/3: Avvio con pm2 ==="
if ! command -v pm2 >/dev/null; then
  sudo npm install -g pm2
fi
pm2 delete 3d-builder-web 2>/dev/null || true
pm2 start npm --name 3d-builder-web -- start
pm2 save

echo ""
echo "=== FATTO: fase 5 ==="
echo "Per far ripartire pm2 automaticamente dopo un riavvio della VM, esegui una volta:"
echo "  pm2 startup   (poi copia/incolla il comando sudo che stampa)"
echo ""
echo "Sito raggiungibile su: http://<IP_PUBBLICO_VM>:3000  (dopo aver aperto la porta 3000"
echo "anche nella Security List di Oracle, vedi 06_oracle_security_list.md)"
