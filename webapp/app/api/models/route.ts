import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { withCors, corsPreflight } from "@/lib/cors";

const PUBLIC_MODELS_DIR = path.join(process.cwd(), "public", "models");

export async function OPTIONS() {
  return corsPreflight();
}

export async function GET() {
  if (!fs.existsSync(PUBLIC_MODELS_DIR)) {
    return withCors(NextResponse.json({ models: [] }));
  }

  const models = fs
    .readdirSync(PUBLIC_MODELS_DIR)
    .filter((f) => f.endsWith(".glb"))
    .map((f) => {
      const id = f.replace(/\.glb$/, "");
      const stat = fs.statSync(path.join(PUBLIC_MODELS_DIR, f));
      return {
        id,
        modelUrl: `/models/${f}`,
        hasCode: fs.existsSync(path.join(PUBLIC_MODELS_DIR, `${id}.jsx`)),
        createdAt: stat.mtime.toISOString(),
      };
    })
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));

  return withCors(NextResponse.json({ models }));
}
