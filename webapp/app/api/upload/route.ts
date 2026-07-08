import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { randomUUID } from "crypto";
import { startJob } from "@/lib/jobs";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const UPLOADS_DIR = path.join(PROJECT_ROOT, "app", "uploads");

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const file = formData.get("video");

  if (!file || !(file instanceof Blob)) {
    return NextResponse.json({ error: "Nessun video ricevuto" }, { status: 400 });
  }

  const jobId = randomUUID();
  fs.mkdirSync(UPLOADS_DIR, { recursive: true });
  const videoPath = path.join(UPLOADS_DIR, `${jobId}.mp4`);

  const buffer = Buffer.from(await file.arrayBuffer());
  fs.writeFileSync(videoPath, buffer);

  startJob(jobId, videoPath);

  return NextResponse.json({ jobId });
}
