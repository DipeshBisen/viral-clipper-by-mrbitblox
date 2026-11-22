import type { Metadata } from "next";
import { QueryProvider } from "@/components/QueryProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Viral Clipper — AI 9:16 Shorts Generator",
  description: "Extract viral moments from 1h+ videos, reframe to 9:16 portrait, and burn animated captions.",
};

const SOCIALS = [
  {
    name: "YouTube",
    handle: "@MrBitBloX",
    href: "https://www.youtube.com/@MrBitBloX",
    hover: "hover:text-red-500 hover:border-red-500/40",
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor" aria-hidden="true">
        <path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2 31 31 0 0 0 0 12a31 31 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1A31 31 0 0 0 24 12a31 31 0 0 0-.5-5.8ZM9.6 15.6V8.4l6.2 3.6-6.2 3.6Z" />
      </svg>
    ),
  },
  {
    name: "Instagram",
    handle: "@ps5_pov_",
    href: "https://www.instagram.com/ps5_pov_/",
    hover: "hover:text-pink-500 hover:border-pink-500/40",
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <rect x="3" y="3" width="18" height="18" rx="5" />
        <circle cx="12" cy="12" r="4" />
        <circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
];

function SocialLinks({ showLabels = false }: { showLabels?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      {SOCIALS.map((s) => (
        <a
          key={s.name}
          href={s.href}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`${s.name} ${s.handle}`}
          title={`${s.name} ${s.handle}`}
          className={`flex items-center gap-1.5 text-zinc-400 border border-zinc-800 rounded-full bg-zinc-900/50 transition-colors ${s.hover} ${
            showLabels ? "px-3 py-1.5 text-xs" : "w-8 h-8 justify-center"
          }`}
        >
          {s.icon}
          {showLabels && <span>{s.handle}</span>}
        </a>
      ))}
    </div>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased bg-[#09090b] text-zinc-100 selection:bg-indigo-500/30 selection:text-indigo-200">
        <QueryProvider>
          <div className="relative min-h-screen flex flex-col justify-between">
            {/* Ambient Background Glow */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[350px] bg-gradient-to-b from-indigo-600/20 via-purple-600/10 to-transparent blur-[120px] pointer-events-none -z-10" />
            
            <header className="border-b border-zinc-800/60 backdrop-blur-sm sticky top-0 z-50 bg-[#09090b]/80">
              <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
                <a href="/" className="flex items-center gap-2 font-bold text-xl tracking-tight">
                  <span className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/25">⚡</span>
                  <span>Viral<span className="text-indigo-400">Clipper</span></span>
                </a>
                <div className="flex items-center gap-2">
                  <SocialLinks />
                  <div className="hidden sm:block text-xs text-zinc-400 font-medium border border-zinc-800 px-3 py-1.5 rounded-full bg-zinc-900/50">
                    9:16 Shorts & Reels AI
                  </div>
                </div>
              </div>
            </header>

            <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-10">
              {children}
            </main>

            <footer className="border-t border-zinc-900 py-6 text-xs text-zinc-600 flex flex-col items-center gap-3">
              <SocialLinks showLabels />
              <span>Personal AI Viral Clipper by Mr BitBloX</span>
            </footer>
          </div>
        </QueryProvider>
      </body>
    </html>
  );
}
