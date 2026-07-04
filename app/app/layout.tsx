import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

// Inter — a clean, corporate grotesk close in spirit to Goldman Sans.
const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Volatility-Control Treasury — Risk Terminal",
  description:
    "Interaktives Backtesting für volatilitätsgesteuerte Treasury-Strategien mit digitalen Assets. Alle Zahlen stammen aus der Python-Engine.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de" className={inter.variable} suppressHydrationWarning>
      <head>
        {/* Apply the saved theme before paint — no flash of the wrong mode. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{if(localStorage.getItem('theme')==='dark')document.documentElement.classList.add('dark')}catch(e){}",
          }}
        />
      </head>
      <body>
        {/* Slim navy accent bar — a quiet institutional signature. */}
        <div style={{ height: 3, background: "var(--color-navy)" }} />
        {children}
      </body>
    </html>
  );
}
