import inspect
import json
from dataclasses import dataclass, field
from typing import List, Any, Optional, Dict

from .utils.utils import parse_doc
from .client import MCPClient
from .components import MCPTool, MCPResource, MCPPrompt

from mcp.server.fastmcp import FastMCP
from litellm import completion
from pydantic import BaseModel, Field


# ==========================
# STATE + LOGGING LAYER
# ==========================


@dataclass
class ExecutionEvent:
    step: str
    data: Any


@dataclass
class AgentState:
    messages: List[Dict[str, Any]] = field(default_factory=list)
    events: List[ExecutionEvent] = field(default_factory=list)

    def log(self, step: str, data: Any):
        self.events.append(ExecutionEvent(step=step, data=data))


# ==========================
# CORE CONFIG OBJECTS
# ==========================


class orch_kit(BaseModel):
    tools_list: List[Any] = Field(default_factory=list)
    resources_list: List[Any] = Field(default_factory=list)
    prompts_list: List[Any] = Field(default_factory=list)


class ServerMeta(BaseModel):
    description: str
    tools: List[Any] = Field(default_factory=list)
    resources: List[Any] = Field(default_factory=list)
    prompts: List[Any] = Field(default_factory=list)
    server: Any


class AgentConfig(BaseModel):
    name: str
    model: str
    server_meta: ServerMeta
    client: Optional[Any] = None

    def create_client(self):
        if self.client is None:
            self.client = MCPClient(
                mode="local",
                orch_kit=orch_kit(
                    tools_list=self.server_meta.tools,
                    resources_list=self.server_meta.resources,
                    prompts_list=self.server_meta.prompts,
                ),
            )


# ==========================
# ORCHESTRATOR / RUNTIME
# ==========================


class Orchestrator:
    def __init__(self, config: Dict):
        self.config = config
        self.tools_modules = config.get("tools_modules", [])
        self.resources_modules = config.get("resources_modules", [])
        self.prompts_modules = config.get("prompts_modules", [])

        self.agents: Dict[str, AgentConfig] = {}
        self.tools_list: List[Any] = []
        self.resources_list: List[Any] = []
        self.prompts_list: List[Any] = []

        self.server = None
        self.state = AgentState()

    # --------------------------
    # COMPONENT SYSTEM
    # --------------------------

    def create_component(self, func, meta):
        type_ = meta.get("type", "tool")
        if type_ == "tool":
            return MCPTool(func, meta)
        if type_ == "resource":
            return MCPResource(func, meta)
        if type_ == "prompt":
            return MCPPrompt(func, meta)
        return None

    def load_modules(self):
        modules = {
            "tool": self.tools_modules,
            "resource": self.resources_modules,
            "prompt": self.prompts_modules,
        }

        for type, module in modules.items():
            for mod in module:
                for _, obj in inspect.getmembers(mod):
                    if inspect.isfunction(obj):
                        doc = inspect.getdoc(obj)
                        meta = parse_doc(doc)
                        if not meta:
                            continue
                        meta["type"] = type
                        component = self.create_component(obj, meta)
                        if component:
                            self._add_component(component)

    def _add_component(self, component):
        t = component.meta.get("type", "tool")
        if t == "tool":
            self.tools_list.append(component)
        elif t == "resource":
            self.resources_list.append(component)
        elif t == "prompt":
            self.prompts_list.append(component)

    # --------------------------
    # MCP SERVER
    # --------------------------

    def register_to_mcp(self):
        if self.server:
            return self.server

        server = FastMCP()
        for comp in self.tools_list + self.resources_list + self.prompts_list:
            comp.register(server)

        self.server = server
        return server

    # --------------------------
    # AGENT REGISTRATION
    # --------------------------

    def add_agent(self, name: str, model: str):
        server = self.register_to_mcp()

        agent = AgentConfig(
            name=name,
            model=model,
            server_meta=ServerMeta(
                description=f"Agent {name} runtime",
                tools=self.tools_list,
                resources=self.resources_list,
                prompts=self.prompts_list,
                server=server,
            ),
        )

        agent.create_client()
        self.agents[name] = agent

    # --------------------------
    # TOOL SYSTEM
    # --------------------------

    def _tool_schema(self, tool):
        if hasattr(tool, "get_json_schema"):
            return tool.get_json_schema()
        if hasattr(tool, "schema"):
            return tool.schema
        raise ValueError("Invalid tool schema")

    def execute_tool(self, agent: AgentConfig, tool_name: str, **kwargs: Any):
        for t in agent.server_meta.tools:
            if getattr(t, "name", None) == tool_name:
                return t.func(**kwargs)
        raise ValueError(f"Tool not found: {tool_name}")

    # --------------------------
    # EXECUTION ENGINE (CORE)
    # --------------------------

    def run_agent(
        self,
        agent_name: str,
        prompt: str,
        api_base=None,
        api_key=None,
        api_version=None,
        max_steps: int = 8,
    ):
        optional_params = {
        "api_base": api_base,
        "api_key": api_key,
        "api_version": api_version
         }
        agent = self.agents.get(agent_name)
        if not agent:
            raise ValueError("Agent not found")

        agent.create_client()

        state = AgentState()
        state.messages.append({"role": "user", "content": prompt})

        tools = [self._tool_schema(t) for t in agent.server_meta.tools]
        active_params = {k: v for k, v in optional_params.items() if v is not None}
        response = completion(
            model=agent.model,
            messages=state.messages,
            tools=tools,
            tool_choice="auto" if tools else None,
            **active_params
        )

        step = 0

        # --------------------------
        # EXECUTION LOOP
        # --------------------------

        while step < max_steps:
            msg = response.choices[0].message
            tool_calls = getattr(msg, "tool_calls", None)

            if not tool_calls:
                state.log("final", msg)
                return response

            for call in tool_calls:
                tool_name = call.function.name
                args = json.loads(call.function.arguments)

                state.log("tool_call", {"tool": tool_name, "args": args})

                result = self.execute_tool(agent, tool_name, **args)

                state.log("tool_result", result)

                state.messages.append(msg)
                state.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": str(result),
                    }
                )

            response = completion(
                model=agent.model,
                messages=state.messages,
                tools=tools,
                tool_choice="auto",
            )

            step += 1

        state.log("stop", "max_steps_reached")
        return response
