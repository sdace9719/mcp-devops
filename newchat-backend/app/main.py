import os
import json
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .prometheus_tools import TOOLS as PROM_TOOLS
from .prometheus_tools import TOOLS as PROM_TOOLS


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    provider: Literal["gpt", "gemini"]
    messages: List[Message]
    model: Optional[str] = None


app = FastAPI(title="NewChat API")


def _select_latest_gemini_model(genai) -> str:
    """Return the latest Gemini model that supports generateContent.

    Prefers names ending with "-latest"; strips any leading "models/" before returning.
    """
    try:
        models = list(genai.list_models())
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Gemini list_models failed: {exc}")

    def normalize(name: str) -> str:
        return name.split("/", 1)[-1] if name.startswith("models/") else name

    latest_candidates = []
    fallback_candidates = []
    for m in models:
        name = getattr(m, "name", "") or ""
        methods = getattr(m, "supported_generation_methods", []) or []
        if not name or "generateContent" not in methods:
            continue
        if name.startswith("models/gemini"):
            if name.endswith("-latest"):
                latest_candidates.append(name)
            else:
                fallback_candidates.append(name)

    candidates = latest_candidates or fallback_candidates
    if not candidates:
        raise HTTPException(status_code=500, detail="No Gemini model with generateContent available")

    # Pick lexicographically highest which typically correlates with newest version
    chosen = sorted(candidates, reverse=True)[0]
    return normalize(chosen)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    if req.provider == "gpt":
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail=f"OpenAI import failed: {exc}")

        client = OpenAI(api_key=openai_key)
        model = req.model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        # Define tool schemas for OpenAI function calling
        tools: List[Dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": "prom_list_metrics",
                    "description": "List available Prometheus metrics via the MCP server.",
                    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "prom_query",
                    "description": "Execute a PromQL instant query and return the raw result.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "prom_range_query",
                    "description": "Execute a PromQL range query with start, end (RFC3339), and step.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "start": {"type": "string"},
                            "end": {"type": "string"},
                            "step": {"type": "string", "default": "30s"},
                        },
                        "required": ["query", "start", "end"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

        # Build conversation with a brief system hint to use tools when helpful
        messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": "You are an assistant that can query Prometheus via tools. When users ask about metrics or PromQL, call the appropriate tool and then explain results.",
            }
        ] + [{"role": m.role, "content": m.content} for m in req.messages]

        try:
            while True:
                completion = client.chat.completions.create(model=model, messages=messages, tools=tools, tool_choice="auto")
                msg = completion.choices[0].message
                tool_calls = getattr(msg, "tool_calls", None)
                if tool_calls:
                    # Append assistant message that initiated tool calls
                    messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [tc.model_dump() for tc in tool_calls]})
                    # Execute each tool call
                    for tc in tool_calls:
                        name = tc.function.name
                        args = {}
                        try:
                            args = json.loads(tc.function.arguments or "{}")
                        except Exception:
                            args = {}
                        if name == "prom_list_metrics":
                            result = await PROM_TOOLS[0].ainvoke({})
                        elif name == "prom_query":
                            result = await PROM_TOOLS[1].ainvoke({"query": args.get("query", "")})
                        elif name == "prom_range_query":
                            result = await PROM_TOOLS[2].ainvoke({
                                "query": args.get("query", ""),
                                "start": args.get("start", ""),
                                "end": args.get("end", ""),
                                "step": args.get("step", "30s"),
                            })
                        else:
                            result = {"error": f"Unknown tool {name}"}
                        # Provide tool result back to the model
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": name,
                            "content": json.dumps(result),
                        })
                    # Loop for another model turn after tool results
                    continue
                # No tool calls => final answer
                text = msg.content
                return {"provider": "gpt", "model": model, "message": text}
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail=f"OpenAI error: {exc}")

    # Gemini
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not set")

    try:
        import google.generativeai as genai
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Gemini import failed: {exc}")

    genai.configure(api_key=gemini_key)
    # Always select the latest available model that supports generateContent
    model_name = _select_latest_gemini_model(genai)

    # Create a simple conversation summary as a single prompt for Gemini
    conversation_text = "\n".join(f"{m.role}: {m.content}" for m in req.messages)

    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(conversation_text)
        text = getattr(response, "text", None) or (response.candidates[0].content.parts[0].text if response.candidates else "")
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Gemini error: {exc}")

    return {"provider": "gemini", "model": model_name, "message": text}


"""Metrics-specific REST endpoints were intentionally removed.

The GPT provider now uses tool-calling to decide when to invoke the
Prometheus MCP tools during normal chat. This keeps the surface area
minimal and aligns with the user requirement that the LLM decide to
use tools. The LangChain-backed tools remain available internally.
"""


