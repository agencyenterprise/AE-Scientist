import type { Metadata, Viewport } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";

import { AuthProvider } from "@/shared/contexts/AuthContext";
import { QueryProvider } from "@/shared/providers/QueryProvider";

import "./globals.css";

export const metadata: Metadata = {
  title: "AE Paper Review",
  description:
    "Get comprehensive AI-powered reviews of your academic papers with detailed analysis, scores, and recommendations.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" className="dark">
        <body
          className={`${GeistSans.variable} ${GeistMono.variable} antialiased min-h-screen bg-background text-foreground`}
        >
          <QueryProvider>
            <AuthProvider>{children}</AuthProvider>
          </QueryProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
