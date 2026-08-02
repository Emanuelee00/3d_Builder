import { spawn } from "child_process";
import fs from "fs";
import path from "path";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const PYTHON_EXE =
  process.platform === "win32"
    ? path.join(PROJECT_ROOT, "app", "venv", "Scripts", "python.exe")
    : path.join(PROJECT_ROOT, "app", "venv", "bin", "python");
const OUTPUT_ROOT = path.join(PROJECT_ROOT, "app", "output");
const PUBLIC_MODELS_DIR = path.join(process.cwd(), "public", "models");
const JOBS_DIR = path.join(PROJECT_ROOT, "app", "job-status");

export type JobStatus = {
  status: "processing" | "done" | "error";
  modelUrl?: string;
  log: string;
  error?: string;
};

// Video (estratto in frame dalla pipeline), foto (gia' pronte, uno scatto per
// immagine) e single-image (rilievo 2.5D da una sola foto, niente multi-vista)
// sono tre modalita' di input alternative per la stessa pipeline.
export type JobInput =
  | { kind: "video"; videoPath: string; frameCount: number }
  | { kind: "photos"; imagesDir: string; frameCount: number }
  | { kind: "single-image"; imagePath: string };

function statusPath(jobId: string): string {
  return path.join(JOBS_DIR, `${jobId}.json`);
}

function writeJob(jobId: string, job: JobStatus): void {
  fs.mkdirSync(JOBS_DIR, { recursive: true });
  fs.writeFileSync(statusPath(jobId), JSON.stringify(job));
}

export function getJob(jobId: string): JobStatus | undefined {
  const file = statusPath(jobId);
  if (!fs.existsSync(file)) return undefined;
  return JSON.parse(fs.readFileSync(file, "utf-8"));
}

// Il codice di uscita da solo ("codice 1") non dice nulla di utile: prova a
// recuperare l'ultimo messaggio di eccezione Python dal log per mostrare
// qualcosa di comprensibile invece di un errore generico.
function extractErrorMessage(log: string, code: number | null): string {
  // Qualsiasi eccezione Python il cui nome finisce in "Error" o "Exception"
  // (RuntimeError, ValueError, CalledProcessError, ecc.), non solo un elenco fisso.
  const matches = [...log.matchAll(/^\w*(?:Error|Exception): (.+)$/gm)];
  if (matches.length > 0) {
    return matches[matches.length - 1][1].trim();
  }
  return `Pipeline terminata con codice ${code}`;
}

export function startJob(jobId: string, input: JobInput): void {
  writeJob(jobId, { status: "processing", log: "" });

  const pipelineArgs =
    input.kind === "video"
      ? [input.videoPath, "--job-name", jobId, "--frames", String(input.frameCount)]
      : input.kind === "photos"
      ? ["--images-dir", input.imagesDir, "--job-name", jobId, "--frames", String(input.frameCount)]
      : ["--single-image", input.imagePath, "--job-name", jobId];

  const child = spawn(PYTHON_EXE, ["-u", "-m", "app.pipeline.run_pipeline", ...pipelineArgs], {
    cwd: PROJECT_ROOT,
  });

  child.stdout.on("data", (chunk) => {
    const job = getJob(jobId);
    if (job) writeJob(jobId, { ...job, log: job.log + chunk.toString() });
  });
  child.stderr.on("data", (chunk) => {
    const job = getJob(jobId);
    if (job) writeJob(jobId, { ...job, log: job.log + chunk.toString() });
  });

  child.on("exit", (code) => {
    const job = getJob(jobId);
    if (!job) return;

    if (code !== 0) {
      writeJob(jobId, { ...job, status: "error", error: extractErrorMessage(job.log, code) });
      return;
    }

    const generatedGlb = path.join(OUTPUT_ROOT, jobId, "scene_final.glb");
    if (!fs.existsSync(generatedGlb)) {
      writeJob(jobId, {
        ...job,
        status: "error",
        error: "Pipeline completata ma il modello finale non è stato trovato",
      });
      return;
    }

    fs.mkdirSync(PUBLIC_MODELS_DIR, { recursive: true });
    const destGlb = path.join(PUBLIC_MODELS_DIR, `${jobId}.glb`);
    fs.copyFileSync(generatedGlb, destGlb);

    const generatedJsx = path.join(OUTPUT_ROOT, jobId, "web", "ScannedModel.jsx");
    if (fs.existsSync(generatedJsx)) {
      fs.copyFileSync(generatedJsx, path.join(PUBLIC_MODELS_DIR, `${jobId}.jsx`));
    }

    writeJob(jobId, { ...job, status: "done", modelUrl: `/models/${jobId}.glb` });
  });
}
