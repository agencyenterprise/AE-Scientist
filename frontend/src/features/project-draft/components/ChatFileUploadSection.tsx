import { FileUpload } from "@/shared/components/FileUpload";
import type { FileMetadata } from "@/types";

interface ChatFileUploadSectionProps {
  conversationId: number;
  onFilesUploaded: (files: FileMetadata[]) => void;
  disabled: boolean;
  currentModel: string;
  currentProvider: string;
  modelCapabilities: {
    supportsImages: boolean;
    supportsPdfs: boolean;
  };
}

export function ChatFileUploadSection({
  conversationId,
  onFilesUploaded,
  disabled,
  currentModel,
  currentProvider,
  modelCapabilities,
}: ChatFileUploadSectionProps) {
  return (
    <div className="px-4 py-4 bg-muted border-b border-border">
      <FileUpload
        conversationId={conversationId}
        onFilesUploaded={onFilesUploaded}
        disabled={disabled}
        maxFiles={5}
        currentModel={currentModel}
        currentProvider={currentProvider}
        modelCapabilities={modelCapabilities}
      />
    </div>
  );
}
