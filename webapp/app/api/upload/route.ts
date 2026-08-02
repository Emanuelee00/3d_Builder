import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { randomUUID } from "crypto";
import { startJob } from "@/lib/jobs";
import { corsPreflight, withCors } from "@/lib/cors";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const UPLOADS_DIR = path.join(PROJECT_ROOT, "app", "uploads");

export async function OPTIONS() {
  return corsPreflight();
}

export async function POST(req: NextRequest) {
  const formData = await req.formData();

  const requestedFrames = Number(formData.get("frameCount"));
  const frameCount = [30, 60, 90].includes(requestedFrames) ? requestedFrames : 60;

  const videoFile = formData.get("video");
  const photoFiles = formData.getAll("photos").filter((f): f is File => f instanceof Blob);
  const imageFile = formData.get("image");

  const jobId = randomUUID();
  fs.mkdirSync(UPLOADS_DIR, { recursive: true });

  if (videoFile instanceof Blob) {
    const videoPath = path.join(UPLOADS_DIR, `${jobId}.mp4`);
    const buffer = Buffer.from(await videoFile.arrayBuffer());
    fs.writeFileSync(videoPath, buffer);
    startJob(jobId, { kind: "video", videoPath, frameCount });
  } else if (photoFiles.length > 0) {
    const imagesDir = path.join(UPLOADS_DIR, `${jobId}_photos`);
    fs.mkdirSync(imagesDir, { recursive: true });
    for (let i = 0; i < photoFiles.length; i++) {
      const buffer = Buffer.from(await photoFiles[i].arrayBuffer());
      fs.writeFileSync(path.join(imagesDir, `photo_${String(i).padStart(4, "0")}.jpg`), buffer);
    }
    startJob(jobId, { kind: "photos", imagesDir, frameCount });
  } else if (imageFile instanceof Blob) {
    const imagePath = path.join(UPLOADS_DIR, `${jobId}.jpg`);
    const buffer = Buffer.from(await imageFile.arrayBuffer());
    fs.writeFileSync(imagePath, buffer);
    startJob(jobId, { kind: "single-image", imagePath });
  } else {
    return withCors(NextResponse.json({ error: "Nessun video, foto o immagine ricevuti" }, { status: 400 }));
  }

  return withCors(NextResponse.json({ jobId }));
}
