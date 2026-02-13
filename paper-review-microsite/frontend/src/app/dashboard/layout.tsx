"use client";

import { useAuth } from "@clerk/nextjs";
import { redirect } from "next/navigation";

import { Header } from "@/shared/components/Header";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isLoaded, isSignedIn } = useAuth();

  if (!isLoaded) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-500" />
      </div>
    );
  }

  if (!isSignedIn) {
    redirect("/login");
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 container mx-auto max-w-5xl px-3 sm:px-4 py-4 sm:py-8">
        {children}
      </main>
      <footer className="border-t border-slate-800 py-4">
        <div className="container mx-auto max-w-5xl px-4 text-center text-sm text-slate-500">
          AE Paper Review
        </div>
      </footer>
    </div>
  );
}
