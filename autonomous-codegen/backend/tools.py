"""
Tool definitions for the autonomous agent
"""
import json
from typing import Any

TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for information. Use this to find documentation, examples, or current information.",
        "parameters": {
            "query": "string - the search query",
            "num_results": "int - number of results (default: 5)"
        }
    },
    {
        "name": "web_fetch",
        "description": "Fetch and read content from a URL. Good for reading documentation or web pages.",
        "parameters": {
            "url": "string - the URL to fetch",
            "extract_text": "bool - extract clean text only (default: true)"
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file in the sandbox workspace.",
        "parameters": {
            "filename": "string - the filename (e.g., 'main.py', 'utils/helper.js')",
            "content": "string - the file content"
        }
    },
    {
        "name": "read_file",
        "description": "Read a file from the sandbox workspace.",
        "parameters": {
            "filename": "string - the filename to read"
        }
    },
    {
        "name": "list_files",
        "description": "List all files in the sandbox workspace.",
        "parameters": {}
    },
    {
        "name": "execute_code",
        "description": "Execute code in the sandbox. Supports Python, JavaScript (Node.js), and Bash.",
        "parameters": {
            "code": "string - the code to execute",
            "language": "string - 'python', 'javascript', or 'bash'",
            "timeout": "int - execution timeout in seconds (default: 30)"
        }
    },
    {
        "name": "execute_file",
        "description": "Execute a file that exists in the sandbox workspace.",
        "parameters": {
            "filename": "string - the file to execute",
            "args": "string - optional command line arguments"
        }
    },
    {
        "name": "install_package",
        "description": "Install a Python package in the sandbox using pip.",
        "parameters": {
            "package": "string - package name (e.g., 'requests', 'numpy==1.24.0')"
        }
    },
    {
        "name": "think",
        "description": "Use this to reason about the problem, plan next steps, or analyze results before taking action.",
        "parameters": {
            "thought": "string - your reasoning or analysis"
        }
    },
    {
        "name": "task_complete",
        "description": "Signal that the task is complete with a final summary.",
        "parameters": {
            "summary": "string - summary of what was accomplished",
            "files_created": "list - list of files created",
            "output": "string - any important output or results"
        }
    }
]


def get_tools_prompt() -> str:
    """Generate the tools description for the system prompt"""
    tools_text = ""
    for tool in TOOLS:
        tools_text += f"\n**{tool['name']}**\n"
        tools_text += f"Description: {tool['description']}\n"
        tools_text += "Parameters:\n"
        for param, desc in tool['parameters'].items():
            tools_text += f"  - {param}: {desc}\n"
    return tools_text


def parse_tool_call(text: str) -> dict | None:
    """
    Parse a tool call from LLM output.
    Expects format:
    <tool>
    {
        "name": "tool_name",
        "parameters": {...}
    }
    </tool>
    """
    import re

    # Try XML-style tags first
    pattern = r'<tool>(.*?)</tool>'
    match = re.search(pattern, text, re.DOTALL)

    if match:
        try:
            tool_json = match.group(1).strip()
            return json.loads(tool_json)
        except json.JSONDecodeError:
            pass

    # Try ```json blocks
    pattern2 = r'```(?:json)?\s*(\{[^`]*"name"[^`]*\})\s*```'
    match2 = re.search(pattern2, text, re.DOTALL)
    if match2:
        try:
            return json.loads(match2.group(1))
        except json.JSONDecodeError:
            pass

    # Try raw JSON with "name" key
    pattern3 = r'\{[^{}]*"name"\s*:\s*"[^"]*"[^{}]*\}'
    matches = re.findall(pattern3, text, re.DOTALL)
    for m in matches:
        try:
            parsed = json.loads(m)
            if "name" in parsed:
                return parsed
        except json.JSONDecodeError:
            continue

    return None
