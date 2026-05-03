"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

// ── Floating particles ──────────────────────────────────────────────────────

function Particles() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let w = 0,
      h = 0;

    interface Particle {
      x: number;
      y: number;
      vx: number;
      vy: number;
      r: number;
      o: number;
    }
    const particles: Particle[] = [];
    const COUNT = 80;

    const resize = () => {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight * 3;
    };
    resize();
    window.addEventListener("resize", resize);

    for (let i = 0; i < COUNT; i++) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        r: Math.random() * 2 + 0.5,
        o: Math.random() * 0.3 + 0.1,
      });
    }

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = w;
        if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h;
        if (p.y > h) p.y = 0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(10,31,68, ${p.o * 0.6})`;
        ctx.fill();
      }
      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 150) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(10,31,68, ${0.05 * (1 - dist / 150)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }
      animId = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none"
      style={{ zIndex: 0 }}
    />
  );
}

// ── Scroll-triggered fade-in ────────────────────────────────────────────────

function FadeIn({
  children,
  delay = 0,
  className = "",
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(40px)",
        transition: `opacity 0.8s ease ${delay}s, transform 0.8s ease ${delay}s`,
      }}
    >
      {children}
    </div>
  );
}

// ── Animated counter ────────────────────────────────────────────────────────

function Counter({ target, suffix = "" }: { target: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [val, setVal] = useState(0);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting && !started.current) {
          started.current = true;
          let start = 0;
          const step = target / 60;
          const tick = () => {
            start += step;
            if (start >= target) {
              setVal(target);
              return;
            }
            setVal(Math.floor(start));
            requestAnimationFrame(tick);
          };
          tick();
        }
      },
      { threshold: 0.5 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [target]);

  return (
    <span ref={ref}>
      {val}
      {suffix}
    </span>
  );
}

// ── Process step illustrations ───────────────────────────────────────────────

function IllustAI() {
  return (
    <svg viewBox="0 0 140 140" className="w-32 h-32" aria-hidden>
      {/* ── Documents (back to front) ── */}
      {/* Doc 3 — back, rotated right */}
      <g transform="rotate(12, 95, 88)">
        <rect x="64" y="56" width="46" height="58" rx="6" fill="#F0F4FA" stroke="#102A5C" strokeWidth="1.2" opacity="0.65"/>
        <rect x="72" y="70" width="30" height="3" rx="1.5" fill="#102A5C" opacity="0.1"/>
        <rect x="72" y="78" width="22" height="3" rx="1.5" fill="#102A5C" opacity="0.1"/>
        <rect x="72" y="86" width="26" height="3" rx="1.5" fill="#102A5C" opacity="0.1"/>
      </g>
      {/* Doc 2 — middle, rotated left */}
      <g transform="rotate(-7, 86, 65)">
        <rect x="58" y="26" width="46" height="58" rx="6" fill="white" stroke="#102A5C" strokeWidth="1.6" opacity="0.82"/>
        <path d="M93 26 L104 37 L93 37 Z" fill="#DCE3F0" stroke="#102A5C" strokeWidth="1"/>
        <rect x="66" y="44" width="28" height="3" rx="1.5" fill="#102A5C" opacity="0.14"/>
        <rect x="66" y="52" width="20" height="3" rx="1.5" fill="#102A5C" opacity="0.14"/>
        <rect x="66" y="60" width="24" height="3" rx="1.5" fill="#102A5C" opacity="0.14"/>
      </g>
      {/* Doc 1 — front, being written */}
      <rect x="54" y="40" width="52" height="68" rx="6" fill="white" stroke="#102A5C" strokeWidth="2.5"/>
      <path d="M94 40 L106 52 L94 52 Z" fill="#DCE3F0" stroke="#102A5C" strokeWidth="1.5" strokeLinejoin="round"/>
      <rect x="63" y="58" width="36" height="3.5" rx="1.5" fill="#102A5C" opacity="0.18"/>
      <rect x="63" y="67" width="28" height="3.5" rx="1.5" fill="#102A5C" opacity="0.18"/>
      <rect x="63" y="76" width="32" height="3.5" rx="1.5" fill="#102A5C" opacity="0.18"/>
      {/* Animated typing line */}
      <rect x="63" y="85" height="3.5" rx="1.5" fill="#102A5C" opacity="0.75">
        <animate attributeName="width" values="0;32;0" dur="2.5s" repeatCount="indefinite"/>
      </rect>

      {/* ── Robot ── */}
      {/* Antenna */}
      <line x1="28" y1="25" x2="28" y2="15" stroke="#102A5C" strokeWidth="2" strokeLinecap="round"/>
      <circle cx="28" cy="12" r="3.5" fill="#C9A24A">
        <animate attributeName="opacity" values="1;0.2;1" dur="1.5s" repeatCount="indefinite"/>
      </circle>
      {/* Head */}
      <rect x="14" y="25" width="28" height="22" rx="6" fill="#102A5C"/>
      {/* Eyes */}
      <circle cx="22" cy="36" r="4" fill="white"/>
      <circle cx="34" cy="36" r="4" fill="white"/>
      {/* Pupils track toward document */}
      <circle cx="23.5" cy="36" r="2.5" fill="#102A5C">
        <animate attributeName="cx" values="23.5;24.5;23.5" dur="3s" repeatCount="indefinite"/>
      </circle>
      <circle cx="35.5" cy="36" r="2.5" fill="#102A5C">
        <animate attributeName="cx" values="35.5;36.5;35.5" dur="3s" repeatCount="indefinite"/>
      </circle>
      {/* Body */}
      <rect x="16" y="49" width="24" height="22" rx="4" fill="#102A5C"/>
      <rect x="19" y="52" width="8" height="8" rx="2" fill="#C9A24A" opacity="0.9"/>
      <rect x="29" y="52" width="8" height="8" rx="2" fill="#DCE3F0" opacity="0.5"/>
      <rect x="19" y="62" width="18" height="2.5" rx="1" fill="#DCE3F0" opacity="0.35"/>

      {/* ── Sparkles ── */}
      <path d="M46 18 L47.5 13 L49 18 L54 19.5 L49 21 L47.5 26 L46 21 L41 19.5Z" fill="#C9A24A">
        <animate attributeName="opacity" values="1;0.2;1" dur="2.2s" repeatCount="indefinite"/>
      </path>
      <circle cx="122" cy="32" r="3" fill="#C9A24A" opacity="0.45">
        <animate attributeName="opacity" values="0.45;0;0.45" dur="2s" repeatCount="indefinite" begin="0.8s"/>
      </circle>
      <circle cx="126" cy="58" r="2" fill="#C9A24A" opacity="0.3">
        <animate attributeName="opacity" values="0.3;0;0.3" dur="1.8s" repeatCount="indefinite" begin="1.3s"/>
      </circle>
    </svg>
  );
}

function IllustSign() {
  return (
    <svg viewBox="0 0 140 140" className="w-32 h-32" aria-hidden>
      {/* Document base */}
      <rect x="14" y="58" width="78" height="74" rx="7" fill="white" stroke="#92400E" strokeWidth="2"/>
      <rect x="25" y="72" width="44" height="3.5" rx="1.5" fill="#92400E" opacity="0.15"/>
      <rect x="25" y="81" width="34" height="3.5" rx="1.5" fill="#92400E" opacity="0.15"/>
      <rect x="25" y="90" width="40" height="3.5" rx="1.5" fill="#92400E" opacity="0.15"/>
      {/* Seal impression — fades in when stamp hits */}
      <g>
        <animate attributeName="opacity" values="0;0;1;1" dur="3s" repeatCount="indefinite" keyTimes="0;0.38;0.52;1"/>
        <circle cx="80" cy="105" r="22" fill="#FEF3C7" stroke="#92400E" strokeWidth="1.8"/>
        <circle cx="80" cy="105" r="16" fill="none" stroke="#92400E" strokeWidth="1" strokeDasharray="3 2" opacity="0.6"/>
        <text x="80" y="101" textAnchor="middle" fill="#92400E" fontSize="7" fontWeight="bold" fontFamily="system-ui">CÔNG TY</text>
        <line x1="68" y1="105" x2="92" y2="105" stroke="#92400E" strokeWidth="0.8" opacity="0.5"/>
        <text x="80" y="113" textAnchor="middle" fill="#92400E" fontSize="8" fontWeight="bold" fontFamily="system-ui">ABC</text>
      </g>
      {/* Ink splatter dots */}
      <circle cx="58" cy="94" r="0" fill="#92400E">
        <animate attributeName="opacity" values="0;0;0.5;0" dur="3s" repeatCount="indefinite" keyTimes="0;0.38;0.44;0.65"/>
        <animate attributeName="r" values="0;0;3;4" dur="3s" repeatCount="indefinite" keyTimes="0;0.38;0.44;0.65"/>
      </circle>
      <circle cx="107" cy="92" r="0" fill="#92400E">
        <animate attributeName="opacity" values="0;0;0.4;0" dur="3s" repeatCount="indefinite" keyTimes="0;0.39;0.45;0.66" begin="0.04s"/>
        <animate attributeName="r" values="0;0;2.5;3.5" dur="3s" repeatCount="indefinite" keyTimes="0;0.39;0.45;0.66" begin="0.04s"/>
      </circle>
      {/* Stamp tool — moves down then back up */}
      <g>
        <animateTransform attributeName="transform" type="translate"
          values="0,0; 0,28; 0,28; 0,0"
          keyTimes="0;0.35;0.55;1" dur="3s" repeatCount="indefinite"
          calcMode="spline" keySplines="0.4 0 0.2 1; 0 0 1 1; 0.4 0 0.2 1"/>
        {/* Handle */}
        <rect x="54" y="6" width="32" height="17" rx="6" fill="#92400E"/>
        <rect x="59" y="10" width="22" height="3" rx="1.5" fill="white" opacity="0.25"/>
        <rect x="59" y="16" width="22" height="3" rx="1.5" fill="white" opacity="0.25"/>
        {/* Body */}
        <rect x="46" y="21" width="48" height="20" rx="4" fill="#C9A24A"/>
        {/* Rubber face */}
        <rect x="46" y="37" width="48" height="12" rx="3" fill="#92400E"/>
        <rect x="52" y="40" width="36" height="2.5" rx="1" fill="white" opacity="0.35"/>
        <rect x="52" y="44" width="22" height="2.5" rx="1" fill="white" opacity="0.35"/>
      </g>
    </svg>
  );
}

function IllustReview() {
  return (
    <svg viewBox="0 0 140 140" className="w-32 h-32" aria-hidden>
      {/* Document stack */}
      <rect x="16" y="30" width="64" height="82" rx="7" fill="#E0F2F1" stroke="#0F766E" strokeWidth="1.5"/>
      <rect x="22" y="24" width="64" height="82" rx="7" fill="white" stroke="#0F766E" strokeWidth="2.5"/>
      <rect x="33" y="42" width="42" height="4" rx="2" fill="#0F766E" opacity="0.2"/>
      <rect x="33" y="52" width="32" height="4" rx="2" fill="#0F766E" opacity="0.2"/>
      <rect x="33" y="62" width="38" height="4" rx="2" fill="#0F766E" opacity="0.2"/>
      <rect x="33" y="72" width="28" height="4" rx="2" fill="#0F766E" opacity="0.2"/>
      {/* Scan line */}
      <rect x="22" y="52" width="64" height="2" rx="1" fill="#0F766E" opacity="0.35">
        <animate attributeName="y" values="38;90;38" dur="3s" repeatCount="indefinite" calcMode="ease-in-out"/>
      </rect>
      {/* Magnifying glass */}
      <circle cx="95" cy="56" r="24" fill="rgba(204,251,241,0.9)" stroke="#0F766E" strokeWidth="3"/>
      <circle cx="95" cy="56" r="15" fill="none" stroke="#0F766E" strokeWidth="2.5"/>
      <line x1="106" y1="67" x2="118" y2="80" stroke="#0F766E" strokeWidth="4" strokeLinecap="round"/>
      {/* Tick inside glass */}
      <path d="M88 56 L93 62 L103 48" stroke="#0F766E" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none"
            strokeDasharray="24" strokeDashoffset="24">
        <animate attributeName="stroke-dashoffset" values="24;0;24" dur="3.5s" repeatCount="indefinite" begin="0.5s"/>
      </path>
    </svg>
  );
}

function IllustCert() {
  return (
    <svg viewBox="0 0 140 140" className="w-32 h-32" aria-hidden>
      {/* Ribbon tails */}
      <path d="M55 108 L48 130 L70 118 L92 130 L85 108" fill="#15803D" opacity="0.7"/>
      {/* Medal circle */}
      <circle cx="70" cy="76" r="40" fill="white" stroke="#15803D" strokeWidth="3"/>
      <circle cx="70" cy="76" r="33" fill="none" stroke="#15803D" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.4"/>
      {/* Star */}
      <path d="M70 48 L74.5 62 L89 62 L77.5 71 L82 85 L70 76 L58 85 L62.5 71 L51 62 L65.5 62 Z" fill="#C9A24A">
        <animate attributeName="opacity" values="1;0.6;1" dur="2s" repeatCount="indefinite"/>
      </path>
      {/* Shine rays */}
      {[0,45,90,135,180,225,270,315].map((deg, i) => (
        <line key={i}
          x1={70 + Math.cos(deg*Math.PI/180)*36}
          y1={76 + Math.sin(deg*Math.PI/180)*36}
          x2={70 + Math.cos(deg*Math.PI/180)*42}
          y2={76 + Math.sin(deg*Math.PI/180)*42}
          stroke="#C9A24A" strokeWidth="2" strokeLinecap="round" opacity="0.5">
          <animate attributeName="opacity" values="0.5;1;0.5" dur="2s" repeatCount="indefinite" begin={`${i*0.25}s`}/>
        </line>
      ))}
      {/* HALAL text */}
      <text x="70" y="100" textAnchor="middle" fill="#15803D" fontSize="9" fontWeight="bold"
            fontFamily="system-ui" letterSpacing="2">HALAL</text>
    </svg>
  );
}

// ── Vertical process line (animates on scroll) ────────────────────────────────

function VerticalProcessLine() {
  const ref = useRef<HTMLDivElement>(null);
  const [drawn, setDrawn] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setDrawn(true); obs.disconnect(); } },
      { threshold: 0.1 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return (
    <div ref={ref} className="hidden md:block absolute left-1/2 -translate-x-1/2 top-0 bottom-0 w-0.5"
         style={{ background: "#E2E8F0", zIndex: 0 }}>
      <div style={{
        height: drawn ? "100%" : "0%",
        background: "linear-gradient(180deg, #102A5C 0%, #C9A24A 33%, #0F766E 66%, #15803D 100%)",
        transition: "height 2.4s cubic-bezier(0.4,0,0.2,1) 0.2s",
      }}/>
    </div>
  );
}

// ── Orbiting rings ──────────────────────────────────────────────────────────

function OrbitRings() {
  return (
    <div
      className="absolute inset-0 grid place-items-center pointer-events-none"
      style={{ zIndex: 1 }}
    >
      {[280, 360, 440].map((size, i) => (
        <div
          key={i}
          className="absolute rounded-full"
          style={{
            width: size,
            height: size,
            border: `1px solid rgba(10,31,68,${0.12 - i * 0.03})`,
            animation: `orbit-spin ${20 + i * 10}s linear infinite ${i % 2 === 0 ? "" : "reverse"}`,
          }}
        >
          <div
            className="absolute w-2 h-2 rounded-full"
            style={{
              top: 0,
              left: "50%",
              transform: "translate(-50%,-50%)",
              background: `rgba(10,31,68,${0.4 - i * 0.1})`,
              boxShadow: `0 0 8px rgba(10,31,68,${0.3})`,
            }}
          />
        </div>
      ))}
    </div>
  );
}

// ── Main ────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  const [scrollY, setScrollY] = useState(0);
  useEffect(() => {
    const onScroll = () => setScrollY(window.scrollY);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const features = [
    {
      icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
      title: "AI đánh giá tuân thủ",
      desc: "Phân tích theo JAKIM/HDC trong vài giây.",
    },
    {
      icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
      title: "Tạo hồ sơ tự động",
      desc: "Mẫu chuẩn, song ngữ Việt – Anh.",
    },
    {
      icon: "M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
      title: "Cổng Halal toàn cầu",
      desc: "Tiếp cận thị trường 7 nghìn tỷ USD.",
    },
    {
      icon: "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z",
      title: "Bảo mật đa tổ chức",
      desc: "Vault, JWT, dữ liệu cách ly tenant.",
    },
  ];

  const stats = [
    { value: 13, suffix: "", label: "Loại tài liệu" },
    { value: 100, suffix: "%", label: "Phạm vi tiêu chuẩn" },
    { value: 4, suffix: "", label: "Ngôn ngữ" },
    { value: 7, suffix: "T$", label: "Thị trường Halal" },
  ];

  return (
    <div className="relative overflow-hidden" style={{ background: "#FFFFFF" }}>
      {/* ── Sticky brand header ── */}
      <div
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          zIndex: 100,
          opacity: scrollY > 80 ? 1 : 0,
          transform: scrollY > 80 ? "translateY(0)" : "translateY(-100%)",
          transition: "opacity 0.3s ease, transform 0.3s ease",
          pointerEvents: scrollY > 80 ? "auto" : "none",
          background: "rgba(255,255,255,0.92)",
          backdropFilter: "blur(14px)",
          WebkitBackdropFilter: "blur(14px)",
          borderBottom: "1px solid rgba(10,31,68,0.07)",
          boxShadow: "0 2px 20px rgba(10,31,68,0.06)",
        }}
      >
        <div
          className="max-w-5xl mx-auto flex items-center justify-between pl-2 pr-6"
          style={{ height: 72 }}
        >
          {/* Logo mark + brand name cạnh nhau, bên trái */}
          <div className="flex items-center gap-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/aminra-mark.png"
              alt=""
              className="h-10 w-10 object-contain"
            />
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/aminra-wordmark-navy.png"
              alt="AMINRA"
              className="h-5 object-contain"
            />
          </div>
        </div>
      </div>

      <Particles />

      {/* ── CSS Animations ── */}
      <style>{`
        @keyframes orbit-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-20px); } }
        @keyframes glow-pulse { 0%,100% { opacity: 0.4; } 50% { opacity: 1; } }
        @keyframes slide-up { from { opacity:0; transform:translateY(60px); } to { opacity:1; transform:translateY(0); } }
        @keyframes shimmer-line { 0%,100% { background-position:0% 0%; } 50% { background-position:100% 0%; } }
      `}</style>

      {/* ── Hero (light, brand-aligned) ── */}
      <section
        className="relative min-h-screen grid place-items-center px-6"
        style={{
          zIndex: 2,
          background:
            "linear-gradient(180deg, #DCE3F0 0%, #F5F1E8 50%, #FFFFFF 100%)",
        }}
      >
        <OrbitRings />

        {/* Radial glow */}
        <div
          className="absolute w-[600px] h-[600px] rounded-full"
          style={{
            background:
              "radial-gradient(circle, rgba(10,31,68,0.06) 0%, transparent 70%)",
            animation: "glow-pulse 4s ease-in-out infinite",
          }}
        />

        <div
          className="relative text-center max-w-4xl py-16"
          style={{ zIndex: 3 }}
        >
          {/* Brand lockup */}
          <FadeIn delay={0.1}>
            <div className="inline-flex flex-col items-center gap-4 mb-12">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/aminra-lockup.png"
                alt="AMINRA"
                className="h-32 md:h-40 object-contain"
              />
              <div className="flex items-center gap-3">
                <span
                  className="block w-10 h-px"
                  style={{ background: "#C9A24A" }}
                />
                <span
                  className="text-xs font-medium"
                  style={{ color: "#A88224", letterSpacing: "0.18em" }}
                >
                  HALAL INTEGRITY · DIGITAL TRUST
                </span>
                <span
                  className="block w-10 h-px"
                  style={{ background: "#C9A24A" }}
                />
              </div>
            </div>
          </FadeIn>

          {/* Headline */}
          <FadeIn delay={0.2}>
            <h1
              className="text-3xl sm:text-5xl md:text-7xl font-black tracking-tight mb-8"
              style={{ color: "#0A1F44", lineHeight: 1.1 }}
            >
              Chứng nhận Halal,
              <br />
              <span style={{ color: "#102A5C" }}>
                tự động{" "}
                <span
                  style={{
                    background: "linear-gradient(135deg, #C9A24A, #A88224)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                  }}
                >
                  90%
                </span>{" "}
                quy trình.
              </span>
            </h1>
          </FadeIn>

          {/* Slogan */}
          <FadeIn delay={0.35}>
            <p
              className="text-lg md:text-xl max-w-xl mx-auto mb-14 leading-relaxed"
              style={{ color: "#374151" }}
            >
              AI soạn hồ sơ —{" "}
              <span className="font-semibold" style={{ color: "#102A5C" }}>
                doanh nghiệp chỉ cần ký duyệt.
              </span>
            </p>
          </FadeIn>

          {/* CTAs */}
          <FadeIn delay={0.5}>
            <div className="flex items-center justify-center gap-4 flex-wrap">
              <Link
                href="/business/register"
                className="px-8 py-4 rounded-2xl font-bold text-base text-white btn-lift"
                style={{
                  background: "linear-gradient(135deg, #0A1F44, #102A5C)",
                  boxShadow: "0 8px 32px rgba(10,31,68,0.30)",
                }}
              >
                Bắt đầu miễn phí
              </Link>
              <Link
                href="/business/login"
                className="px-8 py-4 rounded-2xl font-bold text-base btn-lift"
                style={{
                  color: "#0A1F44",
                  border: "1.5px solid #0A1F44",
                  background: "#FFFFFF",
                }}
              >
                Đăng nhập
              </Link>
            </div>
          </FadeIn>
        </div>
      </section>

      {/* ── Scroll cue (between hero CTA and stats) ── */}
      <div
        className="relative grid place-items-center pt-6 pb-2"
        style={{ zIndex: 2, background: "#FFFFFF" }}
      >
        <div
          className="flex flex-col items-center gap-1"
          style={{ animation: "float 3s ease-in-out infinite" }}
        >
          <span
            className="text-[10px] font-medium uppercase tracking-[0.25em]"
            style={{ color: "#A88224" }}
          >
            Khám phá
          </span>
          <span className="text-2xl leading-none" style={{ color: "#C9A24A" }}>
            ⌄
          </span>
        </div>
      </div>

      {/* ── Stats Bar ── */}
      <section
        className="relative py-16 px-6"
        style={{ zIndex: 2, background: "#FFFFFF" }}
      >
        <div
          className="max-w-5xl mx-auto rounded-3xl p-8"
          style={{
            background: "#FFFFFF",
            border: "1px solid #E2E8F0",
            boxShadow: "0 20px 60px rgba(10,31,68,0.06)",
          }}
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map((s, i) => (
              <FadeIn key={s.label} delay={i * 0.1}>
                <div className="text-center">
                  <div
                    className="text-3xl md:text-4xl font-black"
                    style={{ color: "#0A1F44" }}
                  >
                    <Counter target={s.value} suffix={s.suffix} />
                  </div>
                  <div
                    className="text-xs mt-2 font-semibold uppercase tracking-wider"
                    style={{ color: "#6B7280" }}
                  >
                    {s.label}
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section
        className="relative py-24 px-6"
        style={{ zIndex: 2, background: "#F2F4F5" }}
      >
        <div className="max-w-6xl mx-auto">
          <FadeIn>
            <div className="text-center mb-12">
              <h2
                className="text-3xl md:text-4xl font-black mb-3"
                style={{ color: "#0A1F44" }}
              >
                Giải pháp toàn diện
              </h2>
              <p className="text-base" style={{ color: "#6B7280" }}>
                Từ hồ sơ đến chứng nhận, trên một nền tảng.
              </p>
            </div>
          </FadeIn>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((f, i) => (
              <FadeIn key={f.title} delay={i * 0.08}>
                <div
                  className="rounded-2xl p-6 h-full lift-hover group"
                  style={{
                    background: "#FFFFFF",
                    border: "1px solid #E2E8F0",
                    boxShadow: "0 4px 20px rgba(10,31,68,0.04)",
                  }}
                >
                  <div
                    className="w-12 h-12 rounded-xl grid place-items-center mb-4 transition-transform duration-[240ms] ease-[cubic-bezier(0.25,1,0.5,1)] group-hover:scale-105"
                    style={{
                      background: "#DCE3F0",
                      border: "1px solid #D9B96E",
                    }}
                  >
                    <svg
                      className="w-6 h-6"
                      fill="none"
                      stroke="#0A1F44"
                      strokeWidth="1.8"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d={f.icon}
                      />
                    </svg>
                  </div>
                  <h3
                    className="text-base font-bold mb-2"
                    style={{ color: "#0A1F44" }}
                  >
                    {f.title}
                  </h3>
                  <p
                    className="text-sm leading-relaxed"
                    style={{ color: "#6B7280" }}
                  >
                    {f.desc}
                  </p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section
        className="relative py-24 px-6"
        style={{ zIndex: 2, background: "#F5F1E8" }}
      >
        <div className="max-w-5xl mx-auto">
          <FadeIn>
            <div className="text-center mb-16">
              <h2
                className="text-3xl md:text-4xl font-black mb-3"
                style={{ color: "#0A1F44" }}
              >
                Quy trình chứng nhận Halal
              </h2>
              <p className="text-base" style={{ color: "#6B7280" }}>
                Từ hồ sơ đến chứng nhận — AMINRA đồng hành toàn bộ quy trình.
              </p>
            </div>
          </FadeIn>

          {(() => {
            const steps = [
              {
                number: "01", color: "#102A5C", light: "#DCE3F0", tag: "AI",
                title: "AI chuẩn bị hồ sơ",
                desc: "AI phân tích nguyên liệu, tự động soạn toàn bộ hồ sơ theo chuẩn JAKIM/HDC — đúng mẫu, song ngữ, không cần soạn thủ công.",
                Illust: IllustAI,
              },
              {
                number: "02", color: "#92400E", light: "#FEF3C7", tag: "Doanh nghiệp",
                title: "Doanh nghiệp ký duyệt",
                desc: "Xem xét hồ sơ AI soạn và ký duyệt điện tử. Mọi thay đổi được ghi nhận tức thì — không cần soạn lại từ đầu.",
                Illust: IllustSign,
              },
              {
                number: "03", color: "#0F766E", light: "#CCFBF1", tag: "CB",
                title: "Cơ quan đánh giá hồ sơ",
                desc: "Tổ chức chứng nhận tiếp nhận và thẩm định hồ sơ trực tiếp trên nền tảng. Audit trail đầy đủ, minh bạch.",
                Illust: IllustReview,
              },
              {
                number: "04", color: "#15803D", light: "#DCFCE7", tag: "Halal",
                title: "Chứng chỉ được cấp",
                desc: "Chứng nhận Halal được cấp, đăng ký blockchain và tích hợp mã QR xác minh công khai toàn cầu.",
                Illust: IllustCert,
              },
            ];

            return (
              <div className="relative">
                <VerticalProcessLine />
                <div className="flex flex-col gap-12 md:gap-0">
                  {steps.map((s, i) => {
                    const isEven = i % 2 === 0;
                    const IllustComp = s.Illust;

                    const illustCard = (
                      <div className="flex justify-center">
                        <div
                          className="w-52 h-52 rounded-3xl flex items-center justify-center"
                          style={{
                            background: s.light,
                            border: `1.5px solid ${s.color}22`,
                            animation: `float 4s ease-in-out ${i * 0.6}s infinite`,
                            boxShadow: `0 16px 48px ${s.color}18`,
                          }}
                        >
                          <IllustComp />
                        </div>
                      </div>
                    );

                    const textCard = (
                      <div className={`flex flex-col gap-3 ${isEven ? "md:pl-12" : "md:pr-12"}`}>
                        <span
                          className="text-xs font-bold uppercase tracking-widest px-3 py-1 rounded-full self-start"
                          style={{ background: s.light, color: s.color }}
                        >
                          {s.tag}
                        </span>
                        <h3 className="text-xl md:text-2xl font-black" style={{ color: "#0A1F44" }}>
                          {s.title}
                        </h3>
                        <p className="text-base leading-relaxed" style={{ color: "#374151" }}>
                          {s.desc}
                        </p>
                      </div>
                    );

                    return (
                      <FadeIn key={s.number} delay={i * 0.1}>
                        <div
                          className="grid grid-cols-1 md:grid-cols-[1fr_88px_1fr] items-center gap-6 md:gap-0 py-6 md:py-10"
                          style={{ position: "relative", zIndex: 1 }}
                        >
                          {/*
                            Desktop: isEven → text | badge | illust
                                     isOdd  → illust | badge | text
                            Mobile (grid-cols-1): luôn badge → illust → text
                            Dùng CSS order để đảm bảo mobile nhất quán dù desktop so le.
                          */}

                          {/* Slot A: text(even) / illust(odd) */}
                          <div className={isEven ? "order-3 md:order-none" : "order-2 md:order-none"}>
                            {isEven ? textCard : illustCard}
                          </div>

                          {/* Center: badge (desktop only) */}
                          <div className="hidden md:flex flex-col items-center">
                            <div
                              className="w-14 h-14 rounded-full flex items-center justify-center flex-shrink-0"
                              style={{ background: s.color, boxShadow: `0 8px 24px ${s.color}50` }}
                            >
                              <span className="text-white text-lg font-black">{s.number}</span>
                            </div>
                          </div>

                          {/* Slot B: illust(even) / text(odd) */}
                          <div className={isEven ? "order-2 md:order-none" : "order-3 md:order-none"}>
                            {isEven ? illustCard : textCard}
                          </div>

                          {/* Mobile: badge row */}
                          <div className="flex md:hidden items-center gap-3 order-first">
                            <div
                              className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
                              style={{ background: s.color, boxShadow: `0 4px 12px ${s.color}40` }}
                            >
                              <span className="text-white text-sm font-black">{s.number}</span>
                            </div>
                            <span
                              className="text-xs font-bold uppercase tracking-widest px-3 py-1 rounded-full"
                              style={{ background: s.light, color: s.color }}
                            >
                              {s.tag}
                            </span>
                          </div>
                        </div>
                      </FadeIn>
                    );
                  })}
                </div>
              </div>
            );
          })()}
        </div>
      </section>

      {/* ── CTA Section (60% Primary Green) ── */}
      <section
        className="relative py-24 px-6"
        style={{ zIndex: 2, background: "#FFFFFF" }}
      >
        <FadeIn>
          <div
            className="max-w-3xl mx-auto text-center rounded-3xl p-12 relative overflow-hidden"
            style={{
              background: "linear-gradient(135deg, #0A1F44 0%, #102A5C 100%)",
              boxShadow: "0 20px 60px rgba(10,31,68,0.30)",
            }}
          >
            {/* Gold radial accent */}
            <div
              className="absolute top-0 right-0 w-72 h-72 rounded-full"
              style={{
                background:
                  "radial-gradient(circle, rgba(201,162,74,0.20), transparent 70%)",
              }}
            />

            <div className="relative">
              <h2 className="text-3xl md:text-4xl font-black text-white mb-6">
                Sẵn sàng đạt chứng nhận Halal?
              </h2>
              <Link
                href="/business/register"
                className="inline-flex items-center gap-3 px-8 py-4 rounded-2xl font-bold text-base btn-lift"
                style={{
                  background: "linear-gradient(135deg, #F0D070 0%, #C9A24A 100%)",
                  color: "#0A1F44",
                  boxShadow: "0 8px 32px rgba(201,162,74,0.50)",
                }}
              >
                Đăng ký miễn phí
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M13 7l5 5m0 0l-5 5m5-5H6"
                  />
                </svg>
              </Link>
            </div>
          </div>
        </FadeIn>
      </section>

      {/* ── Footer ── */}
      <footer
        className="relative py-12 px-6"
        style={{ zIndex: 2, background: "#0A1F44" }}
      >
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-lg grid place-items-center p-1"
              style={{ background: "#FFFFFF" }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/aminra-mark.png"
                alt=""
                className="w-full h-full object-contain"
              />
            </div>
            <div className="flex flex-col leading-tight gap-0.5">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/aminra-wordmark-white.png"
                alt="AMINRA"
                className="h-3.5 object-contain self-start"
              />
              <span
                className="text-[10px]"
                style={{ color: "#C9A24A", letterSpacing: "0.1em" }}
              >
                HALAL INTEGRITY · DIGITAL TRUST
              </span>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
            <Link
              href="/business/login"
              className="inline-flex items-center min-h-[32px] text-xs transition-colors hover:text-white"
              style={{ color: "#D9B96E" }}
            >
              Đăng nhập Doanh nghiệp
            </Link>
            <Link
              href="/provider/login"
              className="inline-flex items-center min-h-[32px] text-xs transition-colors hover:text-white"
              style={{ color: "#D9B96E" }}
            >
              Đăng nhập Tổ chức
            </Link>
            <Link
              href="/privacy"
              className="inline-flex items-center min-h-[32px] text-xs transition-colors hover:text-white"
              style={{ color: "#D9B96E" }}
            >
              Chính sách bảo mật
            </Link>
            <Link
              href="/terms"
              className="inline-flex items-center min-h-[32px] text-xs transition-colors hover:text-white"
              style={{ color: "#D9B96E" }}
            >
              Điều khoản
            </Link>
          </div>
          <p
            className="text-xs"
            style={{ color: "#94A3B8" }}
            suppressHydrationWarning
          >
            &copy; {new Date().getFullYear()} AMINRA. Mọi quyền được bảo lưu.
          </p>
        </div>
      </footer>
    </div>
  );
}
