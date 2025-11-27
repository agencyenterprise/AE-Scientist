import React from "react";

interface ProjectDraftEditFormProps {
  editDescription: string;
  setEditDescription: (description: string) => void;
  onKeyDown: (event: React.KeyboardEvent, action: () => void) => void;
  onSave: () => Promise<void>;
  onCancelEdit: () => void;
}

export function ProjectDraftEditForm({
  editDescription,
  setEditDescription,
  onKeyDown,
  onSave,
  onCancelEdit,
}: ProjectDraftEditFormProps) {
  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="flex items-center justify-between mb-2">
        <label className="text-sm font-medium text-muted-foreground">
          Edit Idea (JSON format required)
        </label>
      </div>
      <div className="flex-1 flex flex-col min-h-0">
        <textarea
          value={editDescription}
          onChange={e => setEditDescription(e.target.value)}
          onKeyDown={e => onKeyDown(e, onSave)}
          className="input-field flex-1 min-h-[45vh] sm:min-h-[20rem] resize-none overflow-auto font-mono"
          placeholder="Enter idea data as JSON..."
        />
        <div className="flex justify-end space-x-2 mt-2">
          <button onClick={onCancelEdit} className="btn-secondary text-xs py-1">
            Cancel
          </button>
          <button onClick={onSave} className="btn-primary-gradient text-xs py-1 px-3">
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
