"use client";

import { hypothesisFormSchema } from "@/features/input-pipeline/schemas/hypothesisSchema";
import { FormEvent, useState, useTransition } from "react";

interface UseHypothesisFormProps {
  onSuccess?: (redirectUrl?: string) => void;
}

interface UseHypothesisFormReturn {
  title: string;
  setTitle: (title: string) => void;
  idea: string;
  setIdea: (idea: string) => void;
  pending: boolean;
  error: string | null;
  handleSubmit: (event: FormEvent<HTMLFormElement>) => void;
  resetForm: () => void;
}

export function useHypothesisForm({
  onSuccess,
}: UseHypothesisFormProps = {}): UseHypothesisFormReturn {
  const [pending, startTransition] = useTransition();
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");
  const [error, setError] = useState<string | null>(null);

  const resetForm = () => {
    setTitle("");
    setIdea("");
    setError(null);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const validation = hypothesisFormSchema.safeParse({ title, idea });
    if (!validation.success) {
      setError(validation.error.issues[0]?.message || "Validation failed");
      return;
    }

    startTransition(async () => {
      setError(null);

      const response = await fetch("/api/hypotheses", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title, idea }),
      });

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        const message = (data && (data.message || data.error)) || (await response.text());
        setError(message || "Failed to create hypothesis");
        return;
      }

      resetForm();
      const redirectUrl = data?.ideation?.redirectUrl;
      onSuccess?.(redirectUrl);
    });
  };

  return {
    title,
    setTitle,
    idea,
    setIdea,
    pending,
    error,
    handleSubmit,
    resetForm,
  };
}
