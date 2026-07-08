"use client";

import { useEffect, useRef, useState } from "react";
import { ModelViewer } from "@/components/ModelViewer";

type Status = "idle" | "uploading" | "processing" | "done" | "error";

export default function CapturePage() {
  const [status, setStatus] = useState<Status>("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [modelUrl, setModelUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [log, setLog] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setStatus("uploading");
    setErrorMsg(null);

    const formData = new FormData();
    formData.append("video", file);

    try {
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      if (!res.ok) throw new Error("Upload fallito");
      const data = await res.json();
      setJobId(data.jobId);
      setStatus("processing");
    } catch {
      setStatus("error");
      setErrorMsg("Errore durante il caricamento del video");
    }
  }

  useEffect(() => {
    if (status !== "processing" || !jobId) return;

    pollRef.current = setInterval(async () => {
      const res = await fetch(`/api/status/${jobId}`);
      if (!res.ok) return;
      const data = await res.json();
      setLog(data.log ?? "");

      if (data.status === "done") {
        setModelUrl(data.modelUrl);
        setStatus("done");
        if (pollRef.current) clearInterval(pollRef.current);
      } else if (data.status === "error") {
        setErrorMsg(data.error ?? "Errore sconosciuto");
        setStatus("error");
        if (pollRef.current) clearInterval(pollRef.current);
      }
    }, 3000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [status, jobId]);

  return (
    <div className="flex flex-col min-h-screen bg-[#09090b] text-white">
      <header className="px-6 py-4 border-b border-white/10">
        <h1 className="text-lg font-semibold">Registra e ricostruisci in 3D</h1>
        <p className="text-sm text-white/50">
          Gira lentamente intorno all&apos;oggetto mentre registri, poi carica il video
        </p>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center gap-6 p-6">
        {status === "idle" && (
          <label className="flex flex-col items-center gap-3 px-8 py-6 rounded-lg border border-dashed border-white/30 cursor-pointer hover:border-white/60 transition-colors">
            <span className="text-base font-medium">Registra o scegli un video</span>
            <span className="text-sm text-white/50">Tocca per aprire la fotocamera del telefono</span>
            <input
              type="file"
              accept="video/*"
              capture="environment"
              className="hidden"
              onChange={handleFileChange}
            />
          </label>
        )}

        {status === "uploading" && <p className="text-white/70">Caricamento video in corso…</p>}

        {status === "processing" && (
          <div className="flex flex-col items-center gap-3 w-full max-w-lg">
            <p className="text-white/70">
              Ricostruzione 3D in corso (può richiedere qualche minuto)…
            </p>
            <pre className="text-xs text-white/40 bg-black/40 rounded p-3 max-h-40 overflow-auto w-full whitespace-pre-wrap">
              {log.slice(-1500)}
            </pre>
          </div>
        )}

        {status === "error" && (
          <p className="text-red-400">Errore: {errorMsg}</p>
        )}

        {status === "done" && modelUrl && (
          <div className="w-full max-w-2xl h-[70vh] rounded-lg overflow-hidden border border-white/10">
            <ModelViewer modelPath={modelUrl} />
          </div>
        )}
      </main>
    </div>
  );
}
