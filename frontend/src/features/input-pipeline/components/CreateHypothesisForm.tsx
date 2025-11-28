"use client";

import {
  ConflictResolution,
  ImportStreamingCard,
  ModelLimitConflict,
  useConversationImport,
} from "@/features/conversation-import";
import { ChatGptUrlInput } from "@/features/input-pipeline/components/ChatGptUrlInput";
import { HypothesisForm } from "@/features/input-pipeline/components/HypothesisForm";
import { useManualIdeaImport } from "@/features/input-pipeline/hooks/useManualIdeaImport";
import { hypothesisFormSchema } from "@/features/input-pipeline/schemas/hypothesisSchema";
import { ModelSelector } from "@/features/model-selector/components/ModelSelector";
import { PromptTypes } from "@/shared/lib/prompt-types";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export function CreateHypothesisForm() {
  const router = useRouter();

  // Manual form state
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // Shared model selection state
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedProvider, setSelectedProvider] = useState("");
  const [currentModel, setCurrentModel] = useState("");
  const [currentProvider, setCurrentProvider] = useState("");

  // Conversation import hook for ChatGPT URL
  const importState = useConversationImport({
    autoRedirect: true,
    onSuccess: id => {
      router.push(`/conversations/${id}`);
      router.refresh();
    },
  });

  // Manual idea import hook
  const manualImportState = useManualIdeaImport({
    autoRedirect: true,
    onSuccess: id => {
      setTitle("");
      setIdea("");
      router.push(`/conversations/${id}`);
      router.refresh();
    },
    onError: error => {
      setFormError(error);
    },
  });

  const hasManualInput = title.trim() || idea.trim();
  const hasChatGptUrl = importState.state.url.trim();
  const isDisabled = importState.status.isImporting || manualImportState.status.isImporting;

  // Model selection handlers
  const handleModelChange = (model: string, provider: string) => {
    setFormError(null);
    if (model && provider) {
      setSelectedModel(model);
      setSelectedProvider(provider);
      setCurrentModel(model);
      setCurrentProvider(provider);
    } else {
      setSelectedModel("");
      setSelectedProvider("");
    }
    // Also update the conversation import hook's model state
    importState.actions.setModel(model, provider);
  };

  const handleModelDefaults = (model: string, provider: string) => {
    if (!selectedModel && !selectedProvider) {
      setCurrentModel(model);
      setCurrentProvider(provider);
    }
    // Also update the conversation import hook's model state
    importState.actions.setModelDefaults(model, provider);
  };

  const submitManualForm = () => {
    const validation = hypothesisFormSchema.safeParse({ title, idea });
    if (!validation.success) {
      setFormError(validation.error.issues[0]?.message || "Validation failed");
      return;
    }

    if (!currentModel || !currentProvider) {
      setFormError("LLM model and provider are required. Please wait for model to load.");
      return;
    }

    setFormError(null);
    manualImportState.actions.startImport(title, idea, currentModel, currentProvider);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    // Clear previous errors
    setFormError(null);

    // Prioritize ChatGPT URL if filled
    if (hasChatGptUrl) {
      importState.actions.startImport();
      return;
    }

    // Otherwise submit manual form
    if (hasManualInput) {
      submitManualForm();
      return;
    }

    // Nothing filled
    setFormError("Please fill in the hypothesis details or paste a ChatGPT URL");
  };

  // Clear the other input when one is being used
  const handleTitleChange = (value: string) => {
    setTitle(value);
    if (value.trim()) {
      importState.actions.setUrl("");
    }
  };

  const handleIdeaChange = (value: string) => {
    setIdea(value);
    if (value.trim()) {
      importState.actions.setUrl("");
    }
  };

  const handleUrlChange = (value: string) => {
    importState.actions.setUrl(value);
    if (value.trim()) {
      setTitle("");
      setIdea("");
      setFormError(null);
    }
  };

  // Handle cancel/reset from streaming view
  const handleCancelImport = () => {
    importState.actions.reset();
    manualImportState.actions.reset();
  };

  // Show streaming card when importing via ChatGPT URL
  if (importState.status.isImporting) {
    return (
      <div className="space-y-4">
        <ImportStreamingCard
          streamingContent={importState.state.streamingContent}
          currentState={importState.state.currentState}
          summaryProgress={importState.state.summaryProgress}
          isUpdateMode={importState.state.isUpdateMode}
          textareaRef={importState.streamingRef}
          showHeader={true}
          title="Importing ChatGPT Conversation"
          onClose={handleCancelImport}
          className="rounded-2xl border border-slate-800/70 bg-slate-950/60"
        />
      </div>
    );
  }

  // Show streaming card when generating from manual hypothesis
  if (manualImportState.status.isImporting) {
    return (
      <div className="space-y-4">
        <ImportStreamingCard
          streamingContent={manualImportState.state.streamingContent}
          currentState={manualImportState.state.currentState}
          summaryProgress={null}
          isUpdateMode={false}
          textareaRef={manualImportState.streamingRef}
          showHeader={true}
          title="Generating Research Idea"
          onClose={handleCancelImport}
          className="rounded-2xl border border-slate-800/70 bg-slate-950/60"
        />
      </div>
    );
  }

  // Show conflict resolution when there's a duplicate URL conflict
  if (importState.status.hasConflict) {
    return (
      <div className="rounded-2xl border border-slate-800/70 bg-slate-950/60">
        <ConflictResolution
          conflicts={importState.conflict.items}
          selectedConflictId={importState.conflict.selectedId}
          onSelectConflict={importState.actions.selectConflict}
          onGoToSelected={importState.actions.resolveConflictGoTo}
          onUpdateSelected={importState.actions.resolveConflictUpdate}
          onCreateNew={importState.actions.resolveConflictCreateNew}
          onCancel={importState.actions.cancelConflict}
          onClose={handleCancelImport}
        />
      </div>
    );
  }

  // Show model limit conflict when conversation is too large
  if (importState.status.hasModelLimitConflict) {
    return (
      <div className="rounded-2xl border border-slate-800/70 bg-slate-950/60">
        <ModelLimitConflict
          message={importState.modelLimit.message}
          suggestion={importState.modelLimit.suggestion}
          onProceed={importState.actions.proceedWithSummarization}
          onCancel={importState.actions.cancelModelLimit}
          onClose={handleCancelImport}
        />
      </div>
    );
  }

  // Combine errors from both hooks
  const displayError =
    formError || importState.state.error || manualImportState.state.error || null;

  // Default: show the form
  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <HypothesisForm
        title={title}
        idea={idea}
        onTitleChange={handleTitleChange}
        onIdeaChange={handleIdeaChange}
        disabled={isDisabled}
      />

      <div className="relative py-4">
        <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-gradient-to-r from-transparent via-slate-800/80 to-transparent" />
        <span className="relative mx-auto flex w-fit items-center gap-2 rounded-full border border-slate-800/80 bg-slate-950 px-4 py-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-400">
          or
        </span>
      </div>

      <ChatGptUrlInput
        url={importState.state.url}
        onUrlChange={handleUrlChange}
        disabled={isDisabled}
        error={importState.state.error || null}
        isExtracting={importState.status.isImporting}
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <button
            type="submit"
            className="inline-flex items-center justify-center rounded-full bg-gradient-to-r from-sky-500 via-blue-500 to-cyan-400 px-6 py-3 text-sm font-semibold text-white shadow-[0_18px_40px_-18px_rgba(56,189,248,0.65)] transition hover:from-sky-400 hover:via-blue-400 hover:to-cyan-300 focus:outline-none focus:ring-2 focus:ring-sky-300 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:opacity-40"
            disabled={isDisabled}
          >
            {importState.status.isImporting || manualImportState.status.isImporting
              ? "Generating..."
              : "Create hypothesis"}
          </button>
          <ModelSelector
            promptType={PromptTypes.IDEA_GENERATION}
            onModelChange={handleModelChange}
            onDefaultsChange={handleModelDefaults}
            selectedModel={selectedModel}
            selectedProvider={selectedProvider}
            disabled={isDisabled}
            showMakeDefault={true}
            showCapabilities={false}
          />
        </div>
        {displayError && <span className="text-sm text-rose-400">{displayError}</span>}
      </div>
    </form>
  );
}
