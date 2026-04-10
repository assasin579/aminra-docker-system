import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import ClientI18nProvider from "@/components/ClientI18nProvider";
import LayoutShell from "@/components/LayoutShell";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Aminra - Halal Certification Assistant",
  description: "AI-powered platform for Halal certification consulting",
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
        <meta name="theme-color" content="#087653" />
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
      <body className={`${inter.className} min-h-full`} style={{background: '#FAFCF9'}}>
        <ClientI18nProvider>
          <LayoutShell>{children}</LayoutShell>
        </ClientI18nProvider>
      </body>
    </html>
  );
}
