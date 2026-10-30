"use client";

import { useEffect, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const DISMISS_KEY = "aminra_pwa_install_dismissed_at";
const DISMISS_DAYS = 14;

export default function PWAInstallPrompt() {
  const [evt, setEvt] = useState<BeforeInstallPromptEvent | null>(null);
  const [iosVisible, setIosVisible] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const dismissedAt = Number(localStorage.getItem(DISMISS_KEY) || 0);
    const dismissAge = (Date.now() - dismissedAt) / 86400000;
    if (dismissedAt && dismissAge < DISMISS_DAYS) return;

    // Already running as installed PWA
    const standalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      (window.navigator as Navigator & { standalone?: boolean }).standalone ===
        true;
    if (standalone) return;

    const isIOS =
      /iphone|ipad|ipod/i.test(navigator.userAgent) &&
      !/crios|fxios/i.test(navigator.userAgent);
    if (isIOS) {
      setIosVisible(true);
      return;
    }

    const onBeforeInstall = (e: Event) => {
      e.preventDefault();
      setEvt(e as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    return () =>
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
  }, []);

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
    setEvt(null);
    setIosVisible(false);
  };

  const install = async () => {
    if (!evt) return;
    await evt.prompt();
    await evt.userChoice;
    dismiss();
  };

  if (!evt && !iosVisible) return null;

  return (
    <div
      className="fixed bottom-4 left-4 right-4 sm:left-auto sm:right-4 sm:w-80 z-50 rounded-2xl p-4 shadow-lg animate-modal-content"
      style={{
        background: "#FFFFFF",
        border: "1px solid #E2E8F0",
        boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
      }}
    >
      <div className="flex items-start gap-3">
        <div
          className="w-10 h-10 rounded-xl grid place-items-center flex-shrink-0"
          style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/aminra-mark.png" alt="AMINRA" className="w-7 h-7" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold" style={{ color: "#0A1F44" }}>
            Cài AMINRA lên màn hình chính
          </p>
          {iosVisible ? (
            <p
              className="text-xs mt-1 leading-relaxed"
              style={{ color: "#64748B" }}
            >
              Trên iPhone: bấm nút <strong>Share</strong> ở thanh dưới, sau đó
              chọn <strong>Add to Home Screen</strong>.
            </p>
          ) : (
            <p className="text-xs mt-1" style={{ color: "#64748B" }}>
              Mở nhanh hơn, nhận thông báo, dùng được khi mất sóng.
            </p>
          )}
          <div className="flex gap-2 mt-3">
            {!iosVisible && (
              <button
                onClick={install}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white transition-all duration-200 ease-out hover:scale-105"
                style={{ background: "#0A1F44" }}
              >
                Cài đặt
              </button>
            )}
            <button
              onClick={dismiss}
              className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
              style={{
                background: "#F5F1E8",
                color: "#6B7280",
                border: "1px solid #E2E8F0",
              }}
            >
              Để sau
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
