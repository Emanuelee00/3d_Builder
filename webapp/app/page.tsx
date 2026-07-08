import fs from "fs";
import path from "path";
import { ModelViewer } from "@/components/ModelViewer";
import { CodePanel } from "@/components/CodePanel";

export default function Home() {
  const generatedCode = fs.readFileSync(
    path.join(process.cwd(), "data", "generated-ScannedModel.jsx.txt"),
    "utf-8"
  );

  return (
    <div className="flex flex-col min-h-screen bg-[#09090b] text-white">
      <header className="px-6 py-4 border-b border-white/10">
        <h1 className="text-lg font-semibold">Foto/Video &rarr; 3D &rarr; Three.js</h1>
        <p className="text-sm text-white/50">
          Anteprima del modello ricostruito e del codice React Three Fiber generato dalla pipeline
        </p>
      </header>
      <main className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4 p-4">
        <div className="h-[70vh] md:h-auto rounded-lg overflow-hidden border border-white/10">
          <ModelViewer modelPath="/models/scene_final.glb" />
        </div>
        <div className="h-[50vh] md:h-auto">
          <CodePanel title="ScannedModel.jsx (generato dalla pipeline)" code={generatedCode} />
        </div>
      </main>
    </div>
  );
}
