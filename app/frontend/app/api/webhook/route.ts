import { NextRequest, NextResponse } from "next/server";

declare global {
  var _jobStore: Map<string, any> | undefined;
}

const jobStore = global._jobStore || new Map<string, any>();

export async function POST(req: NextRequest) {
  try {
    const secret = req.headers.get("x-webhook-secret");
    const expectedSecret = process.env.WEBHOOK_SECRET;

    if (expectedSecret && secret !== expectedSecret) {
      return NextResponse.json({ error: "Unauthorized webhook" }, { status: 401 });
    }

    const payload = await req.json();
    const { job_id, status, clips, error } = payload;

    if (!job_id) {
      return NextResponse.json({ error: "Missing job_id" }, { status: 400 });
    }

    const current = jobStore.get(job_id) || {};
    jobStore.set(job_id, {
      ...current,
      status: status || "completed",
      stage: status === "completed" ? "Completed" : "Failed",
      progress: status === "completed" ? 100 : current.progress,
      clips: clips || current.clips || [],
      error: error || null,
      updated_at: new Date().toISOString(),
    });

    return NextResponse.json({ success: true });
  } catch (err: any) {
    console.error("Webhook processing error:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
