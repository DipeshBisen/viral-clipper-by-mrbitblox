import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const jobId = searchParams.get("jobId");
  const filename = searchParams.get("filename");

  if (!jobId || !filename) {
    return new NextResponse("Missing parameters", { status: 400 });
  }

  // Prevent directory traversal
  const safeFilename = path.basename(filename);
  const safeJobId = path.basename(jobId);

  const videoPath = path.resolve(
    process.cwd(),
    "..",
    "backend",
    "output",
    safeJobId,
    safeFilename
  );

  if (!fs.existsSync(videoPath)) {
    return new NextResponse("Video not found", { status: 404 });
  }

  const stat = fs.statSync(videoPath);
  const fileSize = stat.size;
  const range = req.headers.get("range");

  if (range) {
    const parts = range.replace(/bytes=/, "").split("-");
    const start = parseInt(parts[0], 10);
    const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
    const chunksize = end - start + 1;
    const file = fs.createReadStream(videoPath, { start, end });

    const headers = new Headers();
    headers.set("Content-Range", `bytes ${start}-${end}/${fileSize}`);
    headers.set("Accept-Ranges", "bytes");
    headers.set("Content-Length", chunksize.toString());
    headers.set("Content-Type", "video/mp4");

    // @ts-ignore Node stream to web stream
    return new NextResponse(file, { status: 206, headers });
  } else {
    const file = fs.createReadStream(videoPath);
    const headers = new Headers();
    headers.set("Content-Length", fileSize.toString());
    headers.set("Content-Type", "video/mp4");

    // @ts-ignore Node stream to web stream
    return new NextResponse(file, { status: 200, headers });
  }
}
