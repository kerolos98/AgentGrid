import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack
from typing import Optional


class MCPClient:
    def __init__(self, mode: Optional[str] = None, orch_kit: Optional[object] = None, path: Optional[str] = None):
        self.mode = mode

        # In-process
        self.orch = orch_kit
        self.tools = {}
        self.resources = {}
        self.prompts = {}

        # Stdio (optional future)
        self.session = None
        self.exit_stack = AsyncExitStack()

    def connect(self):
        if self.mode == "local":
            self.connect_local()
        elif self.mode == "stdio":
            if not hasattr(self, 'transport'):
                raise RuntimeError("Stdio transport not initialized. Call connect_to_server() first.")
            # Stdio connection is established in connect_to_server()
            pass
        else:
            raise ValueError("Invalid mode. Choose 'local' or 'stdio'.")

    # =========================
    # 🔹 In-Process Connection
    # =========================
    def connect_local(self):
        """
        Connect to an in-memory MCP server (your current design)
        """

        # Build lookup tables
        self.tools = {t.name: t for t in self.orch.tools_list}
        self.resources = {r.name: r for r in self.orch.resources_list}
        self.prompts = {p.name: p for p in self.orch.prompts_list}

        print("\nConnected (LOCAL) with tools:", list(self.tools.keys()))

    def connect_to_server(self, server_script_path: str):
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
    
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
    
        command = sys.executable if is_python else "node"
    
        server_params = StdioServerParameters(
            command=command, args=[server_script_path], env=None
        )
    
        # FIX: We enter the transport first
        # This keeps the stdio_client alive across the session
        self.transport = stdio_client(server_params)
        self.stdio, self.write =  self.exit_stack.enter_async_context(self.transport)
    
        # FIX: Initialize the session within the same stack
        self.session = ClientSession(self.stdio, self.write)
        self.exit_stack.enter_async_context(self.session)
    
        self.session.initialize()

        response =  self.session.list_tools()
        print("\nConnected to server with tools:", [tool.name for tool in response.tools])

    # =========================
    # 🔹 Tool Calls
    # =========================
    def call_tool(self, name: str, arguments: dict):
        if self.mode == "local":
            if name not in self.tools:
                raise ValueError(f"Tool {name} not found")
            return self.tools[name].execute(**arguments)

        elif self.mode == "stdio":
            return  self.session.call_tool(name, arguments)

        else:
            raise RuntimeError("Client not connected")

    def excute_tools(self, tool_calls):
        results = []
        for call in tool_calls:
            func_info = call.model_extra.get('function', {})
            name = func_info.get('name')
            args = func_info.get('arguments', {})

            if name:
                result =  self.call_tool(name, args)
                results.append(result)
        return results

    # =========================
    # 🔹 Resource Access
    # =========================
    def get_resource(self, name: str, arguments: dict = {}):
        if self.mode == "local":
            if name not in self.resources:
                raise ValueError(f"Resource {name} not found")
            return self.resources[name].load(**arguments)

        elif self.mode == "stdio":
            return  self.session.get_resource(name, arguments)

        else:
            raise RuntimeError("Client not connected")

    # =========================
    # 🔹 Prompt Building
    # =========================
    async def build_prompt(self, name: str, arguments: dict = {}):
        if self.mode == "local":
            if name not in self.prompts:
                raise ValueError(f"Prompt {name} not found")
            return self.prompts[name].build(**arguments)

        elif self.mode == "stdio":
            return  self.session.get_prompt(name, arguments)

        else:
            raise RuntimeError("Client not connected")

    # =========================
    # 🔹 Optional: Tool Listing
    # =========================
    async def list_tools(self):
        if self.mode == "local":
            return list(self.tools.keys())

        elif self.mode == "stdio":
            response = await self.session.list_tools()
            return [tool.name for tool in response.tools]

        else:
            raise RuntimeError("Client not connected")

    # =========================
    # 🔹 Close
    # =========================
    async def close(self):
        await self.exit_stack.aclose()