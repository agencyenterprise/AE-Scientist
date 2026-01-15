import { defineResource } from "braided";
import { createSystemHooks, createSystemManager } from "braided-react";
import { useEffect } from "react";
import { narratorStoreResource } from "./resources/narratorStore";
import { sseStreamResource } from "./resources/sseStream";

/**
 * Resource that handles cleanup when navigating away from the narrative page.
 * Listens for beforeunload or page unmount and ensures proper system shutdown.
 */
const cleanupResource = defineResource({
  start: () => {
    const api = {
      cleanupRequested: false,
      cleanupTimeoutId: null as ReturnType<typeof setTimeout> | null,
      cleanupSystem: async () => {
        await narrativeSystemManager.destroySystem();
        api.cleanupRequested = false;
        api.cleanupTimeoutId = null;
      },
      scheduleCleanup: () => {
        api.cleanupRequested = true;
        api.cleanupTimeoutId = setTimeout(() => {
          if (api.cleanupRequested) {
            api.cleanupSystem();
          }
        }, 100);
      },
      cancelCleanup: () => {
        api.cleanupRequested = false;
        if (api.cleanupTimeoutId) {
          clearTimeout(api.cleanupTimeoutId);
          api.cleanupTimeoutId = null;
        }
      },
    };

    const useCleanup = () => {
      useEffect(() => {
        api.cancelCleanup();
        return () => {
          api.scheduleCleanup();
        };
      }, []);
    };

    return {
      useCleanup,
    };
  },
  halt: () => {
    // no-op
  },
});

export const systemConfig = {
  narratorStore: narratorStoreResource,
  sseStream: sseStreamResource,
  cleanup: cleanupResource,
};

export const narrativeSystemManager = createSystemManager(systemConfig);
export const { useResource, useSystemStatus } = createSystemHooks(narrativeSystemManager);
