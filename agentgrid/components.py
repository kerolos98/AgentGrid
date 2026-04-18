import inspect


class BaseComponent:
    def __init__(self, func, meta):
        self.func = func
        self.meta = meta
        self.name = meta.get("name", func.__name__)
        self.uri = meta.get("uri", f"{meta.get('type','tool')}://{self.name}")
        self.description = meta.get("description", "")

    def register(self, server):
        raise NotImplementedError

    def get_json_schema(self):
        # 1. Get the function signature
        sig = inspect.signature(self.func)

        properties = {}
        required = []

        # 2. Map Python types to JSON types
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        for name, param in sig.parameters.items():
            # Skip 'self' if it's a method
            if name == "self":
                continue

            p_type = type_mapping.get(param.annotation, "string")
            properties[name] = {"type": p_type}

            # 3. Check if the parameter is required (no default value)
            if param.default is inspect.Parameter.empty:
                required.append(name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class MCPTool(BaseComponent):
    def execute(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def register(self, server):
        server.tool(name=self.name, description=self.description)(self.func)


class MCPResource(BaseComponent):
    def load(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def register(self, server):
        server.resource(uri=self.uri, name=self.name, description=self.description)(
            self.func
        )


class MCPPrompt(BaseComponent):
    def build(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def register(self, server):
        server.prompt(name=self.name, description=self.description)(self.func)
