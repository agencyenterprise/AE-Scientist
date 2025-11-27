import type { FileMetadata } from "@/types";
import { ModelSelector } from "@/features/model-selector/components/ModelSelector";
import { PromptTypes } from "@/shared/lib/prompt-types";

import { ChatErrorBanner } from "./ChatErrorBanner";
import { ChatFileUploadSection } from "./ChatFileUploadSection";
import { ChatPendingFiles } from "./ChatPendingFiles";
import { ChatInput } from "./ChatInput";

interface ChatInputAreaProps {
  conversationId: number;
  error: string | null;
  showFileUpload: boolean;
  pendingFiles: FileMetadata[];
  inputMessage: string;
  isLoadingHistory: boolean;
  isStreaming: boolean;
  currentModel: string;
  currentProvider: string;
  modelCapabilities: {
    supportsImages: boolean;
    supportsPdfs: boolean;
  };
  onFilesUploaded: (files: FileMetadata[]) => void;
  onClearAllFiles: () => void;
  onRemoveFile: (s3Key: string) => void;
  onInputChange: (value: string) => void;
  onSendMessage: () => void;
  onToggleFileUpload: () => void;
  inputRef?: React.RefObject<HTMLTextAreaElement | null>;
  // Model selector props
  selectedModel: string;
  selectedProvider: string;
  isReadOnly: boolean;
  onModelChange: (model: string, provider: string) => void;
  onDefaultsChange: (model: string, provider: string) => void;
  onCapabilitiesChange: (capabilities: { supportsImages: boolean; supportsPdfs: boolean }) => void;
  onOpenPromptModal?: () => void;
  effectiveCapabilities: {
    hasImages?: boolean;
    hasPdfs?: boolean;
  };
}

export function ChatInputArea({
  conversationId,
  error,
  showFileUpload,
  pendingFiles,
  inputMessage,
  isLoadingHistory,
  isStreaming,
  currentModel,
  currentProvider,
  modelCapabilities,
  onFilesUploaded,
  onClearAllFiles,
  onRemoveFile,
  onInputChange,
  onSendMessage,
  onToggleFileUpload,
  inputRef,
  selectedModel,
  selectedProvider,
  isReadOnly,
  onModelChange,
  onDefaultsChange,
  onCapabilitiesChange,
  onOpenPromptModal,
  effectiveCapabilities,
}: ChatInputAreaProps) {
  return (
    <div className="flex-shrink-0 rounded-2xl border border-slate-800">
      {error && <ChatErrorBanner error={error} />}

      {showFileUpload && (
        <ChatFileUploadSection
          conversationId={conversationId}
          onFilesUploaded={onFilesUploaded}
          disabled={isStreaming}
          currentModel={currentModel}
          currentProvider={currentProvider}
          modelCapabilities={modelCapabilities}
        />
      )}

      <ChatPendingFiles
        pendingFiles={pendingFiles}
        onClearAll={onClearAllFiles}
        onRemoveFile={onRemoveFile}
      />

      <ChatInput
        inputMessage={inputMessage}
        onInputChange={onInputChange}
        onSendMessage={onSendMessage}
        onToggleFileUpload={onToggleFileUpload}
        isLoadingHistory={isLoadingHistory}
        isStreaming={isStreaming}
        currentModel={currentModel}
        showFileUpload={showFileUpload}
        pendingFilesCount={pendingFiles.length}
        inputRef={inputRef}
      />

      {/* Settings row below input */}
      <div className="flex items-center justify-between px-4 py-2 ">
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
      </div>
    </div>
  );
}
