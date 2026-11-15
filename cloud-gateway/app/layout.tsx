import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RDC | Independent agent workspace",
  description: "Connect your own device to RDC and follow its work in an embedded AI preview.",
  icons: {
    icon: "/rdc-logo.png",
    shortcut: "/rdc-logo.png",
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
