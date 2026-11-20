import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Product Information | QR Product Experience",
  description: "Open product information, specifications and files from a product QR code.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
