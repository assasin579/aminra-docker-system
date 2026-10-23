"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

const NEWS_PER_PAGE = 3;
const NEWS = [
  { image: "/news/market.jpg", tag: "market", title: "halal_market_title", description: "halal_market_desc" },
  { image: "/news/business.jpg", tag: "business", title: "export_title", description: "export_desc" },
  { image: "/news/traceability.jpg", tag: "traceability", title: "traceability_title", description: "traceability_desc" },
  { image: "/news/certification.jpg", tag: "certification", title: "certification_title", description: "certification_desc" },
  { image: "/news/readiness.jpg", tag: "business", title: "readiness_title", description: "readiness_desc" },
  { image: "/news/trade.jpg", tag: "market", title: "trade_title", description: "trade_desc" },
] as const;

export default function LandingNews() {
  const { t, i18n } = useTranslation();
  const [page, setPage] = useState(0);
  const [paused, setPaused] = useState(false);
  const pageCount = Math.ceil(NEWS.length / NEWS_PER_PAGE);

  useEffect(() => {
    if (paused || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => setPage((current) => (current + 1) % pageCount), 8000);
    return () => window.clearInterval(timer);
  }, [pageCount, paused]);

  const visibleNews = NEWS.slice(page * NEWS_PER_PAGE, (page + 1) * NEWS_PER_PAGE);
  const selectPage = (next: number) => setPage((next + pageCount) % pageCount);

  return (
    <section
      data-section="landing-news"
      className="relative px-6 py-20 md:py-24"
      style={{ zIndex: 2, background: "#FFFFFF" }}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setPaused(false);
      }}
    >
      <div className="mx-auto max-w-6xl">
        <div className="mb-10 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="mb-3 text-xs font-bold uppercase tracking-[0.2em]" style={{ color: "#A88224" }}>{t("landing.landing_news.eyebrow")}</p>
            <h2 className="text-3xl font-black md:text-4xl" style={{ color: "#0A1F44" }}>{t("landing.landing_news.title")}</h2>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed md:text-base" style={{ color: "#6B7280" }}>{t("landing.landing_news.subtitle")}</p>
            <p role="note" className="mt-3 inline-flex rounded-full border px-3 py-1 text-xs font-semibold" style={{ color: "#704F00", borderColor: "rgba(168,130,36,.3)", background: "rgba(201,162,74,.12)" }}>{t("landing.landing_news.demo_notice")}</p>
          </div>
          <div className="flex items-center gap-3">
            <button type="button" onClick={() => selectPage(page - 1)} aria-label={t("landing.landing_news.previous")} className="grid h-11 w-11 place-items-center rounded-full border bg-white transition hover:-translate-y-0.5 hover:shadow-md focus-visible:outline focus-visible:outline-2" style={{ color: "#0A1F44", borderColor: "rgba(10,31,68,.14)" }}>←</button>
            <div aria-label={t("landing.landing_news.pagination")} aria-live="polite" className="flex items-center gap-2">
              {Array.from({ length: pageCount }, (_, index) => <button key={index} type="button" onClick={() => selectPage(index)} aria-label={t("landing.landing_news.go_to_page", { page: index + 1 })} aria-current={page === index ? "page" : undefined} className="h-2.5 rounded-full transition-all duration-500" style={{ width: page === index ? 28 : 10, background: page === index ? "#C9A24A" : "#CBD5E1" }} />)}
            </div>
            <button type="button" onClick={() => selectPage(page + 1)} aria-label={t("landing.landing_news.next")} className="grid h-11 w-11 place-items-center rounded-full border bg-white transition hover:-translate-y-0.5 hover:shadow-md focus-visible:outline focus-visible:outline-2" style={{ color: "#0A1F44", borderColor: "rgba(10,31,68,.14)" }}>→</button>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3" key={page}>
          {visibleNews.map((item, index) => (
            <article key={item.title} className="group overflow-hidden rounded-3xl border bg-white shadow-sm transition duration-700 ease-out animate-[news-enter_700ms_cubic-bezier(.2,.8,.2,1)_both] hover:-translate-y-1 hover:shadow-xl" style={{ borderColor: "rgba(10,31,68,.08)", animationDelay: `${index * 110}ms` }}>
              <div className="relative aspect-[16/10] overflow-hidden bg-slate-100">
                <img src={item.image} alt={t(`landing.landing_news.alt.${item.tag}`)} loading="lazy" className="h-full w-full object-cover transition duration-700 group-hover:scale-[1.04]" />
                <span className="absolute left-4 top-4 rounded-full border border-white/70 bg-white/90 px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider" style={{ color: "#0A1F44" }}>{t(`landing.landing_news.category.${item.tag}`)}</span>
              </div>
              <div className="p-6">
                <h3 className="mb-3 text-lg font-extrabold leading-snug" style={{ color: "#0A1F44" }}>{t(`landing.landing_news.${item.title}`)}</h3>
                <p className="text-sm leading-relaxed" style={{ color: "#6B7280" }}>{t(`landing.landing_news.${item.description}`)}</p>
              </div>
            </article>
          ))}
        </div>
        <span className="sr-only" aria-live="polite">{t("landing.landing_news.page_status", { page: page + 1, total: pageCount })} · {i18n.language}</span>
      </div>
      <style>{`
        @keyframes news-enter { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: translateY(0); } }
        @media (prefers-reduced-motion: reduce) { [data-section="landing-news"] *, [data-section="landing-news"] *::before, [data-section="landing-news"] *::after { animation: none !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; } }
        @media (hover: none), (pointer: coarse) { [data-section="landing-news"] .group:hover img { transform: none; } [data-section="landing-news"] article:hover { transform: none; } }
      `}</style>
    </section>
  );
}
