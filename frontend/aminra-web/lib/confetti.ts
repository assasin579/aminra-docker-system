/**
 * Confetti helpers — wrap canvas-confetti với 2 preset:
 *
 *   celebrateCert()    — long burst (3 stages) cho cert issuance success
 *   celebrateSuccess() — quick single burst cho generic success (submit, save)
 *
 * Auto no-op nếu user prefers-reduced-motion.
 */

import confetti from "canvas-confetti";

const NAVY = "#0A1F44";
const GOLD = "#C9A24A";
const GOLD_LIGHT = "#F2E6C2";
const CREAM = "#FAF7EE";

function reducedMotion(): boolean {
  if (typeof window === "undefined") return true;
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/** Celebration cho lúc cert mới được issue. ~2.5s tổng. */
export function celebrateCert() {
  if (reducedMotion()) return;

  const colors = [GOLD, NAVY, GOLD_LIGHT, CREAM];
  const duration = 2500;
  const end = Date.now() + duration;

  // Stage 1: side bursts
  (function frame() {
    confetti({
      particleCount: 4,
      angle: 60,
      spread: 70,
      origin: { x: 0, y: 0.7 },
      colors,
      scalar: 0.9,
    });
    confetti({
      particleCount: 4,
      angle: 120,
      spread: 70,
      origin: { x: 1, y: 0.7 },
      colors,
      scalar: 0.9,
    });
    if (Date.now() < end) requestAnimationFrame(frame);
  })();

  // Stage 2: center burst sau 200ms (overlap stage 1)
  setTimeout(() => {
    confetti({
      particleCount: 80,
      spread: 100,
      origin: { y: 0.55 },
      colors,
      scalar: 1.1,
      ticks: 200,
    });
  }, 200);
}

/** Quick single burst — submit form, save success. */
export function celebrateSuccess() {
  if (reducedMotion()) return;
  confetti({
    particleCount: 60,
    spread: 70,
    origin: { y: 0.65 },
    colors: [GOLD, NAVY, GOLD_LIGHT],
    scalar: 0.9,
    ticks: 150,
  });
}
