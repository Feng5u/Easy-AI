import math
from typing import Any, Literal

from easyai.domain.catalog import definitions
from easyai.domain.contracts import BlockIR, Diagnostic, Origin, ProjectDocument

MAX_BLOCKS = 500
MAX_DEPTH = 64


class DecodeError(ValueError):
    pass


def decode(project: ProjectDocument) -> tuple[list[BlockIR], list[Diagnostic]]:
    catalog = definitions()
    seen: set[str] = set()
    diagnostics: list[Diagnostic] = []

    allowed = {
        "type",
        "id",
        "x",
        "y",
        "extraState",
        "fields",
        "inputs",
        "next",
        "disabledReasons",
        "collapsed",
        "inline",
        "data",
        "editable",
        "deletable",
        "movable",
    }
    scanned: set[str] = set()

    def prescan(value: Any, depth: int = 1) -> None:
        if not isinstance(value, dict) or set(value) - allowed:
            raise DecodeError("BLOCK_STRUCTURE_INVALID")
        block_id, type_id = value.get("id"), value.get("type")
        if (
            not isinstance(block_id, str)
            or not block_id
            or len(block_id) > 256
            or block_id in scanned
        ):
            raise DecodeError("BLOCK_ID_INVALID")
        if not isinstance(type_id, str) or type_id not in catalog:
            raise DecodeError("BLOCK_UNKNOWN")
        scanned.add(block_id)
        if len(scanned) > MAX_BLOCKS:
            raise DecodeError("BLOCK_COUNT_LIMIT")
        if depth > MAX_DEPTH:
            raise DecodeError("BLOCK_DEPTH_LIMIT")
        spec = catalog[type_id]
        state = value.get("extraState", {"easyai": {"version": 1, "registered": False}})
        if not isinstance(state, dict) or set(state) != {"easyai"}:
            raise DecodeError("BLOCK_STATE_INVALID")
        state = state["easyai"]
        if (
            not isinstance(state, dict)
            or set(state) != {"version", "registered"}
            or type(state["version"]) is not int
            or state["version"] != 1
            or type(state["registered"]) is not bool
        ):
            raise DecodeError("BLOCK_STATE_INVALID")
        fields = value.get("fields", {})
        if not isinstance(fields, dict) or set(fields) - set(spec["fields"]):
            raise DecodeError("FIELD_UNKNOWN")
        disabled = value.get("disabledReasons", [])
        if not isinstance(disabled, list) or not all(isinstance(x, str) for x in disabled):
            raise DecodeError("BLOCK_STRUCTURE_INVALID")
        connections = value.get("inputs", {})
        if not isinstance(connections, dict) or set(connections) - set(spec["inputs"]):
            raise DecodeError("INPUT_UNKNOWN")
        for connection in connections.values():
            if (
                not isinstance(connection, dict)
                or not connection
                or set(connection) - {"block", "shadow"}
            ):
                raise DecodeError("INPUT_STRUCTURE_INVALID")
            for child in connection.values():
                prescan(child, depth + 1)
        if "next" in value:
            connection = value["next"]
            if (
                spec["placement"].endswith("_root")
                or not isinstance(connection, dict)
                or set(connection) != {"block"}
            ):
                raise DecodeError("INPUT_STRUCTURE_INVALID")
            prescan(connection["block"], depth)

    for workspace_name in ("data", "model", "training"):
        for root in getattr(project.workspaces, workspace_name).blocks.blocks:
            prescan(root)

    def chain(
        value: dict[str, Any],
        workspace: Literal["data", "model", "training"],
        depth: int,
        parent: str | None = None,
        slot: str | None = None,
    ) -> list[BlockIR]:
        result: list[BlockIR] = []
        while value:
            if depth > MAX_DEPTH:
                raise DecodeError("BLOCK_DEPTH_LIMIT")
            block_id, type_id = value.get("id"), value.get("type")
            if not isinstance(block_id, str) or not isinstance(type_id, str) or block_id in seen:
                raise DecodeError("BLOCK_ID_INVALID")
            seen.add(block_id)
            if len(seen) > MAX_BLOCKS:
                raise DecodeError("BLOCK_COUNT_LIMIT")
            if type_id not in catalog:
                raise DecodeError("BLOCK_UNKNOWN")
            spec = catalog[type_id]
            origin = Origin(block_id=block_id, workspace=workspace)
            if value.get("disabledReasons"):
                value = value.get("next", {}).get("block", {})
                continue
            if parent and type_id not in catalog[parent]["inputs"].get(slot, []):
                diagnostics.append(
                    Diagnostic(
                        code="PLACEMENT_INVALID", message="积木不适合这个槽。", origin=origin
                    )
                )
            if (
                not parent
                and spec["placement"]
                != {"data": "data_root", "model": "model_root", "training": "training_root"}[
                    workspace
                ]
            ):
                diagnostics.append(
                    Diagnostic(
                        code="DRAFT_DISCONNECTED",
                        severity="info",
                        message="未连接的草稿未加入程序。",
                        origin=origin,
                    )
                )
                value = value.get("next", {}).get("block", {})
                continue
            raw_fields = value.get("fields", {})
            if not isinstance(raw_fields, dict) or set(raw_fields) - set(spec["fields"]):
                raise DecodeError("FIELD_UNKNOWN")
            fields: dict[str, Any] = {}
            for key, rule in spec["fields"].items():
                item = raw_fields.get(key, rule["default"])
                kind = rule["type"]
                valid = True
                if kind in ("integer", "number"):
                    valid = type(item) in ((int,) if kind == "integer" else (int, float))
                    valid = (
                        valid
                        and (type(item) is int or math.isfinite(item))
                        and rule["min"] <= item <= rule["max"]
                    )
                    valid = valid and not (rule.get("exclusiveMin") and item == rule["min"])
                    valid = valid and not (rule.get("exclusiveMax") and item == rule["max"])
                elif kind == "boolean":
                    valid = type(item) is bool or item in ("TRUE", "FALSE")
                    if valid:
                        item = item is True or item == "TRUE"
                elif kind == "enum":
                    valid = item in rule["options"]
                elif kind == "numbers":
                    try:
                        numbers = [float(x.strip()) for x in item.split(",")]
                        valid = bool(numbers) and all(math.isfinite(x) for x in numbers)
                        if key == "STD":
                            valid = valid and all(x > 0 for x in numbers)
                        item = numbers
                    except (AttributeError, ValueError):
                        valid = False
                else:
                    valid = isinstance(item, str) and len(item) <= rule.get("maxLength", 256)
                if not valid:
                    diagnostics.append(
                        Diagnostic(
                            code="FIELD_INVALID",
                            message="参数格式或范围不正确。",
                            origin=origin,
                            field=key,
                        )
                    )
                else:
                    fields[key] = item
            inputs: dict[str, list[BlockIR]] = {}
            raw_inputs = value.get("inputs", {})
            if not isinstance(raw_inputs, dict) or set(raw_inputs) - set(spec["inputs"]):
                raise DecodeError("INPUT_UNKNOWN")
            for key in spec["inputs"]:
                connection = raw_inputs.get(key, {})
                nested = connection.get("block", connection.get("shadow", {}))
                inputs[key] = chain(nested, workspace, depth + 1, type_id, key)
            state = value.get("extraState", {}).get("easyai", {"version": 1, "registered": False})
            if (
                set(state) != {"version", "registered"}
                or state["version"] != 1
                or type(state["registered"]) is not bool
            ):
                raise DecodeError("BLOCK_STATE_INVALID")
            if spec["placement"].endswith("_root"):
                fields["REGISTERED"] = state["registered"]
            result.append(BlockIR(type_id=type_id, origin=origin, fields=fields, inputs=inputs))
            value = value.get("next", {}).get("block", {})
        return result

    roots: list[BlockIR] = []
    for workspace in ("data", "model", "training"):
        for value in getattr(project.workspaces, workspace).blocks.blocks:
            roots.extend(chain(value, workspace, 1))
    return roots, diagnostics
