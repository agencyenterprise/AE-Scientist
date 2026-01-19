/**
 * Create a subscription object with a payload
 * @param payload - The payload to subscribe to
 * @returns A subscription object
 */
export function createSubscription<TPayload>() {
  const subscribers = new Set<(payload: TPayload) => void>();

  return {
    subscribe: (callback: (payload: TPayload) => void): (() => void) => {
      subscribers.add(callback);
      return () => subscribers.delete(callback);
    },
    notify: (payload: TPayload) => {
      subscribers.forEach(callback => callback(payload));
    },
    clear: () => {
      subscribers.clear();
    },
    size: () => {
      return subscribers.size;
    },
  };
}

export type Subscription<TPayload> = ReturnType<typeof createSubscription<TPayload>>;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type SubscriptionCallback<T extends Subscription<any>> = Parameters<T["subscribe"]>[0];
