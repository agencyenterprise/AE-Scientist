import type { FileMetadata } from "@/types";

interface ChatPendingFilesProps {
  pendingFiles: FileMetadata[];
  onClearAll: () => void;
  onRemoveFile: (s3Key: string) => void;
}

export function ChatPendingFiles({
  pendingFiles,
  onClearAll,
  onRemoveFile,
}: ChatPendingFilesProps) {
  if (pendingFiles.length === 0) {
    return null;
  }

  return (
    <div className="px-4 py-2 bg-primary/10 border-b border-primary/30">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-primary">
          {pendingFiles.length} file{pendingFiles.length !== 1 ? "s" : ""} ready to send
        </span>
        <button onClick={onClearAll} className="text-xs text-primary hover:text-primary/80">
          Clear all
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {pendingFiles.map(file => (
          <div
            key={file.s3_key}
            className="flex items-center space-x-2 bg-card px-2 py-1 rounded border border-border"
          >
            <span className="text-sm text-foreground">{file.filename}</span>
            <button
              onClick={() => onRemoveFile(file.s3_key)}
              className="text-muted-foreground hover:text-foreground"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
