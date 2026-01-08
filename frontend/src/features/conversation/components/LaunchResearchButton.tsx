import { CreateProjectModal } from "@/features/project-draft/components/CreateProjectModal";
import { Button } from "@/shared/components/ui/button";
import { useLaunchResearch } from "../hooks/useLaunchResearch";

interface LaunchResearchButtonProps {
  conversationId: number | null;
  disabled?: boolean;
}

/**
 * Button component for launching research from an idea
 * Handles modal state and confirmation flow
 */
export function LaunchResearchButton({
  conversationId,
  disabled = false,
}: LaunchResearchButtonProps) {
  const {
    isLaunchModalOpen,
    setIsLaunchModalOpen,
    isLaunching,
    handleLaunchClick,
    handleConfirmLaunch,
    gpuTypes,
    selectedGpuType,
    isGpuTypeLoading,
    setSelectedGpuType,
  } = useLaunchResearch(conversationId);

  return (
    <>
      <Button
        onClick={handleLaunchClick}
        size="sm"
        disabled={disabled || isLaunching}
        aria-label="Launch research for this idea"
      >
        Launch Research
      </Button>
      <CreateProjectModal
        isOpen={isLaunchModalOpen}
        onClose={() => setIsLaunchModalOpen(false)}
        onConfirm={handleConfirmLaunch}
        isLoading={isLaunching}
        availableGpuTypes={gpuTypes}
        selectedGpuType={selectedGpuType}
        onSelectGpuType={setSelectedGpuType}
        isGpuTypeLoading={isGpuTypeLoading}
      />
    </>
  );
}
