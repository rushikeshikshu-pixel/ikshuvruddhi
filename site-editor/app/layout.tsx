import type { Metadata } from "next";
import "./globals.css";
import { LanguageProvider } from './ui/language';

export const metadata: Metadata = {
  title: "Ikshu Intelligence | From cane to clarity",
  description: "A field-to-mill intelligence workspace for sugar mills. Organize plots, track satellite observations, compare lab quality and plan harvests.",
  icons: {
    icon: "/ikshu-icon.svg",
    shortcut: "/ikshu-icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased"><LanguageProvider>{children}</LanguageProvider></body>
    </html>
  );
}
