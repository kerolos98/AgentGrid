import asyncio
import os
import sys
import threading

from contextlib import AsyncExitStack
from typing import Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

env = os.environ.copy()
env["PYTHONPATH"] = os.getcwd()

class BackgroundLoop:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(
            target=self._run_loop,
            daemon=True
        )
        self.thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()


class MCPClient:
    def __init__(self, mode: Optional[str] = None, orch_kit: Optional[object] = None, path: Optional[str] = None):
        self.mode = mode

        # In-process data configurations
        self.orch = orch_kit
        self.tools = {}
        self.resources = {}
        self.prompts = {}

        # 🌟 FIX 1: Add a components array required by agent_orch.pull_from_server()
        self.components = [] 

        # Stdio configurations
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.bg = BackgroundLoop()

    def connect(self):
        if self.mode == "local":
            self.connect_local()
        elif self.mode == "stdio":
            if not hasattr(self, 'transport'):
                raise RuntimeError("Stdio transport not initialized. Call connect_to_server() first.")
            pass
        else:
            raise ValueError("Invalid mode. Choose 'local' or 'stdio'.")

    def connect_local(self):
        """Connect to an in-memory MCP server"""
        self.tools = {t.name: t for t in self.orch.tools_list}
        self.resources = {r.name: r for r in self.orch.resources_list}
        self.prompts = {p.name: p for p in self.orch.prompts_list}
        self.components = self.orch.tools_list  # Mirror tools to components
        print("\nConnected (LOCAL) with tools:", list(self.tools.keys()))

    async def _async_connect(self, path):
        is_python = path.endswith(".py")
        is_js = path.endswith(".js")

        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = sys.executable if is_python else "node"

        server_params = StdioServerParameters(
            command=command,
            args=[path, "stdio"],
            env=env
        )

        self.transport = stdio_client(server_params)
        self.stdio, self.write = await self.exit_stack.enter_async_context(
            self.transport
        )

        self.session = ClientSession(self.stdio, self.write)
        await self.exit_stack.enter_async_context(self.session)
        await self.session.initialize()

        # 🌟 FIX 2: Correctly pull and cache tools during connection initialization
        response = await self.session.list_tools()
        
        # Populate components and tools maps dynamically so the framework can discover them
        self.components = response.tools
        self.tools = {t.name: t for t in response.tools}

        print(f"\nConnected (STDIO) with {len(self.components)} tools discovered.")
        return self 

    def connect_to_server(self, path):
        return self.bg.run(
            self._async_connect(path)
        )

    # =========================
    # 🔹 Tool Calls
    # =========================
    def call_tool(self, name: str, arguments: dict):
        if self.mode == "local":
            if name not in self.tools:
                raise ValueError(f"Tool {name} not found")
            return self.tools[name].execute(**arguments)

        elif self.mode == "stdio":
            # Safely executed on background loop thread
            return self.bg.run(self.session.call_tool(name, arguments))
        else:
            raise RuntimeError("Client not connected")

    # =========================
    # 🔹 Resource Access
    # =========================
    def get_resource(self, name: str, arguments: dict = {}):
        if self.mode == "local":
            if name not in self.resources:
                raise ValueError(f"Resource {name} not found")
            return self.resources[name].load(**arguments)

        elif self.mode == "stdio":
            # 🌟 FIX 3: Route through background thread runner to prevent blocking/runtime crash
            return self.bg.run(self.session.get_resource(name, arguments))
        else:
            raise RuntimeError("Client not connected")

    # =========================
    # 🔹 Prompt Building
    # =========================
    def build_prompt(self, name: str, arguments: dict = {}):
        # 🌟 REMOVED 'async' from the definition to keep consistency with sync interface design
        if self.mode == "local":
            if name not in self.prompts:
                raise ValueError(f"Prompt {name} not found")
            return self.prompts[name].build(**arguments)

        elif self.mode == "stdio":
            # 🌟 FIX 4: Route through background loop thread runner
            return self.bg.run(self.session.get_prompt(name, arguments))
        else:
            raise RuntimeError("Client not connected")

    # =========================
    # 🔹 Optional: Tool Listing
    # =========================
    def list_tools(self):
        # 🌟 REMOVED 'async' from definition so it safely defaults to sync orchestration patterns
        if self.mode == "local":
            return list(self.tools.keys())

        elif self.mode == "stdio":
            response = self.bg.run(self.session.list_tools())
            return [tool.name for tool in response.tools]
        else:
            raise RuntimeError("Client not connected")

    # =========================
    # 🔹 Close
    # =========================
    def close(self):
        # Clean up async stack resources inside the background thread
        return self.bg.run(self.exit_stack.aclose())
