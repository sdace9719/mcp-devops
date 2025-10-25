import asyncio
from fastmcp import Client, FastMCP
import json


# HTTP server
client = Client("http://localhost:8081/mcp")

async def main():
    async with client:
        # Basic server interaction
        await client.ping()
        
        # List available operations
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()
        
        # Execute operations
        result = await client.call_tool("execute_query", {"query": "sort_desc(sum(container_memory_usage_bytes) by (container))"})
        result_dict = result.structured_content
        print(result_dict['result'])
        #print(json.dumps(result_dict, indent=4))
        #tools_as_dicts = [tool.model_dump() for tool in tools]
        #print(json.dumps(tools_as_dicts, indent=4))

asyncio.run(main())