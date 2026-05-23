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
    <html lang="en" className="dark h-full">
      <body className={`${inter.className} bg-[#0f0f0f] text-white antialiased h-full`}>
        {children}
      </body>
    </html>
  );
}
