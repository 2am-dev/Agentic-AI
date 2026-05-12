"""
Autonomous Agent - The brain of the system
"""
import httpx
import json
import asyncio
import os
from typing import Callable, Awaitable, Optional
import logging

from tools import TOOLS, get_tools_prompt, parse_tool_call
from web_tools import web_search, web_fetch
from sandbox_runner import SandboxRunner

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "host.docker.internal:11434")


SYSTEM_PROMPT = """You are an Autonomous Code Generator Agent. You can write, execute, and test code to solve programming tasks.

You have access to these tools:

{tools}

## How to use tools:

To call a tool, output it in this exact format:
<tool>
{{"name": "tool_name", "parameters": {{"param1": "value1", "param2": "value2"}}}}
</tool>

## Agent Rules:

1. **ALWAYS start by thinking** - Use the `think` tool to plan your approach
2. **Search when needed** - Use `web_search` and `web_fetch` for documentation, APIs, or examples
3. **Write code carefully** - Use `write_file` to save code, then `execute_code` or `execute_file` to test it
4. **Fix errors** - If code fails, analyze the error, fix it, and try again
5. **Iterate** - Keep improving until the task is complete
6. **Be thorough** - Test your code, handle edge cases
7. **Finish properly** - Use `task_complete` when done with a full summary

## Important:
- Only ONE tool call per response
- Wait for tool results before proceeding  
- The sandbox is isolated - no internet in code execution (except web_search/web_fetch tools)
- You have {max_iterations} iterations maximum
- Write clean, well-commented, production-ready code
"""


class AutonomousAgent:
    def __init__(
        self,
        model: str = "deepseek-coder:6.7b",
        max_iterations: int = 15,
        callback: Optional[Callable] = None,
        session_id: str = "default"
    ):
        self.model = model
        self.max_iterations = max_iterations
        self.callback = callback
        self.session_id = session_id
        self.sandbox = SandboxRunner(session_id)
        self.messages = []
        self.iteration = 0
        self._stop = False
        self.files_created = []

    def stop(self):
        self._stop = True

    async def send(self, update: dict):
        """Send update to frontend"""
        if self.callback:
            await self.callback(update)

    async def run(self, task: str) -> dict:
        """Main agent loop"""
        await self.send({
            "type": "agent_start",
            "message": f"Starting task: {task}",
            "iteration": 0
        })

        # Initialize messages
        system = SYSTEM_PROMPT.format(
            tools=get_tools_prompt(),
            max_iterations=self.max_iterations
        )

        self.messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Task: {task}\n\nBegin working on this task. Think carefully and be thorough."}
        ]

        # Agent loop
        while self.iteration < self.max_iterations and not self._stop:
            self.iteration += 1

            await self.send({
                "type": "iteration_start",
                "iteration": self.iteration,
                "max_iterations": self.max_iterations
            })

            # Get LLM response
            await self.send({
                "type": "thinking",
                "message": "Consulting LLM..."
            })

            response = await self.call_llm()

            if not response:
                await self.send({
                    "type": "error",
                    "message": "LLM returned empty response"
                })
                break

            await self.send({
                "type": "llm_response",
                "content": response,
                "iteration": self.iteration
            })

            # Parse tool call
            tool_call = parse_tool_call(response)

            if not tool_call:
                # No tool call - add response and prompt for tool use
                self.messages.append({"role": "assistant", "content": response})
                self.messages.append({
                    "role": "user",
                    "content": "Please use a tool to continue. Remember to use the <tool> format."
                })

                await self.send({
                    "type": "warning",
                    "message": "No tool call detected, prompting agent..."
                })
                continue

            # Execute tool
            tool_name = tool_call.get("name", "")
            tool_params = tool_call.get("parameters", {})

            await self.send({
                "type": "tool_call",
                "tool": tool_name,
                "params": tool_params,
                "iteration": self.iteration
            })

            # Handle task_complete
            if tool_name == "task_complete":
                self.messages.append({"role": "assistant", "content": response})
                
                result = {
                    "summary": tool_params.get("summary", "Task completed"),
                    "files_created": tool_params.get("files_created", self.files_created),
                    "output": tool_params.get("output", ""),
                    "iterations": self.iteration,
                    "workspace": str(self.sandbox.workspace)
                }

                await self.send({
                    "type": "complete",
                    "result": result
                })

                return result

            # Execute the tool
            tool_result = await self.execute_tool(tool_name, tool_params)

            await self.send({
                "type": "tool_result",
                "tool": tool_name,
                "params":tool_params,
                "result": tool_result,
                "iteration": self.iteration
            })

            # Add to message history
            self.messages.append({"role": "assistant", "content": response})
            self.messages.append({
                "role": "user",
                "content": f"Tool `{tool_name}` result:\n```\n{json.dumps(tool_result, indent=2)}\n```\n\nContinue with the task."
            })

        # Max iterations reached
        if self.iteration >= self.max_iterations:
            await self.send({
                "type": "warning",
                "message": "Maximum iterations reached"
            })

        return {
            "summary": "Task completed (max iterations reached)",
            "files_created": self.files_created,
            "iterations": self.iteration
        }

    async def call_llm(self) -> str:
        """Call Ollama API"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                payload = {
                    "model": self.model,
                    "messages": self.messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9,
                        "num_predict": 2048,
                    }
                }

                resp = await client.post(
                    f"http://{OLLAMA_HOST}/api/chat",
                    json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "")

        except httpx.TimeoutException:
            logger.error("LLM request timed out")
            return ""
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return ""

    async def execute_tool(self, tool_name: str, params: dict) -> dict:
        """Execute a tool and return result"""
        try:
            if tool_name == "think":
                thought = params.get("thought", "")
                await self.send({
                    "type": "thought",
                    "content": thought
                })
                return {"success": True, "thought_recorded": True}

            elif tool_name == "web_search":
                query = params.get("query", "")
                num_results = int(params.get("num_results", 5))
                return await web_search(query, num_results)

            elif tool_name == "web_fetch":
                url = params.get("url", "")
                extract_text = params.get("extract_text", True)
                return await web_fetch(url, extract_text)

            elif tool_name == "write_file":
                filename = params.get("filename", "")
                content = params.get("content", "")
                result = self.sandbox.write_file(filename, content)
                if result.get("success"):
                    if filename not in self.files_created:
                        self.files_created.append(filename)
                return result

            elif tool_name == "read_file":
                filename = params.get("filename", "")
                return self.sandbox.read_file(filename)

            elif tool_name == "list_files":
                return self.sandbox.list_files()

            elif tool_name == "execute_code":
                code = params.get("code", "")
                language = params.get("language", "python")
                timeout = int(params.get("timeout", 30))
                return await self.sandbox.execute_code(code, language, timeout)

            elif tool_name == "execute_file":
                filename = params.get("filename", "")
                args = params.get("args", "")
                return await self.sandbox.execute_file(filename, args)

            elif tool_name == "install_package":
                package = params.get("package", "")
                return await self.sandbox.install_package(package)

            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            return {"success": False, "error": str(e)}
