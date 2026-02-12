"use client";

import { createPortal } from "react-dom";
import { useRef, useState, useEffect } from "react";
import { useAuth } from "@/shared/hooks/useAuth";
import { useRouter } from "next/navigation";
import { MCPIntegrationModal } from "@/features/mcp-integration/components/MCPIntegrationModal";
import { Plug } from "lucide-react";

function getInitials(name: string): string {
  return name
    .split(" ")
    .map(n => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

export function UserProfileDropdown() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [isMCPModalOpen, setIsMCPModalOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [coords, setCoords] = useState({ top: 0, right: 0 });

  useEffect(() => {
    if (isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setCoords({
        top: rect.bottom + 8,
        right: window.innerWidth - rect.right,
      });
    }
  }, [isOpen]);

  if (!user) return null;

  const initials = getInitials(user.name);

  return (
    <>
      <button
        ref={buttonRef}
        onClick={() => setIsOpen(!isOpen)}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-700 text-sm font-medium text-white transition-colors hover:bg-slate-600"
      >
        {initials}
      </button>

      {isOpen &&
        createPortal(
          <>
            <div className="fixed inset-0 z-[55]" onClick={() => setIsOpen(false)} />
            <div
              className="fixed z-[60] w-64 rounded-md border border-slate-700 bg-slate-800 shadow-lg"
              style={{ top: coords.top, right: coords.right }}
            >
              <div className="border-b border-slate-700 px-4 py-3">
                <p className="text-sm font-medium text-white">{user.name}</p>
                <p className="text-xs text-slate-400">{user.email}</p>
              </div>
              <div className="p-2">
                <button
                  onClick={() => {
                    router.push("/billing");
                    setIsOpen(false);
                  }}
                  className="w-full rounded px-3 py-2 text-left text-sm text-slate-300 transition-colors hover:bg-slate-700 hover:text-white"
                >
                  Billing
                </button>
                <button
                  onClick={() => {
                    setIsOpen(false);
                    setIsMCPModalOpen(true);
                  }}
                  className="w-full rounded px-3 py-2 text-left text-sm text-slate-300 transition-colors hover:bg-slate-700 hover:text-white flex items-center gap-2"
                >
                  <Plug className="h-4 w-4" />
                  Integrate with Claude/Cursor
                </button>
                <button
                  onClick={() => {
                    logout();
                    setIsOpen(false);
                  }}
                  className="w-full rounded px-3 py-2 text-left text-sm text-slate-300 transition-colors hover:bg-slate-700 hover:text-white"
                >
                  Logout
                </button>
              </div>
            </div>
          </>,
          document.body
        )}

      {/* MCP Integration Modal - rendered outside dropdown so it persists when dropdown closes */}
      <MCPIntegrationModal open={isMCPModalOpen} onOpenChange={setIsMCPModalOpen} />
    </>
  );
}
