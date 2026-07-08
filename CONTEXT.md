# 3D Builder — contesto del progetto

Utility che trasforma un video (foto multiple) in un modello 3D texturizzato, esportato come asset `.glb` + componente React Three Fiber pronto per il web.

## Idea di partenza

Da una conversazione esplorativa: l'obiettivo iniziale era capire se fosse fattibile creare uno strumento che trasforma foto/video in codice Three.js strutturato. Conclusioni chiave di quella discussione:

- **Foto singola → 3D**: non fattibile in modo affidabile senza AI (nessuna geometria ricavabile da un'unica immagine).
- **Video → 3D senza AI**: fattibile con fotogrammetria classica (Structure-from-Motion + Multi-View Stereo). Il video risolve il problema di avere molte viste della stessa scena.
- **Separazione in "componenti nominati"** (es. "questo è il tavolo", "questa è la sedia"): richiederebbe un modello di segmentazione AI, non implementato — il risultato attuale è **una singola mesh fusa**, non oggetti separati.
- **Business**: mercato saturo di alternative gratuite (Polycam, Scaniverse, RealityScan). L'idea più promettente è una nicchia verticale con export web strutturato (es. arredamento/immobiliare) invece di competere sulla ricostruzione generica.

## Architettura

```
app/                    Pipeline Python (video -> mesh 3D)
  pipeline/
    extract_frames.py   Video -> frame JPG (numero di frame target, non fps fisso)
    sparse.py           pycolmap: pose camere + point cloud sparsa (CPU)
    dense.py            OpenMVS: point cloud densa -> mesh -> texture (CPU)
    finalize_mesh.py     Corregge il glb di OpenMVS (vedi bug noti sotto)
    codegen.py           Genera componente React Three Fiber + preview.html standalone
    run_pipeline.py      Orchestratore CLI end-to-end
  venv/                 Virtualenv Python 3.12 (non in git)
  tools/OpenMVS/        Binari OpenMVS precompilati Windows (non in git, vedi sotto)

webapp/                 Sito Next.js (viewer + capture da telefono)
  app/page.tsx           Homepage: viewer 3D + pannello codice generato
  app/capture/page.tsx   Pagina cattura da telefono (input file con capture="environment")
  app/api/upload/        Riceve il video, lancia la pipeline Python come child process
  app/api/status/[id]/   Polling stato job (basato su file, non in-memory - vedi bug noti)
  lib/jobs.ts            Gestione job: stato su disco in app/job-status/*.json
  components/            ModelViewer (Canvas R3F), ScannedModel (loader glb), CodePanel

colmap/                 Clone di riferimento (solo esempi/documentazione, NON usato in produzione — si usa pycolmap via pip)
```

## Vincoli hardware importanti

- **Nessuna GPU NVIDIA** (Intel Arc integrata) → niente CUDA. COLMAP non ha fallback CPU per `patch_match_stereo`, quindi la ricostruzione densa passa **interamente da OpenMVS** (che supporta CPU) invece che dal modulo dense nativo di COLMAP.
- Python **3.12** richiesto (non 3.13): `pycolmap` e `open3d` non hanno ancora wheel per 3.13.
- OpenMVS scaricato da: `https://github.com/cdcseacave/openMVS/releases` (asset `OpenMVS_Windows_x64.zip`, versione standard non-CUDA). Va estratto in `app/tools/OpenMVS/` (non versionato in git per dimensione — da riscaricare se si clona il repo altrove).

## Bug reali trovati e risolti (da tenere a mente)

1. **`DensifyPointCloud.exe` con `-o`/`--cuda-device` espliciti** → fallisce silenziosamente (exit 1, nessun log). Risolto usando solo i default (sceglie CPU in automatico). Vedi `dense.py`.
2. **Mesh troppo frammentata → crash in `TextureMesh.exe`** (access violation) per troppe micro-patch texture. Risolto decimando la mesh (`--decimate 0.2`) prima della texturizzazione.
3. **Crash intermittente in `DensifyPointCloud`** con tutti i thread (18 core) in parallelo. Risolto limitando `--max-threads 4`.
4. **Il `.glb` esportato da OpenMVS non ha normali ed è "unlit"**, con la texture come **PNG esterno** (non incorporato — invalido per un `.glb` vero). Corretto in `finalize_mesh.py`: ricarica con trimesh, ricalcola le normali, riassocia la texture manualmente, riesporta un `.glb` autosufficiente con materiale PBR standard.
5. **Estrazione frame a fps fisso** non si adattava a video di lunghezza diversa (video corti = troppo pochi frame). Cambiato a target sul **numero totale di frame** (default 60), calcolato in base alla durata reale.
6. **Stato dei job in memoria (`Map` in `lib/jobs.ts`) perso tra le richieste** in Next.js dev mode (i moduli delle API route si re-instanziano). Risolto scrivendo lo stato su file JSON (`app/job-status/<jobId>.json`) invece che in una variabile di modulo.

## Stato attuale

- Pipeline CLI testata end-to-end con un video sintetico (generato con Open3D, scena procedurale con scacchiera colorata per garantire feature SIFT sufficienti).
- Flusso completo testato: upload da webapp → elaborazione Python in background → visualizzazione nel viewer 3D.
- Non ancora testato con un video reale girato da telefono (solo simulato finora).

## Come far girare tutto in locale

```powershell
# Pipeline da riga di comando
app\venv\Scripts\python.exe -m app.pipeline.run_pipeline percorso\video.mp4 --job-name nome_job

# Sito web (serve anche per il flusso capture da telefono)
cd webapp
npm run dev
# poi apri http://localhost:3000 (o l'IP di rete per il telefono, es. http://172.20.48.1:3000/capture)
```

Il flusso "registra dal telefono" richiede che il sito giri **in locale sullo stesso PC** dove sono installati COLMAP/OpenMVS — non funziona se il sito è deployato su Vercel (vedi limite sotto).

## Limite noto per il deploy

Vercel (o qualsiasi hosting serverless) **non può eseguire la pipeline Python** (richiede COLMAP/OpenMVS, binari nativi pesanti, elaborazione di minuti). Il sito deployato su Vercel può quindi solo:
- mostrare il **viewer 3D** con un modello già pronto (es. `scene_final.glb`)
- mostrare il **codice generato** come esempio

La pagina `/capture` (upload + elaborazione automatica) va usata solo in locale finché non si costruisce un backend separato (server con GPU/CPU dedicato) per l'elaborazione — questo è un passo successivo, non ancora affrontato.
