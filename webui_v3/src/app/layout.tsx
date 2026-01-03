import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Grid Trading Bot - WebUI v3",
  description: "Comprehensive control panel for automated grid trading",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
