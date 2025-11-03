import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import Link from "next/link"
import { Sparkles } from "lucide-react"
import { Providers } from "./providers"

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans"
})

export const metadata: Metadata = {
  title: "AI Scientist Orchestrator",
  description:
    "Monitor AI scientist hypotheses, runs, validations, and artifacts powered by MongoDB state."
}

export const dynamic = "force-dynamic"

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.variable} bg-slate-950 text-slate-100`}>
        <Providers>
          <div className="flex min-h-screen flex-col">
            <Header />
            <main className="flex-1 px-4 py-6 sm:px-8">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  )
}

function Header() {
  return (
    <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-8 py-4">
        <Link href="/" className="text-lg font-semibold text-white">
          AI Scientist Orchestrator
        </Link>
        <nav className="flex items-center gap-4 text-sm text-slate-300">
          <Link className="transition hover:text-white" href="/ideation">
            Ideation Queue
          </Link>
          <Link className="transition hover:text-white" href="/validations/queue">
            Validation Queue
          </Link>
          <Link
            className="inline-flex items-center text-white gap-2 rounded-full bg-gradient-to-r from-sky-500 via-blue-500 to-cyan-400 px-4 py-1.5 font-semibold shadow-[0_18px_40px_-22px_rgba(56,189,248,0.65)] transition hover:from-sky-400 hover:via-blue-400 hover:to-cyan-300"
            href="/overview"
          >
            <Sparkles className="h-4 w-4" />
            Overview
          </Link>
        </nav>
      </div>
    </header>
  )
}
