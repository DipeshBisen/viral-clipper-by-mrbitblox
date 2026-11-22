import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
}

export function getScoreColor(score: number): string {
  if (score >= 80) return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
  if (score >= 60) return "text-amber-400 bg-amber-500/10 border-amber-500/20";
  return "text-rose-400 bg-rose-500/10 border-rose-500/20";
}
