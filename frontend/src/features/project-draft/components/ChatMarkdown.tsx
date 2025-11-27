import ReactMarkdown from "react-markdown";

import { FileAttachmentList } from "@/shared/components/FileAttachment";
import type { FileAttachment } from "@/types";

interface ChatMarkdownProps {
  content: string;
  isUser: boolean;
  attachments?: FileAttachment[];
}

export function ChatMarkdown({ content, isUser, attachments = [] }: ChatMarkdownProps) {
  // Preprocess content to preserve line breaks in chat messages
  // Add two spaces before each line break to create proper markdown line breaks
  const processedContent = content.replace(/\n/g, "  \n");

  return (
    <div>
      <ReactMarkdown
        className={`prose prose-sm ${isUser ? "prose-invert" : ""}`}
        components={{
          h1: ({ children }) => (
            <h1 className="text-base font-bold mb-1 mt-2 first:mt-0">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-sm font-semibold mb-1 mt-2 first:mt-0">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-medium mb-1 mt-1 first:mt-0">{children}</h3>
          ),
          p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="list-disc ml-4 mb-1 space-y-0.5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal ml-4 mb-1 space-y-0.5">{children}</ol>,
          li: ({ children }) => <li className="text-sm">{children}</li>,
          code: ({ children }) => (
            <code
              className={`px-1 py-0.5 rounded text-xs font-mono ${
                isUser ? "bg-primary/30" : "bg-muted"
              }`}
            >
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre
              className={`p-2 rounded text-xs font-mono mb-1 whitespace-pre-wrap break-all max-w-full ${
                isUser ? "bg-primary/30" : "bg-muted"
              }`}
              style={{ width: "100%", maxWidth: "100%", overflowWrap: "anywhere" }}
            >
              {children}
            </pre>
          ),
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          a: ({ href, children }) => (
            <a
              href={href}
              className={`hover:underline ${isUser ? "text-primary/80" : "text-primary"}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote
              className={`border-l-2 pl-2 my-1 ${isUser ? "border-primary/50" : "border-border"}`}
            >
              {children}
            </blockquote>
          ),
        }}
      >
        {processedContent}
      </ReactMarkdown>

      {/* Render file attachments */}
      {attachments.length > 0 && (
        <div className={`mt-2 ${isUser ? "text-white" : ""}`}>
          <FileAttachmentList attachments={attachments} showPreviews={true} maxItems={3} />
        </div>
      )}
    </div>
  );
}
