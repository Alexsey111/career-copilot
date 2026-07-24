import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/contexts/AuthContext";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  // title.template — для дочерних layout/страниц: они могут указать
  // title="Отклики" → DOM получит "Отклики | AI Career Copilot for HH".
  // title.default — fallback для страниц без своего title (раньше был
  // плоский string, и динамические маршруты /applications, /interview,
  // /evidence давали "document-title" нарушение в axe).
  title: {
    default: "AI Career Copilot for HH",
    template: "%s | AI Career Copilot for HH",
  },
  description: "AI-powered career assistant for HeadHunter",
  // Bug#36: favicon.ico теперь существует (ранее был 404 — браузер
  // игнорировал logo.svg и показывал пустую вкладку / старый кэш).
  // Добавили apple-touch-icon + shortcut icon, чтобы точно пробить
  // локальный кэш после редизайна.
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/icon.png", type: "image/png", sizes: "512x512" },
      { url: "/logo.svg", type: "image/svg+xml" },
    ],
    shortcut: ["/favicon.ico"],
    apple: [{ url: "/icon.png", sizes: "512x512", type: "image/png" }],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ru"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-gray-50">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
