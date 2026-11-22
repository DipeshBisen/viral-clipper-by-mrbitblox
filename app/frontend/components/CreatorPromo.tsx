/* eslint-disable @next/next/no-img-element */
// "Follow the creator" promo: Mr BitBloX on YouTube and ps5_pov_ on Instagram.

const PROMOS = [
  {
    name: "YouTube",
    handle: "@MrBitBloX",
    href: "https://www.youtube.com/@MrBitBloX",
    image: "/promo/youtube.png",
    cta: "Subscribe on YouTube",
    button: "bg-red-600 hover:bg-red-500",
    ring: "hover:border-red-500/50",
  },
  {
    name: "Instagram",
    handle: "@ps5_pov_",
    href: "https://www.instagram.com/ps5_pov_/",
    image: "/promo/instagram.png",
    cta: "Follow on Instagram",
    button: "bg-gradient-to-r from-amber-500 via-pink-500 to-purple-600 hover:opacity-90",
    ring: "hover:border-pink-500/50",
  },
];

export function CreatorPromo() {
  return (
    <section className="space-y-4" aria-labelledby="creator-promo-title">
      <div className="text-center space-y-1">
        <h2 id="creator-promo-title" className="text-lg font-bold text-zinc-100">
          Made by Mr BitBloX 🎮
        </h2>
        <p className="text-xs text-zinc-400">Gaming, PS5 and PC hardware. Follow for more.</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {PROMOS.map((p) => (
          <a
            key={p.name}
            href={p.href}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`${p.cta} (${p.handle})`}
            className={`group block rounded-2xl border border-zinc-800 bg-zinc-950/60 overflow-hidden transition-colors ${p.ring}`}
          >
            <div className="bg-[#0f0f0f] flex items-center justify-center p-2">
              <img
                src={p.image}
                alt={`${p.name} profile of ${p.handle}`}
                className="w-full h-auto max-h-48 object-contain"
                loading="lazy"
              />
            </div>
            <div className="p-3 flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-zinc-200">{p.handle}</span>
              <span className={`px-3 py-1.5 rounded-lg text-xs font-bold text-white ${p.button}`}>
                {p.cta}
              </span>
            </div>
          </a>
        ))}
      </div>
    </section>
  );
}
