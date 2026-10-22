import * as BlocklyModule from "blockly/core";
import manifest from "./manifest.json" with { type: "json" };
import { FieldSymbolRef, referenceKinds } from "./symbols.mjs";
// Blockly publishes browser ESM and Node CJS under this same subpath.
const Blockly =
  "FieldDropdown" in BlocklyModule
    ? BlocklyModule
    : Reflect.get(BlocklyModule, "default");

// Keep legacy values readable, but do not offer unsupported classroom tasks.
class ClassificationLossField extends Blockly.FieldDropdown {
  onItemSelected_(menu, item) {
    if (item.getValue() !== "CrossEntropy") return;
    super.onItemSelected_(menu, item);
  }
}
export function registerBlocks() {
  for (const spec of manifest.blocks) {
    if (Blockly.Blocks[spec.id]) continue;
    Blockly.Blocks[spec.id] = {
      init() {
        this.easyai = { version: 1, registered: false };
        const row = this.appendDummyInput();
        row.appendField(spec.label);
        for (const [key, field] of Object.entries(spec.fields)) {
          let input;
          if (field.type === "integer" || field.type === "number")
            input = new Blockly.FieldNumber(
              field.default,
              field.min,
              field.max,
              field.type === "integer" ? 1 : undefined,
            );
          else if (field.type === "boolean")
            input = new Blockly.FieldCheckbox(field.default ? "TRUE" : "FALSE");
          else if (field.type === "enum") {
            const options = field.options.map((x) => [
              key === "CRITERION" && x !== "CrossEntropy"
                ? `${x}（禁用：当前单标签十分类任务不适用）`
                : x,
              x,
            ]);
            input =
              key === "CRITERION"
                ? new ClassificationLossField(options)
                : new Blockly.FieldDropdown(options);
          } else if (field.type === "reference") {
            const [kind, role] = referenceKinds[key];
            input = new FieldSymbolRef(kind, role);
          } else
            input = new Blockly.FieldTextInput(
              String(field.default),
              (value) =>
                value.length <= (field.maxLength ?? 256) ? value : null,
            );
          row.appendField(key).appendField(input, key);
          this.setFieldValue(
            field.type === "boolean"
              ? field.default
                ? "TRUE"
                : "FALSE"
              : String(field.default),
            key,
          );
        }
        for (const [slot, accepts] of Object.entries(spec.inputs))
          this.appendStatementInput(slot).setCheck(accepts);
        if (!spec.placement.endsWith("_root")) {
          this.setPreviousStatement(true, spec.id);
          this.setNextStatement(
            true,
            manifest.blocks
              .filter((candidate) => candidate.placement === spec.placement)
              .map((candidate) => candidate.id),
          );
        }
        this.setColour(
          { data: 160, model: 220, train: 30, viz: 290 }[spec.category],
        );
        this.setTooltip(spec.label + " · " + spec.helpKey);
      },
      saveExtraState() {
        return { easyai: this.easyai };
      },
      loadExtraState(state) {
        this.easyai = structuredClone(state.easyai);
      },
    };
  }
}
