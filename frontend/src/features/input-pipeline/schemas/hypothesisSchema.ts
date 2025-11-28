import { z } from "zod";

export const hypothesisFormSchema = z.object({
  title: z.string().min(1, "Title is required"),
  idea: z.string().min(1, "Hypothesis details are required"),
});

export const chatGptUrlSchema = z
  .string()
  .refine(url => !url.trim() || url.includes("chatgpt.com"), {
    message: "URL must be from chatgpt.com",
  })
  .refine(url => !url.trim() || url.includes("/share/"), {
    message:
      "ChatGPT conversation must be shared and public. Click the share button in ChatGPT and use that URL.",
  });

export type HypothesisFormData = z.infer<typeof hypothesisFormSchema>;
