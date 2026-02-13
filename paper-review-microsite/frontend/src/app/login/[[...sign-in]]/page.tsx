"use client";

import { SignIn } from "@clerk/nextjs";

export default function LoginPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-white mb-2">Paper Review</h1>
        <p className="text-slate-400">AI-Powered Academic Paper Analysis</p>
      </div>
      <SignIn
        appearance={{
          elements: {
            rootBox: "mx-auto",
            card: "bg-slate-900 border border-slate-800 shadow-xl",
            headerTitle: "text-white",
            headerSubtitle: "text-slate-400",
            formFieldLabel: "text-slate-300",
            formFieldInput:
              "bg-slate-800 border-slate-700 text-white placeholder:text-slate-500",
            formButtonPrimary:
              "bg-sky-500 hover:bg-sky-400 text-white font-medium",
            footerActionLink: "text-sky-400 hover:text-sky-300",
            dividerLine: "bg-slate-700",
            dividerText: "text-slate-500",
            socialButtonsBlockButton:
              "bg-slate-800 border-slate-700 text-white hover:bg-slate-700",
            socialButtonsBlockButtonText: "text-slate-300",
          },
        }}
        routing="path"
        path="/login"
        signUpUrl="/sign-up"
        forceRedirectUrl="/dashboard"
      />
    </div>
  );
}
