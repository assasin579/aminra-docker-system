'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';

// ── Floating particles ──────────────────────────────────────────────────────

function Particles() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let w = 0, h = 0;

    interface Particle { x: number; y: number; vx: number; vy: number; r: number; o: number; }
    const particles: Particle[] = [];
    const COUNT = 80;

    const resize = () => {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight * 3;
    };
    resize();
    window.addEventListener('resize', resize);

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
        ctx.fillStyle = `rgba(15,81,50, ${p.o * 0.6})`;
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
            ctx.strokeStyle = `rgba(15,81,50, ${0.05 * (1 - dist / 150)})`;
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
      window.removeEventListener('resize', resize);
    };
  }, []);

  return <canvas ref={canvasRef} className="fixed inset-0 pointer-events-none" style={{ zIndex: 0 }} />;
}

// ── Scroll-triggered fade-in ────────────────────────────────────────────────

function FadeIn({ children, delay = 0, className = '' }: { children: React.ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect(); } }, { threshold: 0.15 });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <div ref={ref} className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(40px)',
        transition: `opacity 0.8s ease ${delay}s, transform 0.8s ease ${delay}s`,
      }}>
      {children}
    </div>
  );
}

// ── Animated counter ────────────────────────────────────────────────────────

function Counter({ target, suffix = '' }: { target: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [val, setVal] = useState(0);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !started.current) {
        started.current = true;
        let start = 0;
        const step = target / 60;
        const tick = () => {
          start += step;
          if (start >= target) { setVal(target); return; }
          setVal(Math.floor(start));
          requestAnimationFrame(tick);
        };
        tick();
      }
    }, { threshold: 0.5 });
    obs.observe(el);
    return () => obs.disconnect();
  }, [target]);

  return <span ref={ref}>{val}{suffix}</span>;
}

// ── Orbiting rings ──────────────────────────────────────────────────────────

