import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mismatch Desk | Invoice review",
  description: "Review invoice exceptions against purchase and delivery records.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
