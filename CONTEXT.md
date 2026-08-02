# 3D Builder — contesto del progetto

Utility che trasforma un video (o foto multiple) in un modello 3D texturizzato, esportato come asset `.glb` + componente React Three Fiber pronto per il web.

## Idea di partenza

Da una conversazione esplorativa: l'obiettivo iniziale era capire se fosse fattibile creare uno strumento che trasforma foto/video in codice Three.js strutturato. Conclusioni chiave di quella discussione:

- **Foto singola → 3D**: non fattibile in modo affidabile senza AI (nessuna geometria ricavabile da un'unica immagine) **per un modello completo** (con retro/lati). Rivisitato più avanti con uno scopo volutamente più modesto: un rilievo 2.5D solo del lato fotografato (vedi sezione dedicata sotto) — lì l'AI (depth monoculare) è accettata perché il prodotto non promette più un oggetto pieno.
- **Video → 3D senza AI**: fattibile con fotogrammetria classica (Structure-from-Motion + Multi-View Stereo). Il video (o una serie di foto) risolve il problema di avere molte viste della stessa scena.
- **Separazione in "componenti nominati"** (es. "questo è il tavolo", "questa è la sedia"): richiederebbe un modello di segmentazione AI, non implementato — il risultato attuale è **una singola mesh fusa**, non oggetti separati.
- **Business**: mercato saturo di alternative gratuite (Polycam, Scaniverse, RealityScan). L'idea più promettente è una nicchia verticale con export web strutturato (es. arredamento/immobiliare) invece di competere sulla ricostruzione generica.

## Architettura

```
app/                    Pipeline Python (video/foto -> mesh 3D)
  pipeline/
    extract_frames.py    Video -> frame JPG (numero di frame target, non fps fisso)
    sparse.py            pycolmap (o CLI colmap su ARM64): pose camere + point cloud sparsa (CPU)
    remove_background.py Segmentazione primo piano/sfondo per frame (rembg, CPU)
    dense.py             OpenMVS: point cloud densa (con maschere sfondo) -> mesh -> texture (CPU)
    monocular.py          Alternativa da una sola foto: depth monoculare (AI, solo inferenza)
                          -> rilievo 2.5D texturizzato (niente retro/lati, vedi sezione dedicata)
    finalize_mesh.py     Corregge il glb di OpenMVS (vedi bug noti sotto)
    codegen.py           Genera componente React Three Fiber + preview.html standalone
    run_pipeline.py      Orchestratore CLI end-to-end
  venv/                 Virtualenv Python 3.12 (non in git)
  tools/OpenMVS/        Binari OpenMVS Windows precompilati (solo per sviluppo locale Windows; su Linux/ARM64 si compila da sorgente, vedi sotto)

webapp/                 Sito Next.js (viewer + capture da telefono)
  app/page.tsx           Homepage: viewer 3D + pannello codice generato
  app/capture/page.tsx   Pagina cattura da telefono: toggle Video / Foto multiple / Foto singola
  app/api/upload/        Riceve il video, lancia la pipeline Python come child process
  app/api/status/[id]/   Polling stato job (basato su file, non in-memory - vedi bug noti)
  app/api/models/        Elenca i modelli generati (per il selettore nella homepage)
  lib/jobs.ts            Gestione job: stato su disco in app/job-status/*.json
  components/            ModelViewer (Canvas R3F), ScannedModel (loader glb), CodePanel, Nav

deploy/oracle/          Script di provisioning per il deploy su Oracle Cloud (vedi sotto)
colmap/                 Clone di riferimento (solo esempi/documentazione, NON usato in produzione — si usa pycolmap via pip, o CLI colmap su ARM64)
```

## Ambienti: sviluppo locale (Windows) vs produzione (Oracle Cloud ARM64)

Il progetto è stato inizialmente sviluppato in locale su Windows (Intel Arc integrata, niente CUDA), poi **deployato su una VM Oracle Cloud ARM64 (Ampere, aarch64)** raggiungibile pubblicamente:

- **Sito**: `http://<IP_PUBBLICO_VM>:3000` — gestito da **pm2** (processo `3d-builder-web`), non da `npm run dev`.
- **Rebuild + restart dopo una modifica alla webapp**: `~/rebuild_webapp.sh` (build produzione + `pm2 restart`).
- **Attenzione**: un `pm2 restart` uccide anche il child process Python di un job eventualmente in corso (nessuna sopravvivenza al riavvio del processo padre) — il job resta bloccato per sempre su `"processing"` nel suo file di stato se questo succede. Evitare restart mentre uno scan è attivo; se capita, il job va marcato manualmente `"error"` nel suo file in `app/job-status/`.
- Su questa VM **non esiste una wheel pycolmap per Linux ARM64**: `sparse.py` fa fallback automatico al binario CLI `colmap` (pacchetto apt) se l'import Python fallisce.
- OpenMVS **non è precompilato per ARM64**: va **compilato da sorgente** (vedi `deploy/oracle/02_openmvs_deps.sh` e `03_openmvs_build.sh`, sorgenti in `~/openmvs_src/`, binari in `~/openmvs_src/build_output/bin/`). `config.py` sceglie il percorso giusto in base a `platform.system()`.
- VM: 4 vCPU, 23GB RAM, nessuna GPU (nemmeno integrata) — tutta la pipeline è CPU-only.
- Il comando `colmap` di apt è compilato con supporto Qt/GUI e crasha (SIGABRT) su un server headless senza display se non si forza `QT_QPA_PLATFORM=offscreen` (vedi `_CLI_ENV` in `sparse.py`/`dense.py`).

## Vincoli hardware importanti

- **Nessuna GPU** sulla VM di produzione (CPU-only anche per sviluppo locale originale, niente CUDA). COLMAP non ha fallback CPU per `patch_match_stereo`, quindi la ricostruzione densa passa **interamente da OpenMVS** (che supporta CPU) invece che dal modulo dense nativo di COLMAP.
- Python **3.12** richiesto (non 3.13): `pycolmap` e `open3d` non hanno ancora wheel per 3.13.
- OpenMVS: `https://github.com/cdcseacave/openMVS/releases` per Windows; su Linux/ARM64 si compila da sorgente (vedi sopra).

## Rimozione sfondo automatica

Ogni scan rimuove automaticamente lo sfondo dalla ricostruzione finale (non è un crop successivo — lo sfondo non entra mai nella mesh):

1. Dopo l'undistort delle immagini (in `dense.py`), `remove_background.py` genera una maschera di primo piano per ogni frame con **rembg** (modello `u2netp`, ~4.5MB, CPU, ~0.9s/frame).
2. La maschera (convenzione OpenMVS: `<mask-path>/<nome_immagine_senza_estensione>.mask.png`, 0 = sfondo, 255 = primo piano) viene passata a `DensifyPointCloud` con `--mask-path` e `--ignore-mask-label 0` (di default il masking è disattivato, va esplicitamente abilitato con questo flag).
3. Risultato: la point cloud densa (e quindi mesh + texture) contiene solo l'oggetto in primo piano.
4. `remove_background: bool = True` è un parametro di `run_dense_reconstruction()` — disattivabile se necessario.
5. Limite noto: efficace su oggetti opachi con sfondo semplice; su oggetti piccoli/trasparenti/riflettenti (es. occhiali) il problema principale resta la ricostruzione stessa (vedi sotto), non la rimozione sfondo.

## Rilievo 2.5D da foto singola (`monocular.py`)

Terza modalità di input (oltre a video e foto multiple), pensata per quando serve solo
"il lato fotografato" e non l'intero oggetto — niente multi-vista, quindi niente
SfM/MVS (COLMAP/OpenMVS non entrano in gioco):

1. Un modello di **stima depth monoculare** pre-addestrato (**Depth Anything V2
   Small**, via `transformers`, solo inferenza — nessun training) assegna a ogni
   pixel un valore di vicinanza relativo. Su CPU ARM64: ~6s per caricare i pesi la
   prima volta, poi ~1-6s per immagine.
2. `remove_background.py` (stesso rembg/u2netp del resto della pipeline) isola
   l'oggetto dallo sfondo.
3. La depth normalizzata sposta una griglia di vertici presa dai pixel
   dell'immagine (heightfield); i vertici di sfondo vengono scartati. La foto
   originale (piena risoluzione, non quella ridotta usata per calcolare la
   griglia) diventa la texture via UV diretta.
4. Risultato: pochi secondi totali (contro l'ora+ della pipeline multi-vista),
   ma è **un bassorilievo, non un oggetto pieno** — visto da un'angolazione
   troppo diversa da quella originale si vede che dietro non c'è nulla. Non è
   un bug: è esattamente il compromesso implicito nel fare 3D da una sola foto
   senza multi-vista (vedi "Idea di partenza" sopra).
5. CLI: `run_pipeline.py --single-image percorso/foto.jpg --job-name nome_job`
   (mutualmente esclusivo con `video`/`--images-dir`). Webapp: terza opzione
   "Foto singola" in `/capture` (niente selettore qualità, non si applica).
6. `run_pipeline.py` stampa i propri marcatori `[1/2]`/`[2/2]` per questa
   modalità; `monocular.py` non stampa contatori propri per non confondere
   `progressFromLog()` nella webapp (regex generica su `[n/m]`, non più
   hardcoded su `/5`).

## Velocità: preset qualità legato alla risoluzione OpenMVS

Il selettore "Qualità ricostruzione" in `/capture` (Veloce/Bilanciato/Dettagliato) sceglie sia il numero di frame estratti dal video sia il `--resolution-level` di `DensifyPointCloud` (fase più lenta della pipeline, `_resolution_level_for()` in `run_pipeline.py`):

| Preset | Frame | resolution-level | Effetto |
|---|---|---|---|
| Veloce | 30 | 2 (1/4 risoluzione) | Molto più rapido, meno dettaglio |
| Bilanciato | 60 | 1 (default OpenMVS) | — |
| Dettagliato | 90 | 0 (risoluzione piena) | Più lento, massimo dettaglio |

## Limiti noti della tecnica (non bug, limiti intrinseci)

Oggetti piccoli, trasparenti o riflettenti (es. occhiali) ricostruiscono male con fotogrammetria classica: SIFT non trova punti stabili su superfici trasparenti/riflettenti (i riflessi cambiano con l'angolazione), e strutture sottili si fondono in blob nella mesh densa. Non risolvibile con tuning — servirebbe una tecnica diversa (scanner a luce strutturata, o modello AI per oggetti trasparenti). Testare la pipeline su oggetti opachi con texture per verificare la qualità.

## Bug reali trovati e risolti (da tenere a mente)

1. **`DensifyPointCloud.exe` con `-o`/`--cuda-device` espliciti** → fallisce silenziosamente (exit 1, nessun log). Risolto usando solo i default (sceglie CPU in automatico). Vedi `dense.py`.
2. **Mesh troppo frammentata → crash in `TextureMesh`** (access violation) per troppe micro-patch texture. Risolto decimando la mesh (`--decimate 0.2`) prima della texturizzazione.
3. **Crash intermittente in `DensifyPointCloud`** con troppi thread in parallelo. Risolto limitando `--max-threads 4`.
4. **Il `.glb` esportato da OpenMVS non ha normali ed è "unlit"**, con la texture come **PNG esterno** (non incorporato — invalido per un `.glb` vero). Corretto in `finalize_mesh.py`: ricarica con trimesh, ricalcola le normali, riassocia la texture manualmente, riesporta un `.glb` autosufficiente con materiale PBR standard.
5. **Estrazione frame a fps fisso** non si adattava a video di lunghezza diversa (video corti = troppo pochi frame). Cambiato a target sul **numero totale di frame** (default 60), calcolato in base alla durata reale.
6. **Stato dei job in memoria (`Map` in `lib/jobs.ts`) perso tra le richieste** in Next.js dev mode (i moduli delle API route si re-instanziano). Risolto scrivendo lo stato su file JSON (`app/job-status/<jobId>.json`) invece che in una variabile di modulo.
7. **Sfondo bianco invece che scuro su alcuni dispositivi/temi**: `globals.css` conteneva il boilerplate di default di `create-next-app` (`body { background: var(--background) }`, bianco in light mode) fuori da un `@layer` di Tailwind. In Tailwind v4 il CSS non "layerizzato" vince sempre sulle utility class (es. `bg-[#09090b]` su `<body>` in `layout.tsx`), indipendentemente da specificità/ordine — risultato: testo bianco invisibile su sfondo bianco quando il dispositivo non è in dark mode. Risolto rimuovendo il blocco boilerplate morto (nessun componente usava `bg-background`/`text-foreground`).
8. **Job bloccato per sempre su "processing"**: se il file di stato del job (`app/job-status/<id>.json`) sparisce o resta a "processing" (es. per un riavvio del server che uccide il child process Python), il client restava bloccato a mostrare quello stato per sempre, senza modo di uscirne — niente pulsante "nuovo scan" durante il polling, e un 404 sullo status veniva comunque interpretato come "ancora in corso". Risolto in `capture/page.tsx`: un 404 (job sparito) riporta a "idle", e il pulsante "Annulla / nuovo scan" è ora visibile anche durante "processing".
9. **Barra di progresso sempre a 0%**: i marcatori di fase `[N/5]` sono stampati da Python con `print()`, ma quando lo stdout non è un TTY (spawn da Node) Python usa **buffering a blocchi** invece che a riga — i print restano bloccati nel buffer mentre l'output diretto di COLMAP/OpenMVS (che scrive sul file descriptor, bypassando il buffer Python) arriva subito. Risolto lanciando Python con `-u` (unbuffered) in `lib/jobs.ts`.
10. **`WebGL context was lost` / pagina che sembra "non caricare"**: il rendering 3D (`ModelViewer.tsx`) può fallire su alcuni browser/ambienti (rendering software senza vera GPU, es. sessioni remote/VM). Mitigato con: `dpr` limitato, shadow map disattivata, `Environment` più leggera (`apartment` invece di `city`, bassa risoluzione), un listener su `webglcontextlost` che mostra un messaggio recuperabile invece di uno schermo nero, e un **error boundary React** attorno al `Canvas` (un errore di parsing/rendering non catturato da Suspense mandava in crash l'intera pagina).
11. **Nessun feedback durante l'upload del video**: `fetch()` non espone il progresso di upload. Risolto passando a `XMLHttpRequest` con `upload.onprogress` in `capture/page.tsx`.
12. **Crash criptico e lento su overlap insufficiente tra le viste**: se troppo poche immagini si sovrappongono a sufficienza (video troppo veloce, o foto scattate con angolazioni troppo distanti), COLMAP registra solo 1-2 immagini su tutte quelle fornite, producendo una point cloud quasi vuota — la pipeline proseguiva comunque per 1-2 minuti fino a schiantarsi in modo criptico su OpenMVS (`TextureMesh: invalid PLY file`). Risolto con un controllo fail-fast in `sparse.py` (`_check_registration_quality`) subito dopo la ricostruzione sparsa: se le immagini registrate sono troppo poche (< 3 o < 25% del totale), solleva subito un errore comprensibile invece di continuare.
13. **Errore mostrato all'utente poco informativo** ("Pipeline terminata con codice 1"): `lib/jobs.ts` ora cerca l'ultimo messaggio di eccezione Python (`RuntimeError`/`ValueError`/`Exception`) nel log e lo mostra al posto del codice di uscita nudo (`extractErrorMessage`).

## Stato attuale

- Deployato e testato su VM Oracle Cloud ARM64 con video reali girati da telefono (non solo simulati).
- Flusso completo verificato: upload da webapp → elaborazione Python in background → rimozione sfondo → visualizzazione nel viewer 3D.
- Buona qualità su oggetti opachi con texture; scarsa su oggetti piccoli/trasparenti/riflettenti (limite intrinseco, vedi sopra).
- **Cattura tramite foto multiple** implementata come alternativa al video (`captureMode` in `capture/page.tsx`): scatti singoli accumulati con anteprima, upload in batch, pipeline con `run_pipeline.py --images-dir <cartella>` (salta l'estrazione frame). Probabilmente qualità migliore del video: niente motion blur, risoluzione nativa del telefono più alta, meno artefatti di compressione. Stessa rimozione sfondo automatica di entrambe le modalità.
- Fail-fast e messaggi di errore più chiari quando la ricostruzione non ha abbastanza sovrapposizione tra le viste (vedi bug #12/#13).
- **Rilievo 2.5D da foto singola** (`monocular.py`, terza modalità in `/capture`): testato end-to-end via API reale (`/api/upload` con un solo file `image`), non solo da CLI. Utile quando serve solo il lato fotografato in pochi secondi, non un oggetto pieno.

## Come far girare tutto in locale (sviluppo, Windows)

```powershell
# Pipeline da riga di comando
app\venv\Scripts\python.exe -m app.pipeline.run_pipeline percorso\video.mp4 --job-name nome_job

# Sito web (serve anche per il flusso capture da telefono)
cd webapp
npm run dev
# poi apri http://localhost:3000 (o l'IP di rete per il telefono, es. http://172.20.48.1:3000/capture)
```

## Come far girare tutto in produzione (Oracle Cloud VM)

```bash
# Pipeline da riga di comando
~/3D_visualizer/app/venv/bin/python3 -m app.pipeline.run_pipeline percorso/video.mp4 --job-name nome_job --frames 60

# Rilievo 2.5D da una sola foto (nessun --frames, non si applica)
~/3D_visualizer/app/venv/bin/python3 -m app.pipeline.run_pipeline --single-image percorso/foto.jpg --job-name nome_job

# Dopo una modifica alla webapp (TypeScript/React): rebuild + restart pm2
~/rebuild_webapp.sh

# Dopo una modifica alla pipeline Python: nessun rebuild necessario,
# viene eseguita fresca ad ogni nuovo scan (basta caricare il file sul server)

pm2 list                              # stato processo
pm2 logs 3d-builder-web --lines 50    # log
```

Il flusso "registra dal telefono" (`/capture`) ora gira **direttamente sulla VM di produzione** (non serve più essere sullo stesso PC con COLMAP/OpenMVS installati) — la webapp lancia la pipeline Python come child process sulla stessa macchina.

## Limite noto per il deploy

Vercel (o qualsiasi hosting serverless) **non può eseguire la pipeline Python** (richiede COLMAP/OpenMVS, binari nativi pesanti, elaborazione di minuti). Il sito deployato su Vercel può quindi solo:
- mostrare il **viewer 3D** con un modello già pronto (es. `scene_final.glb`)
- mostrare il **codice generato** come esempio

Per l'elaborazione reale (upload + pipeline) serve un server con CPU/RAM dedicati che tenga il processo vivo per minuti — questo è oggi risolto dalla VM Oracle Cloud (vedi sopra), non da un deploy serverless.
