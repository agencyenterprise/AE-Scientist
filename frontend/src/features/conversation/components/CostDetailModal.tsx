"use client";

import { Button } from "@/shared/components/ui/button";
import type { ConversationCostResponse, ModelCost, ResearchCost } from "@/types";
import { DollarSign } from "lucide-react";
import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface CostDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  cost: ConversationCostResponse | null;
  isLoading: boolean;
}

export function CostDetailModal({ isOpen, onClose, cost, isLoading }: CostDetailModalProps) {
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  if (!isOpen || !isClient) return null;

  return createPortal(
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/50">
      <div className="bg-card rounded-lg shadow-xl max-w-2xl w-full">
        <div className="p-6">
          <div className="flex items-center mb-4">
            <DollarSign className="w-6 h-6 text-primary mr-3" />
            <h3 className="text-lg font-medium text-foreground">Conversation Cost Details</h3>
          </div>
          {isLoading ? (
            <div className="text-center p-8">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--primary)] mx-auto mb-4"></div>
              <p className="text-muted-foreground">Loading cost details...</p>
            </div>
          ) : cost ? (
            <div>
              <div>
                <div className="pt-6">
                  <h3 className="text-md font-semibold mb-2 border-b pb-2">Chat</h3>
                  {cost.cost_by_model.length > 0 ? (
                    <ul className="space-y-2">
                      {cost.cost_by_model.map((modelCost: ModelCost) => (
                        <li key={modelCost.model} className="flex justify-between items-center">
                          <span>{modelCost.model}</span>
                          <span className="font-mono text-sm">
                            {formatCurrency(modelCost.cost)}
                          </span>
                        </li>
                      ))}
                      <li className="flex justify-between items-center font-bold border-t pt-2 mt-2">
                        <span>Total</span>
                        <span className="font-mono text-sm">
                          {formatCurrency(
                            cost.cost_by_model.reduce((acc, modelCost) => acc + modelCost.cost, 0)
                          )}
                        </span>
                      </li>
                    </ul>
                  ) : (
                    <p className="text-sm text-gray-500">No chat costs available.</p>
                  )}
                </div>
                <div>
                  <h3 className="text-md font-semibold mb-2 border-b pt-10 pb-2">Research</h3>
                  {cost.cost_by_research.length > 0 ? (
                    <ul className="space-y-2">
                      {cost.cost_by_research.map((researchCost: ResearchCost) => (
                        <li key={researchCost.run_id} className="flex justify-between items-center">
                          <span className="truncate" title={researchCost.run_id}>
                            Run: {researchCost.run_id}
                          </span>
                          <span className="font-mono text-sm">
                            {formatCurrency(researchCost.cost)}
                          </span>
                        </li>
                      ))}
                      <li className="flex justify-between items-center font-bold border-t pt-2 mt-2">
                        <span>Total</span>
                        <span className="font-mono text-sm">
                          {formatCurrency(
                            cost.cost_by_research.reduce(
                              (acc, researchCost) => acc + researchCost.cost,
                              0
                            )
                          )}
                        </span>
                      </li>
                    </ul>
                  ) : (
                    <p className="text-sm text-gray-500">No research costs available.</p>
                  )}
                </div>
              </div>
              <div className="mt-6 bg-gray-100 dark:bg-gray-800 p-4 rounded-lg">
                <h2 className="text-lg font-semibold text-center">
                  Total Cost: {formatCurrency(cost.total_cost)}
                </h2>
              </div>
            </div>
          ) : (
            <div className="p-6 text-center">
              <p>Could not load cost details.</p>
            </div>
          )}
        </div>
        <div className="flex justify-end p-4 border-t">
          <Button onClick={onClose} variant="outline">
            Close
          </Button>
        </div>
      </div>
    </div>,
    document.body
  );
}
