import { useEffect, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/components/ui/tooltip";

interface CopyToClipboardButtonProps {
  text: string;
  label: string;
}

export function CopyToClipboardButton({ text, label }: CopyToClipboardButtonProps) {
  const [copied, setCopied] = useState(false);
  const timeoutIdRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutIdRef.current !== null) {
        window.clearTimeout(timeoutIdRef.current);
        timeoutIdRef.current = null;
      }
    };
  }, []);

  const handleCopy = async () => {
    if (!text.trim()) {
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      if (timeoutIdRef.current !== null) {
        window.clearTimeout(timeoutIdRef.current);
      }
      timeoutIdRef.current = window.setTimeout(() => {
        timeoutIdRef.current = null;
        setCopied(false);
      }, 1500);
    } catch {
      // Ignore clipboard errors (e.g. not granted); keep UI silent.
    }
  };

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={handleCopy}
          disabled={!text.trim()}
          aria-label={copied ? "Copied" : label}
          className="text-slate-300 hover:text-white"
        >
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        <p className="text-xs">{copied ? "Copied" : label}</p>
      </TooltipContent>
    </Tooltip>
  );
}

