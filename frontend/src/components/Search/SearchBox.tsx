"use client";

import React, { useCallback, useRef } from "react";

interface SearchBoxProps {
  query: string;
  isLoading: boolean;
  placeholder: string;
  onQueryChange: (query: string) => void;
  onSearch: (query: string) => void;
  onClear: () => void;
  disabled: boolean;
}

export function SearchBox({
  query,
  isLoading,
  placeholder,
  onQueryChange,
  onSearch,
  onClear,
  disabled,
}: SearchBoxProps): React.JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null);

  // Handle input changes (no debouncing here; hook handles it)
  const handleInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const newQuery = event.target.value;
      onQueryChange(newQuery);
    },
    [onQueryChange]
  );

  // Handle form submission
  const handleSubmit = useCallback(
    (event: React.FormEvent) => {
      event.preventDefault();
      if (query.trim() && !disabled) {
        onSearch(query.trim());
      }
    },
    [query, disabled, onSearch]
  );

  // Handle keyboard events
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (event.key === "Escape" && query) {
        onClear();
      }
    },
    [query, onClear]
  );

  // Handle clear button click
  const handleClear = useCallback(() => {
    onClear();
  }, [onClear]);

  return (
    <div className="relative w-full max-w-2xl mx-auto">
      <form onSubmit={handleSubmit} className="relative">
        <div className="relative flex items-center">
          {/* Search Icon */}
          <div className="absolute left-3 flex items-center pointer-events-none">
            <svg
              className={`h-5 w-5 ${
                disabled ? "text-muted-foreground/50" : "text-muted-foreground"
              } ${isLoading ? "animate-pulse" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>

          {/* Search Input */}
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            className={`
              w-full pl-10 pr-10 py-2 text-sm border rounded-lg
              focus:ring-2 focus:ring-primary focus:border-primary
              transition-colors duration-200
              ${
                disabled
                  ? "bg-muted border-border text-muted-foreground cursor-not-allowed"
                  : "bg-card border-border text-foreground hover:border-primary/50"
              }
              ${isLoading ? "bg-primary/10" : ""}
            `}
          />

          {/* Clear Button */}
          {query && !disabled && (
            <button
              type="button"
              onClick={handleClear}
              className="absolute right-3 p-1 text-muted-foreground hover:text-foreground transition-colors duration-200"
              title="Clear search"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          )}

          {/* Loading Indicator */}
          {isLoading && (
            <div className="absolute right-3 flex items-center">
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-primary border-t-transparent"></div>
            </div>
          )}
        </div>
      </form>
    </div>
  );
}
