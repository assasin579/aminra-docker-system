'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Wraps internal SPA navigations in document.startViewTransition() so the
 * CSS rules in globals.css ::view-transition-old/new(root) animate the swap.
 *
 * Falls through silently on browsers without the API (Firefox <pending>, Safari < 18).
 * Honors prefers-reduced-motion by skipping the transition.
 *
 * Coexists with NavigationProgress: this prevents the default Link click and
 * routes through router.push, NavigationProgress still picks up the click.
 */
export default function ViewTransitions() {
  const router = useRouter();

  useEffect(() => {
    if (typeof document.startViewTransition !== 'function') return;

    const onClick = (e: MouseEvent) => {
      // Modifier-clicks, middle-click, etc. → let browser handle
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

      const anchor = (e.target as HTMLElement | null)?.closest?.('a');
      if (!anchor) return;
      const href = anchor.getAttribute('href');
      if (!href) return;
      if (href.startsWith('http') || href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('#')) return;
      if (anchor.getAttribute('target') === '_blank' || anchor.hasAttribute('download')) return;

      let url: URL;
      try { url = new URL(href, window.location.href); } catch { return; }
      if (url.origin !== window.location.origin) return;
      if (url.pathname === window.location.pathname && url.search === window.location.search) return;

      // Honor reduced-motion preference
      const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      if (reduce) return;

      e.preventDefault();
      const path = url.pathname + url.search + url.hash;
      const transition = document.startViewTransition!(() => {
        router.push(path);
      });

      // Fail-safe: if anything throws or the navigation hangs, abort cleanly.
      transition.finished.catch(() => {});
    };

    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, [router]);

  return null;
}
