import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Geist, Geist_Mono } from "next/font/google";

import { QueryProvider } from "@/components/providers/query-provider";
import { AuthProvider } from "@/components/providers/auth-provider";
import { ToastProvider } from "@/components/ui/toast";
import { ThemeWatcher } from "@/components/providers/theme-watcher";
import { THEME_SCRIPT } from "@/lib/theme";

import "./globals.css";
import "./bizpilot.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata: Metadata = {
  title: "BizPilot AI",
  description: "Business records and a read-only AI assistant for Pakistani small businesses",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className={`${geist.variable} ${geistMono.variable}`} data-theme="light" suppressHydrationWarning>
      <head>
        {/* Sets data-theme before first paint (no white flash in dark mode). */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="bp">
        <ThemeWatcher />
        <QueryProvider>
          <AuthProvider>
            <ToastProvider>{children}</ToastProvider>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
