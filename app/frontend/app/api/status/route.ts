import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

declare global {
  var _jobStore: Map<string, any> | undefined;
}

const jobStore = global._jobStore || new Map<string, any>();

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const jobId = searchParams.get("jobId");

  if (!jobId) {
    return NextResponse.json({ error: "Missing jobId query parameter" }, { status: 400 });
  }

  let job = jobStore.get(jobId);
  const backendDir = path.resolve(process.cwd(), "..", "backend");

  // 1. Check local filesystem for output clips manifest (Completion)
  const manifestPath = path.join(backendDir, "output", jobId, "clips.json");
  if (fs.existsSync(manifestPath)) {
    try {
      const data = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
      if (Array.isArray(data) && data.length > 0) {
        const clips = data.map((c: any) => ({
          ...c,
          url: `/api/video?jobId=${jobId}&filename=${encodeURIComponent(c.filename)}`,
        }));

        const completedJob = {
          ...(job || {}),
          job_id: jobId,
          status: "completed",
          stage: "Completed",
          progress: 100,
          clips,
        };
        jobStore.set(jobId, completedJob);
        return NextResponse.json(completedJob);
      } else if (Array.isArray(data) && data.length === 0) {
        return NextResponse.json({
          status: "failed",
          stage: "Failed",
          progress: 0,
          clips: [],
          error: "No high-confidence moments detected. Try adjusting clip duration or another video.",
        });
      }
    } catch (e) {
      console.error("Error reading clips.json:", e);
    }
  }

  // 2. Check local filesystem for real-time status.json from Python
  const statusFilePath = path.join(backendDir, "data", jobId, "status.json");
  if (fs.existsSync(statusFilePath)) {
    try {
      const realStatus = JSON.parse(fs.readFileSync(statusFilePath, "utf-8"));
      if (realStatus) {
        if (Array.isArray(realStatus.clips)) {
          realStatus.clips = realStatus.clips.map((c: any) => ({
            ...c,
            url: c.filename
              ? `/api/video?jobId=${jobId}&filename=${encodeURIComponent(c.filename)}`
              : c.url,
          }));
        }
        job = { ...(job || {}), ...realStatus };
        jobStore.set(jobId, job);
        return NextResponse.json(job);
      }
    } catch (e) {
      // ignore
    }
  }

  // 3. If Modal backend URL is available and job not finished, proxy status from Modal
  const backendUrl = process.env.MODAL_API_URL;
  if (backendUrl && (!job || job.status === "processing" || job.status === "queued")) {
    try {
      const res = await fetch(`${backendUrl}/get_status?job_id=${encodeURIComponent(jobId)}`);
      if (res.ok) {
        const remoteStatus = await res.json();
        if (remoteStatus && remoteStatus.status !== "not_found") {
          job = { ...job, ...remoteStatus };
          jobStore.set(jobId, job);
        }
      }
    } catch (err) {
      // ignore network errors
    }
  }

  if (!job) {
    return NextResponse.json({
      status: "processing",
      stage: "Initializing video processing pipeline...",
      progress: 15,
      clips: [],
    });
  }

  return NextResponse.json(job);
}
