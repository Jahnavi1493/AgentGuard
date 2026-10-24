from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class MockAgent:
    """A simple scripted agent that receives only guarded tools."""

    def __init__(self, tools: Dict[str, Any], scenarios_path: str = "agent/scenarios.json"):
        self.tools = tools
        self.scenarios_path = Path(scenarios_path)

    def load_scenarios(self) -> List[Dict[str, Any]]:
        with open(self.scenarios_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def run_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = scenario["tool"]
        if tool_name not in self.tools:
            return {
                "scenario_id": scenario["id"],
                "decision": "BLOCK",
                "reason": "The mock agent does not have access to that tool.",
                "tool": tool_name,
            }
        return self.tools[tool_name](**scenario["params"])

    def run_all(self) -> List[Dict[str, Any]]:
        results = []
        for scenario in self.load_scenarios():
            results.append(self.run_scenario(scenario))
        return results
