# Setup server Oracle Cloud (Ampere A1, ARM64) — 3D Builder

Script per ricreare da zero l'ambiente sulla VM Oracle Free Tier (Ubuntu 24.04 Minimal
aarch64, VM.Standard.A1.Flex, 4 OCPU / 24GB RAM) se mai serve rifare tutto daccapo.

Ordine di esecuzione, sulla VM via SSH (`ssh -i ~/.ssh/oracle_3dbuilder ubuntu@<IP>`):

1. `01_base_setup.sh` — sistema, Node.js, firewall locale (ufw), clone del repo
2. `02_openmvs_deps.sh` — dipendenze di build per OpenMVS (Eigen, Boost, OpenCV, CGAL, Ceres)
3. `03_openmvs_build.sh` — compila OpenMVS da sorgente (nessuna build precompilata per ARM64; ~20-40 min)
4. `04_python_pipeline.sh` — venv Python + pycolmap (o fallback CLI `colmap` via apt, vedi sotto)
5. `05_webapp_setup.sh` — npm install/build della webapp + avvio persistente con pm2
6. `06_oracle_security_list.md` — **non è uno script**: passaggi manuali nella console Oracle per aprire le porte a livello di rete cloud (obbligatorio, altrimenti il sito non è raggiungibile da internet)

## Nota importante: pycolmap su ARM64

`pycolmap` (i binding Python di COLMAP) **non ha build precompilate per Linux ARM64** su
PyPI — solo x86_64. Compilarlo da sorgente sarebbe un lavoro enorme (richiede compilare
l'intero COLMAP C++ con tutte le sue dipendenze). Soluzione adottata: Ubuntu fornisce un
pacchetto **`colmap` precompilato per arm64** nei repo ufficiali (il tool CLI, non i
binding Python). `app/pipeline/sparse.py` prova prima a importare `pycolmap`; se non è
installato, usa automaticamente il CLI `colmap` via `subprocess` (stessi risultati, path
diverso). Su Windows (dove pycolmap ha wheel) il comportamento resta invariato.

## Copiare la chiave SSH su un nuovo PC

La chiave dedicata per questa VM è `~/.ssh/oracle_3dbuilder` (senza passphrase, generata
apposta per uso automatizzato — vedi CONTEXT.md per il perché). Se serve rifare il setup
da un altro PC, la chiave pubblica corrispondente deve essere già in
`~/.ssh/authorized_keys` sulla VM (aggiunta manualmente durante il primo setup).
