import os
import json
from typing import Any, Dict, List, Literal, Optional
import logging
import yaml

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from .prometheus_tools import mcp_list_tools, request_mcp
from fastapi.responses import StreamingResponse
from fastapi.responses import StreamingResponse
from .agent import LLMAgent



# Configure logging to stderr (visible in docker logs)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    provider: Literal["gpt", "gemini"]
    messages: List[Message]
    model: Optional[str] = None


app = FastAPI(title="NewChat API")

# Cache the MCP tool registry for the life of the server process so the model
# keeps schemas in context across turns until a refresh/new session.
_TOOL_REGISTRY_CONTEXT: Optional[str] = None


def _build_llm(provider: str, model: Optional[str]) -> Any:
    if provider == "gpt":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
        model_name = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return ChatOpenAI(api_key=api_key, model=model_name, temperature=0)
    # provider == gemini
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not set")
    # Enforce flash-only model (never pro)
    model_name = model or "gemini-2.5-flash"
    return ChatGoogleGenerativeAI(google_api_key=api_key, model=model_name, temperature=0)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}

@app.post("/api/chat_stream")
async def chat_stream(req: ChatRequest):
    
    logger.info(f"chat_stream called with provider={req.provider}, messages={len(req.messages)}")
    try:
        # BEGIN stream additions (non-invasive)
        def _line(obj: Any) -> str:
            try:
                return json.dumps(obj, ensure_ascii=False) + "\n"
            except Exception as exc:
                return json.dumps({"type": "error", "error": f"serialize: {exc}"}) + "\n"
        # END stream additions
         # Build LLM (provider-specific instantiation only; tool logic is generic)
        llm = _build_llm(req.provider, req.model)
        logger.info("LLM built successfully")
        # stream: model ready
        yieldable = []
        yieldable.append(_line({"type": "stage", "stage": "model_ready"}))

        # Prepare LangChain tools (expose only one generic wrapper tool)
        tool_list = [request_mcp]
        llm_with_tools = llm.bind_tools(tool_list)

        # Prepare conversation
        system_prompt = (
            "You are an devops expert proficient in all monitoring, logging and deployment tools.  "
            "You are given access to a live prometheus-mcp server that can be used to query the prometheus database. "
            "This prometheus is configured to scrape the metrics of all containers within the environment. "
            "For any queries, relating to the user's environment, you should use the prometheus-mcp server to query the prometheus database. "
            "Do not give a generic response, instead rely on tools provided to you to answer the question. "
            "You only have one parent tool, which will be used to call any tool from the list provided below. "
            "All tools require specific arguments, which can be provided in a specific format(show below in example). "
            "For any task, gather some necessary information before directly trying to perform the task. This will allow you execute the task more efficiently. "
            "For Prometheus results, do not consider system-level groups or their metrics, unless problem solving specefically requires investigation of them. "
            "Instead of trying to get the answer in one shot, try to devide the task into discovery phase and execution phase. "
            # "In the discovery phase, you should try to gather as much information as possible about the problem. "
            # "In the execution phase, you should try to execute the task and get the answer. "
            # "If you don't get a satisfactory result, try again with a different approach."
        )
        messages_lc = {"messages": []} # Start empty - no system message here
        # Attach (and cache) the tool registry once per server lifetime
        global _TOOL_REGISTRY_CONTEXT
        if _TOOL_REGISTRY_CONTEXT is None:
            try:
                registry = await mcp_list_tools()
                _TOOL_REGISTRY_CONTEXT = yaml.dump(registry)
            except Exception:
                _TOOL_REGISTRY_CONTEXT = "[]"
        # Merge registry into the system prompt (will be passed via template at runtime)
        #print(_TOOL_REGISTRY_CONTEXT)
        example = f"""
                Now, consider the following section of the registry:-

                - description: Execute a PromQL instant query against Prometheus
                    inputSchema:
                        properties:
                        query:
                            title: Query
                            type: string
                        time:
                            anyOf:
                            - type: string
                            - type: 'null'
                            default: null
                            title: Time
                        required:
                        - query
                        type: object
                    name: execute_query
                    outputSchema:
                        additionalProperties: true
                        type: object
                  
                  The name of the tool can be gathered from the name field.
                  All the possible parameters are listed in proerties section with expected data type. Notice that the time parameter is optional.
                  To call a tool execute_query(refer name field for tool name) from the provided list,
                  you would provide the following arguments to the parent tool
                  ------------------------------------------------------------
                  tool: execute_query
                  parameters:
                        query: container_cpu_usage_seconds_total
                        <some-other-parameter>: <some-of-some-the-parameter>
                  ------------------------------------------------------------
                  Here the parameters is a multiline string with each parameter name and value pair on a new line.
                  each name value pair is separated by a colon on each line, following a typical yaml format.
                  The parent tool will then call the mcp tool on remote mcp server with the provided parameters.
                  The result of the tool call will be returned to you which you should parse for relevant content.
                  If no required parameters exist for that tool name in the registry and you decide no optional parameters are needed, you can pass an empty string for the parameters.
                  """

        # Prepare the system message with tool registry and example (will be injected via prompt template)
        system_with_context = system_prompt + f"\n\nTool registry: {_TOOL_REGISTRY_CONTEXT}" + f"\n\nExample: {example}"
        #print(system_with_context)
        # stream: registry loaded
        yieldable.append(_line({"type": "stage", "stage": "registry_loaded"}))


        messages_lc["messages"].append(SystemMessage(content=system_with_context))
        messages_lc["messages"].append(HumanMessage(content=req.messages[-1].content))
        # stream: history prepared
        yieldable.append(_line({"type": "stage", "stage": "history_prepared"}))

        # AgentExecutor-based tool loop (added without modifying prompts/tools)
        try:
            agent = LLMAgent(llm_with_tools,tool_list)

            # Compose inputs for the agent
            yieldable.append(_line({"type": "stage", "stage": "model_invoked"}))
            
            final_event = None
            async for event in agent.app.astream_events(messages_lc, version="v2"):
                event_type = event["event"]
                event_name = event["name"]

                if event_type == "on_tool_start":
                    print(f"Tool '{event_name}' started")
                    yieldable.append(_line({"type": "stage", "stage": "tool_call_start"}))
                elif event_type == "on_tool_end":
                    print(f"Tool '{event_name}' finished")
                    yieldable.append(_line({"type": "stage", "stage": "tool_call_ended"}))

                # Example: Check for node start/end
                if event_type == "on_chain_start":
                    # Nodes in LangGraph often appear as 'chains' in events
                    print(f"Node '{event_name}' started.")
                    yieldable.append(_line({"type": "stage", "stage": f"node_start_{event_name}"}))
                elif event_type == "on_chain_end":
                    print(f"Node '{event_name}' finished.")
                    yieldable.append(_line({"type": "stage", "stage": f"node_end_{event_name}"}))
                
                final_event = event['data']

            #print(type(final_event['output']['messages']))
            final_answer = final_event['output']['messages'][-1].content[-1]['text']
            yieldable.append(_line({"type": "final", "message": str(final_answer), "model": getattr(llm_with_tools, "model_name", None) or getattr(llm_with_tools, "model", None)}))
            return StreamingResponse((x for x in yieldable), media_type="application/x-ndjson")
        except Exception as exc:
            logger.exception(f"Error in chat_stream: {exc}")
            yieldable.append(_line({"type": "error", "error": str(exc)}))
            return StreamingResponse((x for x in yieldable), media_type="application/x-ndjson")
    except Exception as exc:
        logger.exception(f"Outer exception in chat_stream: {exc}")
        return StreamingResponse((x for x in [_line({"type": "error", "error": str(exc)})]), media_type="application/x-ndjson")
