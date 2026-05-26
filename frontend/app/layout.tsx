import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Learn-AI — Learn anything, visually",
  description: "AI-powered visual learning with adaptive quizzes and animated explanations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    /*
     * suppressHydrationWarning — the inline script below sets data-theme
     * before React hydrates, so the attribute differs between SSR and client.
     * Suppressing avoids a harmless console warning.
     *
     * data-theme="dark" — default applied on the server so first-time
     * visitors never see a flash of wrong colours (script corrects it
     * synchronously on the client if the user has a saved preference).
     */
    <html lang="en" className="h-full" data-theme="dark" suppressHydrationWarning>
      <head>
        {/* Anti-flash: read saved theme from localStorage and apply BEFORE paint */}
        <script dangerouslySetInnerHTML={{ __html: `
          try {
            var t = localStorage.getItem('learnai-theme') || 'dark';
            document.documentElement.setAttribute('data-theme', t);
          } catch(e) {}
        `}} />
      </head>
      <body className={`${inter.className} bg-[var(--bg)] text-[var(--tx1)] antialiased h-full`}>
        {children}
      </body>
    </html>
  );
}
