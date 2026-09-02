"""Load a Blueprint from YAML with strict validation.

Follows HomeRail's WorkflowSpec lesson: unknown fields are hard errors, so
a typo can never silently change what a workflow does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codeagent.blueprint.graph import Blueprint, Edge, Node, NodeKind

_TOP_LEVEL_KEYS = {"name", "description", "nodes", "edges"}
_NODE_KEYS = {"id", "kind", "label", "prompt", "config"}
_EDGE_KEYS = {"source", "target", "label"}


class BlueprintSpecError(ValueError):
    """Raised when a blueprint YAML document fails strict validation."""


def _check_keys(mapping: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = set(mapping) - allowed
    if unknown:
        raise BlueprintSpecError(
            f"{where}: unknown field(s) {sorted(unknown)}; allowed: {sorted(allowed)}"
        )


def parse_blueprint(data: dict[str, Any]) -> Blueprint:
    """Build a :class:`Blueprint` from an already-parsed mapping."""
    if not isinstance(data, dict):
        raise BlueprintSpecError("blueprint document must be a mapping")
    _check_keys(data, _TOP_LEVEL_KEYS, "blueprint")

    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise BlueprintSpecError("blueprint needs a non-empty 'nodes' list")

    nodes: list[Node] = []
    for i, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict):
            raise BlueprintSpecError(f"nodes[{i}] must be a mapping")
        _check_keys(raw, _NODE_KEYS, f"nodes[{i}]")
        node_id = raw.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise BlueprintSpecError(f"nodes[{i}].id must be a non-empty string")
        raw_kind = raw.get("kind", "agent")
        try:
            kind = NodeKind(raw_kind)
        except ValueError:
            raise BlueprintSpecError(
                f"node {node_id!r}: unknown kind {raw_kind!r}; "
                f"allowed: {[k.value for k in NodeKind]}"
            ) from None
        config = raw.get("config") or {}
        if not isinstance(config, dict):
            raise BlueprintSpecError(f"node {node_id!r}: config must be a mapping")
        nodes.append(
            Node(
                id=node_id,
                kind=kind,
                label=str(raw.get("label", "")),
                prompt=str(raw.get("prompt", "")),
                config=config,
            )
        )

    edges: list[Edge] = []
    for i, raw in enumerate(data.get("edges") or []):
        if not isinstance(raw, dict):
            raise BlueprintSpecError(f"edges[{i}] must be a mapping")
        _check_keys(raw, _EDGE_KEYS, f"edges[{i}]")
        if "source" not in raw or "target" not in raw:
            raise BlueprintSpecError(f"edges[{i}] needs both 'source' and 'target'")
        edges.append(
            Edge(
                source=str(raw["source"]),
                target=str(raw["target"]),
                label=str(raw.get("label", "")),
            )
        )

    try:
        return Blueprint(nodes=nodes, edges=edges, name=str(data.get("name", "blueprint")))
    except (ValueError, TypeError) as exc:
        raise BlueprintSpecError(str(exc)) from exc


def load_blueprint_yaml(source: str | Path) -> Blueprint:
    """Load a blueprint from a YAML file path or YAML text."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise BlueprintSpecError(
            "PyYAML is required for blueprint YAML: pip install pyyaml"
        ) from exc
    if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source and Path(source).expanduser().exists()):
        text = Path(source).expanduser().read_text(encoding="utf-8")
    else:
        text = str(source)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise BlueprintSpecError(f"invalid YAML: {exc}") from exc
    return parse_blueprint(data)
