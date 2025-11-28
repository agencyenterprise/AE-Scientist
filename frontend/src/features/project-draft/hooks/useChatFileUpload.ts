import { useState, useMemo, useCallback } from "react";

import type { ChatMessage, FileMetadata } from "@/types";

interface ConversationCapabilities {
  hasImages?: boolean;
  hasPdfs?: boolean;
}

interface ChatFileUploadState {
  pendingFiles: FileMetadata[];
  showFileUpload: boolean;
  effectiveCapabilities: ConversationCapabilities;
}

interface ChatFileUploadActions {
  handleFilesUploaded: (files: FileMetadata[]) => void;
  removePendingFile: (s3Key: string) => void;
  clearPendingFiles: () => void;
  setShowFileUpload: (show: boolean) => void;
  toggleFileUpload: () => void;
  consumePendingFiles: () => FileMetadata[];
}

interface UseChatFileUploadOptions {
  conversationCapabilities?: ConversationCapabilities;
  messages: ChatMessage[];
}

export function useChatFileUpload({
  conversationCapabilities,
  messages,
}: UseChatFileUploadOptions): ChatFileUploadState & ChatFileUploadActions {
  const [pendingFiles, setPendingFiles] = useState<FileMetadata[]>([]);
  const [showFileUpload, setShowFileUpload] = useState(false);

  // Compute effective capabilities by merging conversation capabilities with current session uploads
  const effectiveCapabilities = useMemo(() => {
    // Check if there are any images in pending files
    const hasUploadedImages = pendingFiles.some(file => file.file_type.startsWith("image/"));

    // Check if there are any PDFs in pending files
    const hasUploadedPdfs = pendingFiles.some(file => file.file_type === "application/pdf");

    // Check if there are any images in sent messages during this session
    const hasSentImages = messages.some(message =>
      message.attachments?.some(attachment => attachment.file_type.startsWith("image/"))
    );

    // Check if there are any PDFs in sent messages during this session
    const hasSentPdfs = messages.some(message =>
      message.attachments?.some(attachment => attachment.file_type === "application/pdf")
    );

    return {
      hasImages: conversationCapabilities?.hasImages || hasUploadedImages || hasSentImages,
      hasPdfs: conversationCapabilities?.hasPdfs || hasUploadedPdfs || hasSentPdfs,
    };
  }, [conversationCapabilities, pendingFiles, messages]);

  const handleFilesUploaded = useCallback((files: FileMetadata[]) => {
    setPendingFiles(prev => [...prev, ...files]);
  }, []);

  const removePendingFile = useCallback((s3Key: string) => {
    setPendingFiles(prev => prev.filter(file => file.s3_key !== s3Key));
  }, []);

  const clearPendingFiles = useCallback(() => {
    setPendingFiles([]);
  }, []);

  const toggleFileUpload = useCallback(() => {
    setShowFileUpload(prev => !prev);
  }, []);

  // Consume pending files and clear them (used when sending a message)
  const consumePendingFiles = useCallback(() => {
    const files = [...pendingFiles];
    setPendingFiles([]);
    setShowFileUpload(false);
    return files;
  }, [pendingFiles]);

  return {
    pendingFiles,
    showFileUpload,
    effectiveCapabilities,
    handleFilesUploaded,
    removePendingFile,
    clearPendingFiles,
    setShowFileUpload,
    toggleFileUpload,
    consumePendingFiles,
  };
}
