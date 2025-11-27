import { ModelSelector } from "@/features/model-selector/components/ModelSelector";
import { PromptTypes } from "@/shared/lib/prompt-types";

interface ChatHeaderProps {
  selectedModel: string;
  selectedProvider: string;
  isReadOnly: boolean;
  isStreaming: boolean;
  effectiveCapabilities: {
    hasImages?: boolean;
    hasPdfs?: boolean;
  };
  onModelChange: (model: string, provider: string) => void;
  onDefaultsChange: (model: string, provider: string) => void;
  onCapabilitiesChange: (capabilities: { supportsImages: boolean; supportsPdfs: boolean }) => void;
  onOpenPromptModal?: () => void;
}

export function ChatHeader({
  selectedModel,
  selectedProvider,
  isReadOnly,
  isStreaming,
  effectiveCapabilities,
  onModelChange,
  onDefaultsChange,
  onCapabilitiesChange,
  onOpenPromptModal,
}: ChatHeaderProps) {
  return (
    <div className="flex-shrink-0 px-4 pt-2 pb-1 border-b border-border bg-gradient-to-r from-muted to-muted/80">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <div className="flex flex-row md:flex-col items-baseline gap-1">
            <h3 className="text-sm font-medium text-foreground">Project Chat</h3>
            <span className="text-xs text-muted-foreground">Discuss and refine with AI</span>
          </div>
        </div>
        <div className="flex items-center space-x-2 md:mt-0 mt-1">
          <ModelSelector
            promptType={PromptTypes.IDEA_CHAT}
            onModelChange={onModelChange}
            onDefaultsChange={onDefaultsChange}
            onCapabilitiesChange={onCapabilitiesChange}
            selectedModel={selectedModel}
            selectedProvider={selectedProvider}
            disabled={isReadOnly || isStreaming}
            showMakeDefault={true}
            conversationCapabilities={effectiveCapabilities}
          />
          {onOpenPromptModal && !isReadOnly && (
            <button
              onClick={onOpenPromptModal}
              className="flex items-center space-x-1 px-2 py-1 text-xs font-medium text-[var(--primary-700)] hover:bg-[var(--muted)] rounded border border-[var(--border)] transition-colors"
              title="Configure AI prompts"
            >
              <span>⚙️</span>
              <span>AI Config</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
