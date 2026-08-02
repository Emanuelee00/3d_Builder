"use client";

import { useEffect, useRef, useState } from "react";
import { ModelViewer } from "@/components/ModelViewer";

type Status = "idle" | "uploading" | "processing" | "done" | "error";
type CaptureMode = "video" | "photos";

// Se impostata (es. su Vercel), le richieste vanno al PC locale che esegue
// davvero la pipeline (es. un URL ngrok). Vuota = usa le API di questo stesso
// sito (comportamento di sviluppo in locale).
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

const ACTIVE_JOB_KEY = "3dbuilder_active_job";

// localStorage puo' lanciare un'eccezione (non limitarsi a fallire) in alcune modalita'
// browser (es. Safari in navigazione privata, o impostazioni privacy restrittive) - senza
// protezione questo mandava in crash l'intera pagina (schermata bianca) al primo avvio.
function safeStorage() {
  try {
    const testKey = "__storage_test__";
    window.localStorage.setItem(testKey, "1");
    window.localStorage.removeItem(testKey);
    return window.localStorage;
  } catch {
    return null;
  }
}

const FRAME_OPTIONS = [
  { value: 30, label: "Veloce", hint: "meno dettaglio" },
  { value: 60, label: "Bilanciato", hint: "predefinito" },
  { value: 90, label: "Dettagliato", hint: "più lento" },
] as const;

// Sotto questa soglia la ricostruzione (SfM) ha troppe poche viste sovrapposte
// per avere buone probabilita' di riuscita; sopra RECOMMENDED_PHOTOS la qualita'
// tipicamente non migliora molto oltre.
const MIN_PHOTOS_TO_SUBMIT = 5;
const RECOMMENDED_PHOTOS = 20;

// La pipeline stampa "[N/5] descrizione fase" per ognuno dei 5 passaggi: la usiamo
// per stimare una percentuale di avanzamento senza dover instrumentare il Python.
function progressFromLog(log: string): number {
  const matches = [...log.matchAll(/\[(\d)\/5\]/g)];
  if (matches.length === 0) return 0;
  const lastStep = Number(matches[matches.length - 1][1]);
  return Math.min(100, Math.round((lastStep / 5) * 100));
}

function CameraIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 8h3l1.5-2h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z" strokeLinejoin="round" />
      <circle cx="12" cy="13" r="3.5" />
    </svg>
  );
}

