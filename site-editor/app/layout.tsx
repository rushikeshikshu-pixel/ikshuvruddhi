import type { Metadata } from "next";
import "./globals.css";

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
      <body className="antialiased">{children}</body>
    </html>
  );
}
