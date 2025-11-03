import { type RunStatus } from "@/lib/state/constants"
import { cva } from "class-variance-authority"
import { cn } from "@/lib/utils/cn"

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold",
  {
    variants: {
      status: {
        QUEUED: "bg-slate-800 text-slate-200",
        SCHEDULED: "bg-slate-800 text-slate-200",
        STARTING: "bg-slate-800 text-slate-200",
        RUNNING: "bg-blue-900/60 text-blue-200 border border-blue-600/60",
        AUTO_VALIDATING: "bg-purple-900/60 text-purple-200 border border-purple-500/70",
        AWAITING_HUMAN: "bg-amber-900/60 text-amber-100 border border-amber-500/60",
        HUMAN_VALIDATED: "bg-emerald-900/60 text-emerald-100 border border-emerald-500/60",
        COMPLETED: "bg-emerald-900/60 text-emerald-100 border border-emerald-500/60",
        FAILED: "bg-rose-900/60 text-rose-200 border border-rose-500/70",
        CANCELED: "bg-slate-800 text-slate-400"
      }
    },
    defaultVariants: {
      status: "QUEUED"
    }
  }
)

export function StatusBadge({ status }: { status: RunStatus }) {
  return <span className={cn(badgeVariants({ status }))}>{status.replace(/_/g, " ")}</span>
}
