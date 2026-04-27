import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import ClientI18nProvider from "@/components/ClientI18nProvider";
import LayoutShell from "@/components/LayoutShell";
import PWAInstallPrompt from "@/components/PWAInstallPrompt";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AMINRA — Halal Integrity, Digital Trust",
  description: "AMINRA — Halal Integrity, Digital Trust. Nền tảng chứng nhận Halal & kiểm định thực địa, hỗ trợ doanh nghiệp tuân thủ JAKIM / BPJPH / HDC.",
  icons: {
    icon: [{ url: "/aminra-mark.svg", type: "image/svg+xml" }],
    apple: [{ url: "/aminra-mark.svg", type: "image/svg+xml" }],
    shortcut: "/aminra-mark.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full" translate="no">
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#0F5132" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <script src="/chunk-error-handler.js" async></script>
        <script dangerouslySetInnerHTML={{ __html: `
          if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
              navigator.serviceWorker.register('/sw.js').catch(() => {});
            });
          }
        `}} />
      </head>
      <body className={`${inter.className} min-h-full`} style={{background: '#FFFFFF'}}>
        <ClientI18nProvider>
          <LayoutShell>{children}</LayoutShell>
          <PWAInstallPrompt />
        </ClientI18nProvider>
      </body>
    </html>
  );
}
