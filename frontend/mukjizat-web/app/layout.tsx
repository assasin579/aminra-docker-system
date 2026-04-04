import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import ClientI18nProvider from "@/components/ClientI18nProvider";
import LayoutShell from "@/components/LayoutShell";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Mukjizat Saigoncert - Halal Certification Assistant",
  description: "AI-powered platform for Halal certification consulting",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full" translate="no">
      <body className={`${inter.className} min-h-full`} style={{background: '#111725'}}>
        <ClientI18nProvider>
          <LayoutShell>{children}</LayoutShell>
        </ClientI18nProvider>
      </body>
    </html>
  );
}