export default function CapturePage() {
  const [status, setStatus] = useState<Status>("idle");
  const [captureMode, setCaptureMode] = useState<CaptureMode>("video");
  const [photos, setPhotos] = useState<File[]>([]);
  const [photoUrls, setPhotoUrls] = useState<string[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [modelUrl, setModelUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [log, setLog] = useState("");
  const [frameCount, setFrameCount] = useState<number>(60);
  const [uploadProgress, setUploadProgress] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Riprende un job già in corso (o già concluso) se navighi via e torni indietro,
  // invece di perdere lo stato e dover ricaricare tutto da capo.
  useEffect(() => {
    const storage = safeStorage();
    const savedJobId = storage?.getItem(ACTIVE_JOB_KEY);
    if (!savedJobId) return;

    fetch(`${API_BASE}/api/status/${savedJobId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setJobId(savedJobId);
          applyStatus(data);
        } else {
          // Il job salvato non esiste più lato server (es. riavvio, pulizia stato):
          // niente da riprendere, torna alla schermata di partenza invece di
          // restare bloccati per sempre su "processing".
          storage?.removeItem(ACTIVE_JOB_KEY);
        }
      })
      .catch(() => {
        storage?.removeItem(ACTIVE_JOB_KEY);
      });
  }, []);

  function applyStatus(data: { status: Status; log?: string; modelUrl?: string; error?: string }) {
    setLog(data.log ?? "");
    if (data.status === "done" && data.modelUrl) {
      setModelUrl(`${API_BASE}${data.modelUrl}`);
      setStatus("done");
    } else if (data.status === "error") {
      setErrorMsg(data.error ?? "Errore sconosciuto");
      setStatus("error");
    } else {
      setStatus("processing");
    }
  }

  // Genera le anteprime delle foto scattate finora e libera la memoria dei blob
  // quando l'elenco cambia o il componente si smonta.
  useEffect(() => {
    const urls = photos.map((file) => URL.createObjectURL(file));
    setPhotoUrls(urls);
    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [photos]);

  function handleAddPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    // Azzera il valore subito: permette di scattare un'altra foto con lo stesso
    // input senza dover prima "deselezionare" nulla.
    e.target.value = "";
    if (!file) return;
    setPhotos((prev) => [...prev, file]);
  }

  function removeLastPhoto() {
    setPhotos((prev) => prev.slice(0, -1));
  }

  // Upload condiviso da video singolo e foto multiple, con barra di progresso
  // reale: fetch() non espone il progresso di upload, serve XMLHttpRequest.
  function uploadAndStart(buildFormData: () => FormData) {
    setStatus("uploading");
    setUploadProgress(0);
    setErrorMsg(null);

    const xhr = new XMLHttpRequest();
    xhr.upload.addEventListener("progress", (ev) => {
      if (ev.lengthComputable) {
        setUploadProgress(Math.round((ev.loaded / ev.total) * 100));
      }
    });
    xhr.addEventListener("load", () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        setStatus("error");
        setErrorMsg("Errore durante il caricamento");
        return;
      }
      const data = JSON.parse(xhr.responseText);
      safeStorage()?.setItem(ACTIVE_JOB_KEY, data.jobId);
      setJobId(data.jobId);
      setStatus("processing");
    });
    xhr.addEventListener("error", () => {
      setStatus("error");
      setErrorMsg("Errore durante il caricamento");
    });
    xhr.open("POST", `${API_BASE}/api/upload`);
    xhr.send(buildFormData());
  }

  function handleVideoFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    uploadAndStart(() => {
      const formData = new FormData();
      formData.append("video", file);
      formData.append("frameCount", String(frameCount));
      return formData;
    });
  }

  function handleSubmitPhotos() {
    if (photos.length < MIN_PHOTOS_TO_SUBMIT) return;
    uploadAndStart(() => {
      const formData = new FormData();
      photos.forEach((photo) => formData.append("photos", photo));
      formData.append("frameCount", String(frameCount));
      return formData;
    });
  }

  function startNewScan() {
    safeStorage()?.removeItem(ACTIVE_JOB_KEY);
    setJobId(null);
    setModelUrl(null);
    setErrorMsg(null);
    setLog("");
    setPhotos([]);
    setStatus("idle");
  }

  useEffect(() => {
    if (status !== "processing" || !jobId) return;

    pollRef.current = setInterval(async () => {
      const res = await fetch(`${API_BASE}/api/status/${jobId}`);
      if (!res.ok) {
        // Il job e' sparito lato server a meta' polling: non restare bloccati
        // in "processing" per sempre, torna alla schermata di partenza.
        if (pollRef.current) clearInterval(pollRef.current);
        startNewScan();
        return;
      }
      const data = await res.json();
      applyStatus(data);
      if (data.status === "done" || data.status === "error") {
        if (pollRef.current) clearInterval(pollRef.current);
      }
    }, 3000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [status, jobId]);

  const progress = progressFromLog(log);

  return (
    <div className="flex flex-col flex-1 text-white">
      <header className="px-6 py-4 border-b border-white/10 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Registra e ricostruisci in 3D</h1>
          <p className="text-sm text-white/50">
            Gira lentamente intorno all&apos;oggetto mentre registri, poi carica il video
          </p>
        </div>
        {(status === "done" || status === "error" || status === "processing") && (
          <button
            onClick={startNewScan}
            className="shrink-0 px-4 py-2 rounded-full text-sm font-medium bg-white/10 hover:bg-white/20 transition-colors"
          >
            {status === "processing" ? "Annulla / nuovo scan" : "Nuovo scan"}
          </button>
        )}
      </header>

      <main className="flex-1 flex flex-col items-center justify-center gap-8 p-6">
        {status === "idle" && (
          <div className="flex flex-col items-center gap-8 w-full max-w-sm">
            <div className="flex w-full p-1 rounded-full bg-white/5 border border-white/10">
              {(
                [
                  { value: "video" as const, label: "Video" },
                  { value: "photos" as const, label: "Foto" },
                ]
              ).map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setCaptureMode(opt.value)}
                  className={`flex-1 px-3 py-2 rounded-full text-sm font-medium transition-all ${
                    captureMode === opt.value
                      ? "bg-indigo-500 text-white shadow-lg shadow-indigo-500/30"
                      : "text-white/50 hover:text-white/80"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <div className="flex flex-col items-center gap-3 w-full">
              <span className="text-xs uppercase tracking-wide text-white/40">Qualità ricostruzione</span>
              <div className="flex w-full p-1 rounded-full bg-white/5 border border-white/10">
                {FRAME_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setFrameCount(opt.value)}
                    className={`flex-1 px-3 py-2 rounded-full text-sm font-medium transition-all ${
                      frameCount === opt.value
                        ? "bg-indigo-500 text-white shadow-lg shadow-indigo-500/30"
                        : "text-white/50 hover:text-white/80"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <span className="text-xs text-white/40">
                {FRAME_OPTIONS.find((o) => o.value === frameCount)?.hint}
              </span>
            </div>

            {captureMode === "video" ? (
              <label className="group flex flex-col items-center gap-4 cursor-pointer">
                <span className="flex items-center justify-center w-24 h-24 rounded-full bg-indigo-500 group-hover:bg-indigo-400 group-active:scale-95 transition-all shadow-xl shadow-indigo-500/30">
                  <CameraIcon />
                </span>
                <span className="flex flex-col items-center gap-1">
                  <span className="text-base font-medium">Registra o scegli un video</span>
                  <span className="text-sm text-white/40">Tocca per aprire la fotocamera del telefono</span>
                </span>
                <input
                  type="file"
                  accept="video/*"
                  capture="environment"
                  className="hidden"
                  onChange={handleVideoFileChange}
                />
              </label>
            ) : (
              <div className="flex flex-col items-center gap-4 w-full">
                {photos.length > 0 && (
                  <div className="grid grid-cols-4 gap-2 w-full">
                    {photoUrls.map((url, i) => (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        key={i}
                        src={url}
                        alt={`Foto ${i + 1}`}
                        className="aspect-square w-full object-cover rounded-lg border border-white/10"
                      />
                    ))}
                  </div>
                )}

                <label className="group flex flex-col items-center gap-3 cursor-pointer">
                  <span className="flex items-center justify-center w-20 h-20 rounded-full bg-indigo-500 group-hover:bg-indigo-400 group-active:scale-95 transition-all shadow-xl shadow-indigo-500/30">
                    <CameraIcon />
                  </span>
                  <span className="text-sm font-medium">Scatta foto ({photos.length})</span>
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    className="hidden"
                    onChange={handleAddPhoto}
                  />
                </label>

                <p className="text-xs text-white/40 text-center">
                  {photos.length < RECOMMENDED_PHOTOS
                    ? `Consigliate almeno ${RECOMMENDED_PHOTOS} foto da angolazioni diverse, girando lentamente intorno all'oggetto`
                    : "Buon numero di foto — puoi continuare a scattare o ricostruire ora"}
                </p>

                {photos.length > 0 && (
                  <div className="flex gap-2 w-full">
                    <button
                      onClick={removeLastPhoto}
                      className="flex-1 px-3 py-2 rounded-full text-sm font-medium bg-white/10 hover:bg-white/20 transition-colors"
                    >
                      Rimuovi ultima
                    </button>
                    <button
                      onClick={() => setPhotos([])}
                      className="flex-1 px-3 py-2 rounded-full text-sm font-medium bg-white/10 hover:bg-white/20 transition-colors"
                    >
                      Ricomincia
                    </button>
                  </div>
                )}

                <button
                  onClick={handleSubmitPhotos}
                  disabled={photos.length < MIN_PHOTOS_TO_SUBMIT}
                  className="w-full px-4 py-3 rounded-full text-sm font-medium bg-indigo-500 hover:bg-indigo-400 disabled:bg-white/10 disabled:text-white/30 disabled:cursor-not-allowed transition-colors"
                >
                  {photos.length < MIN_PHOTOS_TO_SUBMIT
                    ? `Servono almeno ${MIN_PHOTOS_TO_SUBMIT} foto`
                    : `Ricostruisci con ${photos.length} foto`}
                </button>
              </div>
            )}
          </div>
        )}

        {status === "uploading" && (
          <div className="flex flex-col items-center gap-3 w-full max-w-sm">
            <p className="text-white/70">Caricamento in corso…</p>
            <div className="w-full h-2 rounded-full bg-white/10 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-400 transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <span className="text-xs text-white/40">{uploadProgress}%</span>
          </div>
        )}

        {status === "processing" && (
          <div className="flex flex-col items-center gap-3 w-full max-w-lg">
            <p className="text-white/70 text-center">
              Ricostruzione 3D in corso (può richiedere qualche minuto)… puoi cambiare pagina,
              continua in background.
            </p>
            <div className="w-full h-2 rounded-full bg-white/10 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-400 transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="text-xs text-white/40">{progress}%</span>
            <pre className="text-xs text-white/40 bg-black/40 rounded-lg p-3 max-h-40 overflow-auto w-full whitespace-pre-wrap">
              {log.slice(-1500)}
            </pre>
          </div>
        )}

        {status === "error" && (
          <p className="text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3">
            Errore: {errorMsg}
          </p>
        )}

        {status === "done" && modelUrl && (
          <div className="w-full max-w-2xl h-[70vh] rounded-2xl overflow-hidden border border-white/10 shadow-2xl">
            <ModelViewer modelPath={modelUrl} />
          </div>
        )}
      </main>
    </div>
  );
}
