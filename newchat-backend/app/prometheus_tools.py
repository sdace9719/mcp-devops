import os
from typing import Any, Dict, List

import httpx
from langchain.tools import tool


class MCPClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def _get(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, json: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=json)
            resp.raise_for_status()
            return resp.json()

    async def list_targets(self) -> Dict[str, Any]:
        return await self._get("/targets")

    async def list_metrics(self) -> Dict[str, Any]:
        return await self._get("/tools/get_targets")

    async def execute_query(self, query: str) -> Dict[str, Any]:
        return await self._post("/tools/execute_query", {"query": query})

    async def execute_range_query(self, query: str, start: str, end: str, step: str) -> Dict[str, Any]:
        payload = {"query": query, "start": start, "end": end, "step": step}
        return await self._post("/tools/execute_range_query", payload)


def _client() -> MCPClient:
    base = os.getenv("PROMETHEUS_MCP_URL", "http://prometheus-mcp:8080")
    return MCPClient(base)


@tool("prom_list_metrics", return_direct=False)
async def prom_list_metrics_tool() -> List[str]:
    """List available Prometheus metrics via the Prometheus MCP server."""
    res = await _client().list_metrics()
    # Expect MCP tool wrapper to return a JSON with keys or list; normalize to list of names
    if isinstance(res, dict) and "data" in res:
        data = res["data"]
        if isinstance(data, list):
            return [str(x) for x in data]
        return [str(k) for k in data.keys()]
    if isinstance(res, list):
        return [str(x) for x in res]
    return [str(res)]


@tool("prom_query", return_direct=False)
async def prom_query_tool(query: str) -> Dict[str, Any]:
    """Execute a PromQL instant query. Input: query string."""
    return await _client().execute_query(query)


@tool("prom_range_query", return_direct=False)
async def prom_range_query_tool(query: str, start: str, end: str, step: str = "30s") -> Dict[str, Any]:
    """Execute a PromQL range query. Inputs: query, start RFC3339, end RFC3339, step e.g. 30s."""
    return await _client().execute_range_query(query, start, end, step)


# Export an ordered list for simple access
TOOLS = [prom_list_metrics_tool, prom_query_tool, prom_range_query_tool]


