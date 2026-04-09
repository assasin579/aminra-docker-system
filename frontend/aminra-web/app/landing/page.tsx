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
        ctx.fillStyle = `rgba(8, 118, 83, ${p.o})`;
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
            ctx.strokeStyle = `rgba(8, 118, 83, ${0.06 * (1 - dist / 150)})`;
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
            border: `1px solid rgba(8,118,83,${0.12 - i * 0.03})`,
            animation: `orbit-spin ${20 + i * 10}s linear infinite ${i % 2 === 0 ? '' : 'reverse'}`,
          }}>
          <div className="absolute w-2 h-2 rounded-full"
            style={{ top: 0, left: '50%', transform: 'translate(-50%,-50%)', background: `rgba(8,118,83,${0.4 - i * 0.1})`, boxShadow: `0 0 8px rgba(8,118,83,${0.3})` }} />
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
      title: 'Đánh giá tuân thủ bằng AI', desc: 'Phân tích tài liệu Halal theo tiêu chuẩn JAKIM/HDC trong vài giây, thay vì hàng tuần.' },
    { icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
      title: 'Tạo hồ sơ thông minh', desc: 'Tự động tạo tài liệu đạt chuẩn từ mẫu chuyên nghiệp — hỗ trợ song ngữ Việt/Anh.' },
    { icon: 'M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
      title: 'Cổng Halal toàn cầu', desc: 'Kết nối doanh nghiệp Việt Nam với thị trường Halal 7 nghìn tỷ USD theo chuẩn quốc tế.' },
    { icon: 'M13 10V3L4 14h7v7l9-11h-7z',
      title: 'Chấm điểm tức thì', desc: 'Điểm tuân thủ theo thời gian thực kèm phân tích chi tiết — nắm rõ vị trí của bạn.' },
    { icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z',
      title: 'Cộng tác đa vai trò', desc: 'Chủ doanh nghiệp, thành viên và kiểm toán viên cùng làm việc trên một nền tảng.' },
    { icon: 'M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z',
      title: 'Bảo mật doanh nghiệp', desc: 'Hệ thống Vault, xác thực JWT và kiến trúc dữ liệu cách ly theo từng tổ chức.' },
  ];

  const stats = [
    { value: 13, suffix: '', label: 'Loại tài liệu' },
    { value: 100, suffix: '%', label: 'Phạm vi tiêu chuẩn' },
    { value: 4, suffix: '', label: 'Ngôn ngữ' },
    { value: 7, suffix: 'T$', label: 'Thị trường Halal' },
  ];

  return (
    <div className="relative overflow-hidden" style={{ background: '#060d1a' }}>
      <Particles />

      {/* ── CSS Animations ── */}
      <style>{`
        @keyframes orbit-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-20px); } }
        @keyframes glow-pulse { 0%,100% { opacity: 0.4; } 50% { opacity: 1; } }
        @keyframes gradient-shift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
        @keyframes slide-up { from { opacity:0; transform:translateY(60px); } to { opacity:1; transform:translateY(0); } }
      `}</style>

      {/* ── Hero ── */}
      <section className="relative min-h-screen grid place-items-center px-6" style={{ zIndex: 2 }}>
        <OrbitRings />

        {/* Radial glow */}
        <div className="absolute w-[600px] h-[600px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(8,118,83,0.08) 0%, transparent 70%)', animation: 'glow-pulse 4s ease-in-out infinite' }} />

        <div className="relative text-center max-w-4xl" style={{ zIndex: 3 }}>
          {/* Badge */}
          <FadeIn>
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full mb-8"
              style={{ background: 'rgba(8,118,83,0.08)', border: '1px solid rgba(8,118,83,0.2)' }}>
              <div className="w-2 h-2 rounded-full" style={{ background: '#10B981', animation: 'glow-pulse 2s ease-in-out infinite' }} />
              <span className="text-xs font-medium" style={{ color: '#10B981' }}>Nền tảng Chứng nhận Halal bằng AI</span>
            </div>
          </FadeIn>

          {/* Logo */}
          <FadeIn delay={0.1}>
            <div className="inline-flex items-center gap-4 mb-6">
              <div className="w-16 h-16 rounded-2xl grid place-items-center" style={{ background: '#087653', boxShadow: '0 0 40px rgba(8,118,83,0.3)' }}>
                <span className="text-white font-black text-3xl">A</span>
              </div>
            </div>
          </FadeIn>

          {/* Headline */}
          <FadeIn delay={0.2}>
            <h1 className="text-3xl sm:text-5xl md:text-7xl font-black tracking-tight mb-6"
              style={{
                background: 'linear-gradient(135deg, #ffffff 0%, #10B981 40%, #087653 60%, #065E43 100%)',
                backgroundSize: '200% 200%',
                animation: 'gradient-shift 6s ease infinite',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                lineHeight: 1.1,
              }}>
              Chứng nhận Halal,<br />Chuẩn quốc tế.
            </h1>
          </FadeIn>

          {/* Slogan */}
          <FadeIn delay={0.35}>
            <p className="text-lg md:text-xl max-w-2xl mx-auto mb-10 leading-relaxed" style={{ color: '#94a3b8' }}>
              Nền tảng AI giúp doanh nghiệp Việt Nam kết nối với
              <span className="font-semibold text-white"> thị trường Halal toàn cầu</span>.
              Từ hồ sơ đến chứng nhận — <span style={{ color: '#10B981' }}>nhanh hơn, thông minh hơn, chuẩn hơn</span>.
            </p>
          </FadeIn>

          {/* CTAs */}
          <FadeIn delay={0.5}>
            <div className="flex items-center justify-center gap-4 flex-wrap">
              <Link href="/business/register"
                className="px-8 py-4 rounded-2xl font-bold text-base text-white transition-all hover:scale-105 active:scale-95"
                style={{
                  background: 'linear-gradient(135deg, #065E43, #087653)',
                  boxShadow: '0 8px 32px rgba(8,118,83,0.35), 0 0 0 1px rgba(8,118,83,0.2)',
                }}>
                Bắt đầu miễn phí
              </Link>
              <Link href="/business/login"
                className="px-8 py-4 rounded-2xl font-bold text-base transition-all hover:scale-105"
                style={{ color: '#94a3b8', border: '1px solid rgba(8,118,83,0.15)', background: 'rgba(15,30,53,0.5)', backdropFilter: 'blur(8px)' }}>
                Đăng nhập
              </Link>
            </div>
          </FadeIn>

          {/* Scroll hint */}
          <div className="absolute bottom-8 left-1/2 -translate-x-1/2" style={{ animation: 'float 3s ease-in-out infinite' }}>
            <svg className="w-6 h-6" fill="none" stroke="#334155" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
          </div>
        </div>
      </section>

      {/* ── Stats Bar ── */}
      <section className="relative py-16 px-6" style={{ zIndex: 2 }}>
        <div className="max-w-5xl mx-auto rounded-3xl p-8"
          style={{
            background: 'linear-gradient(135deg, rgba(15,34,54,0.9), rgba(22,40,71,0.9))',
            border: '1px solid rgba(8,118,83,0.15)',
            backdropFilter: 'blur(20px)',
            boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          }}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map((s, i) => (
              <FadeIn key={s.label} delay={i * 0.1}>
                <div className="text-center">
                  <div className="text-3xl md:text-4xl font-black" style={{ color: '#10B981' }}>
                    <Counter target={s.value} suffix={s.suffix} />
                  </div>
                  <div className="text-xs mt-2 font-medium" style={{ color: '#94a3b8' }}>{s.label}</div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="relative py-24 px-6" style={{ zIndex: 2 }}>
        <div className="max-w-6xl mx-auto">
          <FadeIn>
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-black text-white mb-4">Giải pháp toàn diện</h2>
              <p className="text-base max-w-xl mx-auto" style={{ color: '#94a3b8' }}>
                Quy trình chứng nhận Halal trọn vẹn — từ soạn thảo hồ sơ đến nộp hồ sơ cho tổ chức chứng nhận.
              </p>
            </div>
          </FadeIn>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((f, i) => (
              <FadeIn key={f.title} delay={i * 0.08}>
                <div className="rounded-2xl p-6 h-full transition-all duration-300 hover:scale-[1.02] group"
                  style={{
                    background: 'linear-gradient(135deg, rgba(15,30,53,0.8), rgba(10,22,40,0.8))',
                    border: '1px solid rgba(8,118,83,0.15)',
                    backdropFilter: 'blur(10px)',
                  }}>
                  <div className="w-12 h-12 rounded-xl grid place-items-center mb-4 transition-all group-hover:scale-110"
                    style={{ background: 'rgba(8,118,83,0.1)', border: '1px solid rgba(8,118,83,0.2)' }}>
                    <svg className="w-6 h-6" fill="none" stroke="#10B981" strokeWidth="1.8" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d={f.icon} />
                    </svg>
                  </div>
                  <h3 className="text-base font-bold text-white mb-2">{f.title}</h3>
                  <p className="text-sm leading-relaxed" style={{ color: '#94a3b8' }}>{f.desc}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="relative py-24 px-6" style={{ zIndex: 2 }}>
        <div className="max-w-4xl mx-auto">
          <FadeIn>
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-black text-white mb-4">Ba bước đến chứng nhận</h2>
              <p className="text-base" style={{ color: '#94a3b8' }}>Đơn giản, minh bạch và nhanh chóng.</p>
            </div>
          </FadeIn>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              { step: '01', title: 'Tạo hồ sơ', desc: 'Tạo tài liệu Halal đạt chuẩn từ mẫu chuyên nghiệp, thông tin doanh nghiệp tự động điền sẵn.' },
              { step: '02', title: 'Đánh giá bằng AI', desc: 'Nhận điểm tuân thủ tức thì cùng phản hồi chi tiết từ AI được huấn luyện theo tiêu chuẩn Halal.' },
              { step: '03', title: 'Nộp & Chứng nhận', desc: 'Gửi bộ hồ sơ hoàn chỉnh trực tiếp đến tổ chức chứng nhận Halal được công nhận.' },
            ].map((s, i) => (
              <FadeIn key={s.step} delay={i * 0.15}>
                <div className="text-center">
                  <div className="inline-flex items-center justify-center w-16 h-16 rounded-full mb-5"
                    style={{
                      background: 'linear-gradient(135deg, rgba(8,118,83,0.15), rgba(8,118,83,0.05))',
                      border: '2px solid rgba(8,118,83,0.2)',
                      boxShadow: '0 0 30px rgba(8,118,83,0.1)',
                    }}>
                    <span className="text-xl font-black" style={{ color: '#10B981' }}>{s.step}</span>
                  </div>
                  <h3 className="text-lg font-bold text-white mb-2">{s.title}</h3>
                  <p className="text-sm leading-relaxed" style={{ color: '#94a3b8' }}>{s.desc}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA Section ── */}
      <section className="relative py-24 px-6" style={{ zIndex: 2 }}>
        <FadeIn>
          <div className="max-w-3xl mx-auto text-center rounded-3xl p-12 relative overflow-hidden"
            style={{
              background: 'linear-gradient(135deg, #0a1628, #112240)',
              border: '1px solid rgba(8,118,83,0.2)',
              boxShadow: '0 0 80px rgba(8,118,83,0.08)',
            }}>
            {/* Glow */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 rounded-full"
              style={{ background: 'radial-gradient(circle, rgba(8,118,83,0.12), transparent)' }} />

            <div className="relative">
              <h2 className="text-3xl md:text-4xl font-black text-white mb-4">
                Sẵn sàng chinh phục Halal?
              </h2>
              <p className="text-base mb-8 max-w-lg mx-auto" style={{ color: '#94a3b8' }}>
                Cùng hàng trăm doanh nghiệp Việt Nam xây dựng hành trình chứng nhận Halal với AMINRA.
              </p>
              <Link href="/business/register"
                className="inline-flex items-center gap-3 px-8 py-4 rounded-2xl font-bold text-base text-white transition-all hover:scale-105"
                style={{
                  background: 'linear-gradient(135deg, #065E43, #087653)',
                  boxShadow: '0 8px 32px rgba(8,118,83,0.4)',
                }}>
                Bắt đầu ngay
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </Link>
            </div>
          </div>
        </FadeIn>
      </section>

      {/* ── Footer ── */}
      <footer className="relative py-12 px-6" style={{ zIndex: 2, borderTop: '1px solid rgba(8,118,83,0.15)' }}>
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg grid place-items-center" style={{ background: '#087653' }}>
              <span className="text-white font-bold text-sm">A</span>
            </div>
            <span className="text-sm font-semibold text-white">AMINRA</span>
            <span className="text-xs" style={{ color: '#334155' }}>Chứng nhận Halal bằng AI</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/business/login" className="text-xs transition-colors hover:text-white" style={{ color: '#5B6B7D' }}>Đăng nhập Doanh nghiệp</Link>
            <Link href="/provider/login" className="text-xs transition-colors hover:text-white" style={{ color: '#5B6B7D' }}>Đăng nhập Tổ chức</Link>
          </div>
          <p className="text-xs" style={{ color: '#1e3a5f' }} suppressHydrationWarning>
            &copy; {new Date().getFullYear()} AMINRA. Mọi quyền được bảo lưu.
          </p>
        </div>
      </footer>
    </div>
  );
}
