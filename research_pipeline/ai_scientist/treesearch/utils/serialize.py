import copy
import json
from pathlib import Path
from typing import TypeVar, cast, overload

import dataclasses_json

from ..journal import Journal, Node


def dumps_json(obj: dataclasses_json.DataClassJsonMixin | Journal) -> str:
    """Serialize dataclasses (such as Journals) to JSON."""
    if isinstance(obj, Journal):
        journal_copy = copy.deepcopy(obj)
        node2parent: dict[str, str] = {}
        for n in journal_copy.nodes:
            if n.parent is not None:
                # Handle both Node objects and string IDs
                parent_id = n.parent.id if isinstance(n.parent, Node) else cast(str, n.parent)
                node2parent[n.id] = parent_id
        for n in journal_copy.nodes:
            n.parent = None
            n.children = set()

        obj_dict_generic = cast(dict[str, object], journal_copy.to_dict())
        obj_dict_generic["node2parent"] = node2parent
        obj_dict_generic["__version"] = "2"
        return json.dumps(obj_dict_generic, separators=(",", ":"))

    obj_dict_generic = cast(dict[str, object], obj.to_dict())
    return json.dumps(obj_dict_generic, separators=(",", ":"))


def dump_json(obj: dataclasses_json.DataClassJsonMixin | Journal, path: Path) -> None:
    with open(path, "w") as f:
        f.write(dumps_json(obj=obj))


G = TypeVar("G", bound=dataclasses_json.DataClassJsonMixin)


@overload
def loads_json(s: str, cls: type[Journal]) -> Journal:
    pass


@overload
def loads_json(s: str, cls: type[G]) -> G:
    pass


def loads_json(s: str, cls: type[object]) -> object:
    """Deserialize JSON to dataclasses or Journal."""
    obj_dict = json.loads(s)

    if cls is Journal:
        # Manually reconstruct Journal from dict
        id_to_node: dict[str, Node] = {}
        for node_data in obj_dict.get("nodes", []):
            node = Node.from_dict(node_data)
            id_to_node[node.id] = node

        # Restore relationships
        for child_id, parent_id in obj_dict.get("node2parent", {}).items():
            child_node = id_to_node[child_id]
            parent_node = id_to_node[parent_id]
            child_node.parent = parent_node
            child_node.__post_init__()

        journal = Journal(
            summary_model=str(obj_dict["summary_model"]),
            node_selection_model=str(obj_dict["node_selection_model"]),
            summary_temperature=float(obj_dict.get("summary_temperature", 1.0)),
            node_selection_temperature=float(obj_dict.get("node_selection_temperature", 1.0)),
            event_callback=lambda _event: None,
        )
        journal.nodes.extend(id_to_node.values())
        return journal

    # Generic dataclass-json path
    obj = cls.from_dict(obj_dict)  # type: ignore[attr-defined]
    return obj


@overload
def load_json(path: Path, cls: type[Journal]) -> Journal:
    pass


@overload
def load_json(path: Path, cls: type[G]) -> G:
    pass


def load_json(path: Path, cls: type[object]) -> object:
    with open(path, "r") as f:
        return loads_json(s=f.read(), cls=cls)  # type: ignore[arg-type]
