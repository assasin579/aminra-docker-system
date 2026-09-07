import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import ClientI18nProvider from "@/components/ClientI18nProvider";
import LayoutShell from "@/components/LayoutShell";
import NavigationProgress from "@/components/NavigationProgress";
import ViewTransitions from "@/components/ViewTransitions";
import PWAInstallPrompt from "@/components/PWAInstallPrompt";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AMINRA — Halal Integrity, Digital Trust",
  description:
    "AMINRA — Halal Integrity, Digital Trust. Nền tảng chứng nhận Halal & kiểm định thực địa, hỗ trợ doanh nghiệp tuân thủ JAKIM / BPJPH / HDC.",
  icons: {
    icon: [{ url: "/aminra-mark.png", type: "image/png" }],
    apple: [{ url: "/aminra-mark.png", type: "image/png" }],
    shortcut: "/aminra-mark.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full"
      translate="no"
      data-scroll-behavior="smooth"
    >
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#0A1F44" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta
          name="apple-mobile-web-app-status-bar-style"
          content="black-translucent"
        />
        <script src="/chunk-error-handler.js" async></script>
        <script
          dangerouslySetInnerHTML={{
            __html: `
          if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
              const isAuthCriticalRoute = new RegExp('^/(auth|admin)(/|$)').test(window.location.pathname);

              navigator.serviceWorker
                .register('/sw.js', { updateViaCache: 'none' })
                .then((registration) => {
                  registration.update().catch(() => {});

                  if (registration.waiting && isAuthCriticalRoute) {
                    // Make auth/admin fixes take over immediately instead of waiting
                    // for the user to close every old tab controlled by the stale SW.
                    registration.waiting.postMessage({ type: 'SKIP_WAITING' });
                  }
                })
                .catch(() => {});

              if (isAuthCriticalRoute && window.caches) {
                caches
                  .keys()
                  .then((keys) =>
                    Promise.all(
                      keys
                        .filter((key) => key.startsWith('aminra-') && key !== 'aminra-v6')
                        .map((key) => caches.delete(key)),
                    ),
                  )
                  .catch(() => {});
              }

              let refreshing = false;
              navigator.serviceWorker.addEventListener('controllerchange', () => {
                if (!isAuthCriticalRoute || refreshing) return;
                if (window.location.pathname.startsWith('/auth/callback')) return;
                refreshing = true;
                window.location.reload();
              });
            });
          }
        `,
          }}
        />
      </head>
      <body
        className={`${inter.className} min-h-full`}
        style={{ background: "#FFFFFF" }}
      >
        <ClientI18nProvider>
          <NavigationProgress />
          <ViewTransitions />
          <LayoutShell>{children}</LayoutShell>
          <PWAInstallPrompt />
        </ClientI18nProvider>
      </body>
    </html>
  );
}
