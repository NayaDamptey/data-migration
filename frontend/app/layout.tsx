import type { ReactNode } from "react";
import { Inter } from "next/font/google";
import "./globals.css";
import { StoreProvider } from "../lib/store";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata = { title: "Migryr" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <StoreProvider>{children}</StoreProvider>
      </body>
    </html>
  );
}