function OrbitRings() {
  return (
    <div className="absolute inset-0 grid place-items-center pointer-events-none" style={{ zIndex: 1 }}>
      {[280, 360, 440].map((size, i) => (
        <div key={i} className="absolute rounded-full"
          style={{
            width: size, height: size,
            border: `1px solid rgba(15,81,50,${0.12 - i * 0.03})`,
            animation: `orbit-spin ${20 + i * 10}s linear infinite ${i % 2 === 0 ? '' : 'reverse'}`,
          }}>
          <div className="absolute w-2 h-2 rounded-full"
            style={{ top: 0, left: '50%', transform: 'translate(-50%,-50%)', background: `rgba(15,81,50,${0.4 - i * 0.1})`, boxShadow: `0 0 8px rgba(15,81,50,${0.3})` }} />
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
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const features = [
    { icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
      title: 'AI đánh giá tuân thủ', desc: 'Phân tích theo JAKIM/HDC trong vài giây.' },
    { icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
      title: 'Tạo hồ sơ tự động', desc: 'Mẫu chuẩn, song ngữ Việt – Anh.' },
    { icon: 'M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
      title: 'Cổng Halal toàn cầu', desc: 'Tiếp cận thị trường 7 nghìn tỷ USD.' },
    { icon: 'M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z',
      title: 'Bảo mật đa tổ chức', desc: 'Vault, JWT, dữ liệu cách ly tenant.' },
  ];

  const stats = [
    { value: 13, suffix: '', label: 'Loại tài liệu' },
    { value: 100, suffix: '%', label: 'Phạm vi tiêu chuẩn' },
    { value: 4, suffix: '', label: 'Ngôn ngữ' },
    { value: 7, suffix: 'T$', label: 'Thị trường Halal' },
  ];

  return (
    <div className="relative overflow-hidden" style={{ background: '#FFFFFF' }}>
      <Particles />

      {/* ── CSS Animations ── */}
      <style>{`
        @keyframes orbit-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-20px); } }
        @keyframes glow-pulse { 0%,100% { opacity: 0.4; } 50% { opacity: 1; } }
        @keyframes slide-up { from { opacity:0; transform:translateY(60px); } to { opacity:1; transform:translateY(0); } }
      `}</style>

      {/* ── Hero (light, brand-aligned) ── */}
      <section className="relative min-h-screen grid place-items-center px-6"
        style={{ zIndex: 2, background: 'linear-gradient(180deg, #E8F5EF 0%, #F7F1E6 50%, #FFFFFF 100%)' }}>
        <OrbitRings />

        {/* Radial glow */}
        <div className="absolute w-[600px] h-[600px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(15,81,50,0.06) 0%, transparent 70%)', animation: 'glow-pulse 4s ease-in-out infinite' }} />

        <div className="relative text-center max-w-4xl py-16" style={{ zIndex: 3 }}>
          {/* Badge */}
          <FadeIn>
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full mb-8"
              style={{ background: '#FFFFFF', border: '1px solid #B7CBB8', boxShadow: '0 2px 8px rgba(15,81,50,0.06)' }}>
              <div className="w-2 h-2 rounded-full" style={{ background: '#198754', animation: 'glow-pulse 2s ease-in-out infinite' }} />
              <span className="text-xs font-semibold" style={{ color: '#0F5132' }}>Halal × AI</span>
            </div>
          </FadeIn>

          {/* Logo on neutral plaque */}
          <FadeIn delay={0.1}>
            <div className="inline-flex flex-col items-center gap-3 mb-8">
              <div className="w-28 h-28 rounded-3xl grid place-items-center p-3"
                style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', boxShadow: '0 12px 40px rgba(15,81,50,0.12)' }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/aminra-mark.svg" alt="AMINRA" className="w-full h-full object-contain" />
              </div>
              <div className="flex items-center gap-3">
                <span className="block w-10 h-px" style={{ background: '#D4AF37' }} />
                <span className="text-xs font-medium" style={{ color: '#0F5132', letterSpacing: '0.18em' }}>HALAL INTEGRITY · DIGITAL TRUST</span>
                <span className="block w-10 h-px" style={{ background: '#D4AF37' }} />
              </div>
            </div>
          </FadeIn>

          {/* Headline */}
          <FadeIn delay={0.2}>
            <h1 className="text-3xl sm:text-5xl md:text-7xl font-black tracking-tight mb-6"
              style={{ color: '#0F5132', lineHeight: 1.1 }}>
              Chứng nhận Halal,<br />
              <span style={{ color: '#198754' }}>Chuẩn quốc tế.</span>
            </h1>
          </FadeIn>

          {/* Slogan */}
          <FadeIn delay={0.35}>
            <p className="text-lg md:text-xl max-w-xl mx-auto mb-10 leading-relaxed" style={{ color: '#374151' }}>
              AI hỗ trợ doanh nghiệp Việt đạt chứng nhận Halal — <span className="font-semibold" style={{ color: '#198754' }}>nhanh hơn, chuẩn hơn</span>.
            </p>
          </FadeIn>

          {/* CTAs */}
          <FadeIn delay={0.5}>
            <div className="flex items-center justify-center gap-4 flex-wrap">
              <Link href="/business/register"
                className="px-8 py-4 rounded-2xl font-bold text-base text-white transition-all hover:scale-105 active:scale-95"
                style={{
                  background: 'linear-gradient(135deg, #0F5132, #198754)',
                  boxShadow: '0 8px 32px rgba(15,81,50,0.30)',
                }}>
                Bắt đầu miễn phí
              </Link>
              <Link href="/business/login"
                className="px-8 py-4 rounded-2xl font-bold text-base transition-all hover:scale-105"
                style={{ color: '#0F5132', border: '1.5px solid #0F5132', background: '#FFFFFF' }}>
                Đăng nhập
              </Link>
            </div>
          </FadeIn>

          {/* Scroll hint */}
          <div className="absolute bottom-8 left-1/2 -translate-x-1/2" style={{ animation: 'float 3s ease-in-out infinite' }}>
            <svg className="w-6 h-6" fill="none" stroke="#0F5132" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
          </div>
        </div>
      </section>

      {/* ── Stats Bar ── */}
      <section className="relative py-16 px-6" style={{ zIndex: 2, background: '#FFFFFF' }}>
        <div className="max-w-5xl mx-auto rounded-3xl p-8"
          style={{
            background: '#FFFFFF',
            border: '1px solid #E2E8F0',
            boxShadow: '0 20px 60px rgba(15,81,50,0.06)',
          }}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map((s, i) => (
              <FadeIn key={s.label} delay={i * 0.1}>
                <div className="text-center">
                  <div className="text-3xl md:text-4xl font-black" style={{ color: '#0F5132' }}>
                    <Counter target={s.value} suffix={s.suffix} />
                  </div>
                  <div className="text-xs mt-2 font-semibold uppercase tracking-wider" style={{ color: '#6B7280' }}>{s.label}</div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="relative py-24 px-6" style={{ zIndex: 2, background: '#F2F4F5' }}>
        <div className="max-w-6xl mx-auto">
          <FadeIn>
            <div className="text-center mb-12">
              <h2 className="text-3xl md:text-4xl font-black mb-3" style={{ color: '#0F5132' }}>Giải pháp toàn diện</h2>
              <p className="text-base" style={{ color: '#6B7280' }}>Từ hồ sơ đến chứng nhận, trên một nền tảng.</p>
            </div>
          </FadeIn>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((f, i) => (
              <FadeIn key={f.title} delay={i * 0.08}>
                <div className="rounded-2xl p-6 h-full transition-all duration-300 hover:scale-[1.02] group"
                  style={{
                    background: '#FFFFFF',
                    border: '1px solid #E2E8F0',
                    boxShadow: '0 4px 20px rgba(15,81,50,0.04)',
                  }}>
                  <div className="w-12 h-12 rounded-xl grid place-items-center mb-4 transition-all group-hover:scale-110"
                    style={{ background: '#E8F5EF', border: '1px solid #B7CBB8' }}>
                    <svg className="w-6 h-6" fill="none" stroke="#0F5132" strokeWidth="1.8" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d={f.icon} />
                    </svg>
                  </div>
                  <h3 className="text-base font-bold mb-2" style={{ color: '#0F5132' }}>{f.title}</h3>
                  <p className="text-sm leading-relaxed" style={{ color: '#6B7280' }}>{f.desc}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="relative py-24 px-6" style={{ zIndex: 2, background: '#F7F1E6' }}>
        <div className="max-w-4xl mx-auto">
          <FadeIn>
            <div className="text-center mb-12">
              <h2 className="text-3xl md:text-4xl font-black" style={{ color: '#0F5132' }}>Ba bước đến chứng nhận</h2>
            </div>
          </FadeIn>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              { step: '01', title: 'Tạo hồ sơ', desc: 'Soạn từ mẫu chuẩn JAKIM/HDC.' },
              { step: '02', title: 'AI đánh giá', desc: 'Điểm tuân thủ tức thì.' },
              { step: '03', title: 'Nộp & cấp chứng nhận', desc: 'Gửi tới tổ chức được công nhận.' },
            ].map((s, i) => (
              <FadeIn key={s.step} delay={i * 0.15}>
                <div className="text-center">
                  <div className="inline-flex items-center justify-center w-16 h-16 rounded-full mb-5"
                    style={{
                      background: '#FFFFFF',
                      border: '2px solid #D4AF37',
                      boxShadow: '0 8px 24px rgba(212,175,55,0.20)',
                    }}>
                    <span className="text-xl font-black" style={{ color: '#0F5132' }}>{s.step}</span>
                  </div>
                  <h3 className="text-lg font-bold mb-2" style={{ color: '#0F5132' }}>{s.title}</h3>
                  <p className="text-sm leading-relaxed" style={{ color: '#374151' }}>{s.desc}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA Section (60% Primary Green) ── */}
      <section className="relative py-24 px-6" style={{ zIndex: 2, background: '#FFFFFF' }}>
        <FadeIn>
          <div className="max-w-3xl mx-auto text-center rounded-3xl p-12 relative overflow-hidden"
            style={{
              background: 'linear-gradient(135deg, #0F5132 0%, #198754 100%)',
              boxShadow: '0 20px 60px rgba(15,81,50,0.30)',
            }}>
            {/* Gold radial accent */}
            <div className="absolute top-0 right-0 w-72 h-72 rounded-full"
              style={{ background: 'radial-gradient(circle, rgba(212,175,55,0.20), transparent 70%)' }} />

            <div className="relative">
              <h2 className="text-3xl md:text-4xl font-black text-white mb-6">
                Sẵn sàng đạt chứng nhận Halal?
              </h2>
              <Link href="/business/register"
                className="inline-flex items-center gap-3 px-8 py-4 rounded-2xl font-bold text-base transition-all hover:scale-105"
                style={{
                  background: '#D4AF37',
                  color: '#0F5132',
                  boxShadow: '0 8px 32px rgba(212,175,55,0.35)',
                }}>
                Đăng ký miễn phí
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </Link>
            </div>
          </div>
        </FadeIn>
      </section>

      {/* ── Footer ── */}
      <footer className="relative py-12 px-6" style={{ zIndex: 2, background: '#0A3622' }}>
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg grid place-items-center p-1" style={{ background: '#FFFFFF' }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/aminra-mark.svg" alt="AMINRA" className="w-full h-full object-contain" />
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-semibold text-white tracking-wider">AMINRA</span>
              <span className="text-[10px]" style={{ color: '#D4AF37', letterSpacing: '0.1em' }}>HALAL INTEGRITY, DIGITAL TRUST</span>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
            <Link href="/business/login" className="inline-flex items-center min-h-[32px] text-xs transition-colors hover:text-white" style={{ color: '#B7CBB8' }}>Đăng nhập Doanh nghiệp</Link>
            <Link href="/provider/login" className="inline-flex items-center min-h-[32px] text-xs transition-colors hover:text-white" style={{ color: '#B7CBB8' }}>Đăng nhập Tổ chức</Link>
            <Link href="/privacy"        className="inline-flex items-center min-h-[32px] text-xs transition-colors hover:text-white" style={{ color: '#B7CBB8' }}>Chính sách bảo mật</Link>
            <Link href="/terms"          className="inline-flex items-center min-h-[32px] text-xs transition-colors hover:text-white" style={{ color: '#B7CBB8' }}>Điều khoản</Link>
          </div>
          <p className="text-xs" style={{ color: '#94A3B8' }} suppressHydrationWarning>
            &copy; {new Date().getFullYear()} AMINRA. Mọi quyền được bảo lưu.
          </p>
        </div>
      </footer>
    </div>
  );
}
