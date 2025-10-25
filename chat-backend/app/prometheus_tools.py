import yaml
import os
from typing import Any, Dict

from fastmcp import Client
from langchain_core.tools import tool


class MCPHttpClient:
    def __init__(self, base_url: str) -> None:
        # Expect the full MCP base (e.g. http://prometheus-mcp:8080/mcp)
        self.client = Client(base_url.rstrip("/"))

    async def list_tools(self) -> Any:
        async with self.client:
            return await self.client.list_tools()

    async def call_tool(self, tool: str, args: Dict[str, Any]) -> Any:
        async with self.client:
            return await self.client.call_tool(tool, args)


def get_mcp_client() -> MCPHttpClient:
    base = os.getenv("PROMETHEUS_MCP_URL", "http://prometheus-mcp:8080/mcp")
    return MCPHttpClient(base)


async def mcp_list_tools() -> Any:
    tools = await get_mcp_client().list_tools()
    # Convert FastMCP Tool objects to JSON-serializable dicts
    json_tools = []
    for t in tools or []:
        try:
            name = getattr(t, "name", None)
            description = getattr(t, "description", None)
            input_schema = getattr(t, "inputSchema", None)
            output_schema = getattr(t, "outputSchema", None)
            json_tools.append({
                "name": name,
                "description": description,
                "inputSchema": input_schema,
                "outputSchema": output_schema,
            })
        except Exception:
            # Fallback to string representation if fields not accessible
            json_tools.append({"name": str(t)})
    return json_tools


async def send_request_to_mcp(tool: str, args: Dict[str, Any]) -> Any:
    result = await get_mcp_client().call_tool(tool, args)
    # Unwrap FastMCP CallToolResult to JSON-serializable content
    try:
        structured = getattr(result, "structured_content", None)
        data = getattr(result, "data", None)
        if structured is not None:
            return structured
        if data is not None:
            return data
        content = getattr(result, "content", None)
        if isinstance(content, list) and content:
            # Flatten text contents if present
            texts = []
            for part in content:
                text = getattr(part, "text", None)
                if text:
                    texts.append(text)
            if texts:
                return {"text": "\n".join(texts)}
        # As a last resort, return repr
        return {"result": repr(result)}
    except Exception as e:
        print(e)
        return {"result": repr(result)}

# LangChain tool wrappers (generic)
@tool("request_mcp")
async def request_mcp(tool: str, parameters: str = "") -> Any:  # type: ignore[override]
    """Call a tool from registry by providing tool name and parameters
      parameters is a multiline string with each parameter name and value pair on a new line.
      example:-
      parameter1: value1
      parameter2: value2
       """
    try:

        args_dict = yaml.safe_load(parameters)
    except Exception:
        return {"error": "Invalid parameter strings", "args": parameters}
    return await send_request_to_mcp(tool, args_dict)


