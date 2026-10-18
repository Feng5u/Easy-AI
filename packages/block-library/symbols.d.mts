import * as Blockly from "blockly/core";
export type SymbolKind = "transform" | "dataset" | "dataloader" | "model_class";
export interface SymbolRecord {
  id: string;
  kind: SymbolKind;
  name: string;
  registered: boolean;
  role: "train" | "test" | null;
  workspace: "data" | "model";
}
export interface ReferenceStatus {
  valid: boolean;
  label: string;
  message: string | null;
}
export const referenceKinds: Record<
  string,
  [SymbolKind, "train" | "test" | null]
>;
export function symbolSnapshot(
  workspaces: Partial<Record<"data" | "model" | "training", Blockly.Workspace>>,
): SymbolRecord[];
export function bindSymbolProvider(
  workspace: Blockly.Workspace,
  provider: () => SymbolRecord[],
): () => void;
export function referenceStatus(
  value: string,
  kind: SymbolKind,
  role: "train" | "test" | null,
  symbols: SymbolRecord[],
): ReferenceStatus;
export class FieldSymbolRef extends Blockly.FieldDropdown {
  constructor(kind: SymbolKind, role?: "train" | "test" | null);
  symbolKind: SymbolKind;
  symbolRole: "train" | "test" | null;
  symbols(): SymbolRecord[];
  status(): ReferenceStatus;
  referenceOptions(): [string, string][];
  refresh(): void;
}
export function refreshReferences(
  workspaces: Partial<Record<"data" | "model" | "training", Blockly.Workspace>>,
): void;
export function setRegistration(
  block: Blockly.Block,
  registered: boolean,
): void;
