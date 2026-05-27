import re
import copy


def clean_schema(schema):
    """
    Recursively clean MCP schema for LiteLLM/OpenAI compatibility.
    """

    if isinstance(schema, dict):
        cleaned = {}

        for key, value in schema.items():

            # Remove unsupported/problematic keys
            if key in {
                "additionalProperties",
                "$schema",
                "title",
                "examples",
                "default",
            }:
                continue

            cleaned[key] = clean_schema(value)

        return cleaned

    elif isinstance(schema, list):
        return [clean_schema(v) for v in schema]

    return schema


def map_mcp_to_litellm(mcp_tool):
    """
    Convert MCP tool schema to LiteLLM/OpenAI tool schema.
    """

    schema = copy.deepcopy(mcp_tool.inputSchema)
    schema = clean_schema(schema)

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def parse_doc(doc: str):
    meta = {}
    meta["description"]=doc.strip()
    return meta
