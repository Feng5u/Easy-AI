import Blockly from "blockly/core";
import manifest from "./manifest.json" with { type: "json" };
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
          else if (field.type === "enum")
            input = new Blockly.FieldDropdown(field.options.map((x) => [x, x]));
          // References intentionally retain missing IDs; M4 replaces display with FieldSymbolRef.
          else input = new Blockly.FieldTextInput(String(field.default));
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
          this.setNextStatement(true);
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
