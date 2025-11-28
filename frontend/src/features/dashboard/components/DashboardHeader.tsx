"use client";

import { SearchBox } from "@/features/search";

type DashboardSearchBoxProps = {
  query: string;
  isLoading: boolean;
  placeholder: string;
  onQueryChange: (query: string) => void;
  onSearch: (query: string) => void;
  onClear: () => void;
  disabled: boolean;
};

export function DashboardHeader({ searchBoxProps }: { searchBoxProps?: DashboardSearchBoxProps }) {
  return (
    <div className="toolbar-glass px-6 py-3 sticky top-0 z-10">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3 self-end md:self-auto w-full md:w-auto">
          {searchBoxProps && (
            <div className="flex-1 md:w-[32rem]">
              <SearchBox {...searchBoxProps} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
