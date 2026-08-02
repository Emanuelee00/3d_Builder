"use client";

import { useEffect, useState } from "react";
import { ModelViewer } from "@/components/ModelViewer";
import { CodePanel } from "@/components/CodePanel";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

type ModelInfo = {
  id: string;
  modelUrl: string;
  hasCode: boolean;
  createdAt: string;
};

export default function Home() {
  const [models, setModels] = useState<ModelInfo[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [codeCache, setCodeCache] = useState<Record<string, string>>({});

  useEffect(() => {
    fetch(`${API_BASE}/api/models`)
      .then((res) => res.json())
      .then((data: { models: ModelInfo[] }) => {
        setModels(data.models);
        if (data.models.length > 0) setSelectedId(data.models[0].id);
      });
  }, []);

  const selected = models?.find((m) => m.id === selectedId) ?? null;

  useEffect(() => {
    if (!selected?.hasCode || codeCache[selected.id]) return;
    fetch(`${API_BASE}/models/${selected.id}.jsx`)
      .then((res) => res.text())
      .then((text) => setCodeCache((prev) => ({ ...prev, [selected.id]: text })));
  }, [selected, codeCache]);

  const code = selected?.hasCode ? codeCache[selected.id] ?? "" : "";

  return (
    <div className="flex flex-col flex-1 text-white">
      <header className="px-6 py-4 border-b border-white/10 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Foto/Video &rarr; 3D &rarr; Three.js</h1>
          <p className="text-sm text-white/50">
            Anteprima del modello ricostruito e del codice React Three Fiber generato dalla pipeline
          </p>
        </div>

        {models && models.length > 0 && (
          <select
            value={selectedId ?? ""}
            onChange={(e) => setSelectedId(e.target.value)}
            className="bg-white/10 border border-white/20 rounded-md px-3 py-2 text-sm"
          >
            {models.map((m) => (
              <option key={m.id} value={m.id} className="bg-[#09090b]">
                {new Date(m.createdAt).toLocaleString("it-IT")}
              </option>
            ))}
          </select>
        )}
      </header>

      {models === null && (
        <main className="flex-1 flex items-center justify-center text-white/50">Caricamento…</main>
      )}

      {models && models.length === 0 && (
        <main className="flex-1 flex flex-col items-center justify-center gap-3 text-white/50">
          <p>Nessun modello ancora generato.</p>
          <a href="/capture" className="text-white underline">
            Registra il primo video &rarr;
          </a>
        </main>
      )}

      {selected && (
        <main className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4 p-4">
          <div className="h-[70vh] md:h-auto rounded-lg overflow-hidden border border-white/10">
            <ModelViewer modelPath={`${API_BASE}${selected.modelUrl}`} />
          </div>
          <div className="h-[50vh] md:h-auto">
            {code ? (
              <CodePanel title="ScannedModel.jsx (generato dalla pipeline)" code={code} />
            ) : (
              <div className="h-full flex items-center justify-center text-white/40 text-sm border border-white/10 rounded-lg">
                Nessun codice disponibile per questo modello
              </div>
            )}
          </div>
        </main>
      )}
    </div>
  );
}
