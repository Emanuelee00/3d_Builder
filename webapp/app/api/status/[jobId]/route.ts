import { NextRequest, NextResponse } from "next/server";
import { getJob } from "@/lib/jobs";
import { corsPreflight, withCors } from "@/lib/cors";

export async function OPTIONS() {
  return corsPreflight();
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  const { jobId } = await params;
  const job = getJob(jobId);

  if (!job) {
    return withCors(NextResponse.json({ error: "Job non trovato" }, { status: 404 }));
  }

  return withCors(NextResponse.json(job));
}
