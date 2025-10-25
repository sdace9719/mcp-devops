import asyncio
import json
import os
import yaml
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing import Dict, Any, List
from fastmcp import Client


class AgentState(BaseModel):
    messages: Annotated[List[BaseMessage], add_messages]

class LLMAgent:

    async def call_model(self,state: AgentState):
        """The node that calls the LLM."""
        print("---CALLING MODEL---")
        # Get all messages from the state
        messages = state.messages
        # Call the LLM with the messages
        response = await self.model_with_tools.ainvoke(messages)
        # Return a dictionary with the new message to append to the state
        return {"messages": [response]}

    async def call_tool(self,state: AgentState):
        """The node that executes tools."""
        print("---CALLING TOOL---")
        # Get the last message, which should be an AI message with tool calls
        last_message = state.messages[-1]
        
        tool_outputs = []
        # Loop through all tool calls requested by the LLM
        for tool_call in last_message.tool_calls:
            tool_name = tool_call['name']
            print(f"Executing tool: {tool_name}")

            for t in self.tools_list:
                if t.name == tool_name:
                    selected_tool = t
                    break
            
            if selected_tool:
                # Call the tool with the arguments from the LLM
                output = await selected_tool.ainvoke(tool_call['args'])
                # Create a ToolMessage to send back to the LLM
                tool_outputs.append(
                    ToolMessage(content=str(output), tool_call_id=tool_call['id'])
                )
            
        # Return a dictionary with the tool outputs to append to the state
        return {"messages": tool_outputs}

    # --- 4. Define the Edges (Graph Logic) ---
    # This function decides which node to go to next.
    def should_continue(self,state: AgentState):
        """Conditional edge: decides to call tools or end."""
        last_message = state.messages[-1]
        # If the LLM made a tool call, we route to the `call_tool` node
        if last_message.tool_calls:
            return "continue"
        # Otherwise, the LLM gave a final answer, so we end
        return "end"

    def __init__(self, llm_with_tools,tools_list):
        self.tools_list = tools_list
        workflow = StateGraph(AgentState)

        # Add the two nodes we defined
        workflow.add_node("agent", self.call_model)
        workflow.add_node("action", self.call_tool)

        # Set the entry point of the graph
        workflow.set_entry_point("agent")

        # Add the conditional edge
        workflow.add_conditional_edges(
            "agent",          # Start from the 'agent' node
            self.should_continue,  # Call this function to decide the path
            {
                "continue": "action", # If it returns "continue", go to "action"
                "end": END            # If it returns "end", finish the graph
            }
        )

        # Add a normal edge: after the 'action' node runs, always go back to 'agent'
        workflow.add_edge("action", "agent")

        # --- 6. Compile and Run the Graph ---
        # Compile the graph into a runnable object
        self.app = workflow.compile()
        self.model_with_tools = llm_with_tools


