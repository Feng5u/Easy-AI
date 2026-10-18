import type { ProjectDocument } from "../electron/bridge.js";

export type WorkspaceTab = "data" | "model" | "training";
export interface ProjectEditorProps {
  project: ProjectDocument;
  readOnly: boolean;
  selectedBlock: string | null;
  onChange(workspaces: ProjectDocument["workspaces"]): void;
  onSelect(blockId: string | null): void;
  activeTab: WorkspaceTab;
  onTabChange(tab: WorkspaceTab): void;
}
