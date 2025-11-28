import type { FileMetadata } from "@/types";

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
    </div>
  );
}
