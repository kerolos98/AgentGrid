# AgentGrid

![Python](https://img.shields.io/badge/python-3.9+-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Status](https://img.shields.io/badge/status-alpha-orange)
![LLM](https://img.shields.io/badge/LLM-local%20first-purple)

Lightweight agent orchestration framework with tool calling, local LLM support, and modular RAG integration.

---

## ✨ Features

* 🔧 **Tool-based architecture (minimal & powerful)**
* 🤖 **Multi-agent support**
* 🧠 **Local LLM compatible (LiteLLM / Ollama)**
* 🔍 **RAG as tools**
* 🧩 **Zero-boilerplate tool creation**

---

## ❓ Why AgentGrid?

Most frameworks are either:

### 🔹 High-level (LangChain, CrewAI)

* heavy abstractions
* hard to debug
* opinionated

### 🔹 Low-level

* flexible
* but no structure

---

## 🚀 AgentGrid Approach

* ⚖️ **Minimal core**
* 🔍 **Full transparency**
* 🧩 **Composable tools**
* 🧠 **Agent-driven execution**

---

## 🧠 Core Philosophy

> Tool creation should be as simple as possible.

### ✅ In AgentGrid:

**A tool is just:**

* a Python function
* with type annotations
* and a docstring

👉 That’s it.

No classes.
No decorators.
No registration boilerplate.

---

## 🔧 Creating a Tool

```python
def sum_data(data: list[int]):
    """
    type: tool
    name: sum_data
    description: Sum a list of numbers
    """
    return sum(data)
```

AgentGrid automatically:

* parses the docstring
* extracts metadata
* reads type annotations
* exposes the function as a tool

---

## ⚡ Quick Example

```python
from agentgrid import Orchestrator
import agentgrid.tools.github_tools as github_tools

config = {
    "tools_modules": [github_tools],
}

orch = Orchestrator(config)
orch.load_modules()

orch.add_agent("git_agent", model="ollama_chat/qwen3:4b")

response = orch.run_agent(
    "git_agent",
    "Create a new branch feature/api and commit changes"
)

print(response)
```

---

## 🔍 RAG Integration

RAG is just another tool:

```python
def search_docs(query: str):
    """
    type: tool
    name: search_docs
    description: Search documents and return relevant context
    """
    return "retrieved context"
```

---

## 🆚 Why not LangChain?

| Feature       | LangChain | AgentGrid   |
| ------------- | --------- | ----------- |
| Abstraction   | High      | Minimal     |
| Control       | Medium    | Full        |
| Debugging     | Hard      | Easy        |
| Tool creation | Complex   | Simple      |
| Overhead      | Heavy     | Lightweight |

---

## 🧩 Project Structure

```
agentgrid/
├── agentgrid/
│   ├── orchestrator.py
│   ├── components.py
│   ├── client.py
│   ├── utils/
│   └── tools/
├── examples/
├── README.md
└── pyproject.toml
```

---

## ⚠️ Notes

* Tool calling depends on model capability
* Always validate tool inputs (recommended)
* Git tools require a valid git repository

---

## 🚀 Roadmap

* [ ] Tool validation layer
* [ ] Retry / fallback system
* [ ] Memory support
* [ ] CLI interface
* [ ] Plugin ecosystem

---

## 📜 License

This project is licensed under the **Apache License 2.0**.

* You are free to use, modify, and distribute this software
* Includes explicit copyright and patent protection
* Requires proper attribution

For full terms, see the `LICENSE` file.

---

## 👤 Author

Kerolos Emad
