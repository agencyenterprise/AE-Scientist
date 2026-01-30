import { Header } from "@/shared/components/Header";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AE Scientist",
  description:
    "Transform conversations into research proposals and automatically run multi-stage experiments to generate publication-ready papers.",
};

export const dynamic = "force-dynamic";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 px-4 py-6 sm:px-8">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-12">{children}</div>
      </main>
    </div>
  );
}
