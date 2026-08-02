import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { corsPreflight, withCors } from "@/lib/cors";

const PUBLIC_MODELS_DIR = path.join(process.cwd(), "public", "models");

// Next.js (con Turbopack, in produzione con "next start") non sembra rileggere
// public/ da disco ad ogni richiesta: un file .glb copiato li' DOPO l'ultima build
// risulta 404 finche' non si rifa' una build, anche se il file esiste davvero su
// disco (verificato: un file presente da prima di una build torna 200, uno aggiunto
// dopo torna 404 anche in locale sul server, quindi non e' un problema di cache del
// browser/tunnel). Dato che i modelli vengono generati in continuazione da job che
// girano ben oltre l'ultima build, li serviamo con una route dinamica che legge
// sempre da disco invece di affidarci al file statico in public/models/.
export async function OPTIONS() {
  return corsPreflight();
}

export async function GET(_req: NextRequest, { params }: { params: Promise<{ filename: string }> }) {
  const { filename } = await params;
  if (!/^[a-zA-Z0-9-]+\.(glb|jsx)$/.test(filename)) {
    return withCors(NextResponse.json({ error: "Nome file non valido" }, { status: 400 }));
  }

  const filePath = path.join(PUBLIC_MODELS_DIR, filename);
  if (!fs.existsSync(filePath)) {
    return withCors(NextResponse.json({ error: "Modello non trovato" }, { status: 404 }));
  }

  const contentType = filename.endsWith(".glb") ? "model/gltf-binary" : "text/plain; charset=utf-8";
  const body = new Uint8Array(fs.readFileSync(filePath));
  return withCors(new NextResponse(body, { headers: { "Content-Type": contentType } }));
}
