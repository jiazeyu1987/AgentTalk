from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import DagInvalid


@dataclass(frozen=True)
class Dag:
    raw: dict

    @property
    def plan_id(self) -> str:
        return str(self.raw["plan_id"])

    @property
    def nodes(self) -> list[dict]:
        return list(self.raw.get("nodes") or [])

    def node_by_task_id(self, task_id: str) -> dict | None:
        for n in self.nodes:
            if str(n.get("task_id")) == task_id:
                return n
        return None

    def assigned_agent_for_task(self, task_id: str) -> str:
        node = self.node_by_task_id(task_id)
        if not node:
            raise DagInvalid(code="DAG_TASK_NOT_FOUND", message=f"task_id not found in DAG: {task_id}")
        agent_id = node.get("assigned_agent_id")
        if not agent_id:
            raise DagInvalid(code="DAG_TASK_NO_ASSIGNEE", message=f"task_id has no assigned_agent_id: {task_id}")
        return str(agent_id)

    def deliver_to_for_output(self, task_id: str, output_name: str) -> list[str]:
        node = self.node_by_task_id(task_id)
        if not node:
            raise DagInvalid(code="DAG_TASK_NOT_FOUND", message=f"task_id not found in DAG: {task_id}")
        outputs = node.get("outputs") or []
        for o in outputs:
            if str(o.get("name")) == output_name:
                dt = o.get("deliver_to") or []
                return [str(x) for x in dt]
        raise DagInvalid(
            code="DAG_OUTPUT_NOT_FOUND",
            message=f"output not found in DAG: task_id={task_id} output_name={output_name}",
        )


def parse_dag(obj: dict) -> Dag:
    if str(obj.get("schema_version")) != "1.1":
        raise DagInvalid(code="DAG_SCHEMA_VERSION_UNSUPPORTED", message=str(obj.get("schema_version")))
    if "plan_id" not in obj or "nodes" not in obj:
        raise DagInvalid(code="DAG_INVALID", message="missing plan_id/nodes")
    return Dag(raw=obj)


def parse_active_dag_ref(obj: dict) -> tuple[str, str]:
    try:
        plan_id = str(obj["plan_id"])
        sha = str(obj["task_dag_sha256"])
        return plan_id, sha
    except Exception as e:
        raise DagInvalid(code="ACTIVE_DAG_REF_INVALID", message=str(e)) from e

