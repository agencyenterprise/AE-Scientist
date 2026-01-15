/**
 * ScrollToLatestButton - Floating button that appears when user is not at bottom.
 * Animated entrance/exit with motion.
 */

import { motion, AnimatePresence } from "motion/react";
import { Button } from "@/shared/components/ui/button";
import { ChevronsDown } from "lucide-react";

interface ScrollToLatestButtonProps {
  visible: boolean;
  onClick: () => void;
}

export function ScrollToLatestButton({ visible, onClick }: ScrollToLatestButtonProps) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          transition={{ duration: 0.2, ease: "easeInOut" }}
          className="absolute bottom-3 right-3 z-50"
        >
          <Button
            onClick={onClick}
            size="lg"
            className="shadow-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-full px-6 py-3 flex items-center gap-2"
          >
            <ChevronsDown className="w-5 h-5" />
            Scroll to latest
          </Button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
