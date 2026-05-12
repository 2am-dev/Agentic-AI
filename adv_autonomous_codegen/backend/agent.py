import httpx
import json
import re
from tools import execute_tool
from db import append_log

OLLAMA_HOST = "http://host.docker.internal:11434/api/generate"

SYSTEM_PROMPT = """You are an Advanced Autonomous Coding Agent.
You operate in a ReAct loop. You MUST respond strictly in the following format:

THOUGHT: <your reasoning for the next step>
ACTION: <tool_name>
INPUT: <json object of arguments>

Available Tools:
1. write_file: {"filename": "str", "content": "str"}
2. read_file: {"filename": "str"}
3. list_files: {}
4. execute_code: {"command": "str"} - Runs bash commands (python x.py, npm install, etc.)
5. web_search: {"query": "str"}
6. task_complete: {"summary": "str"}

Rules:
- One tool call per turn.
- The environment is an isolated Linux container.
- Write full code, do not use placeholders.
"""

async def run_agent(session_id: str, task: str, model: str, max_iterations: int, send_ws_msg):
    context = f"{SYSTEM_PROMPT}\n\nUSER TASK: {task}\n"
    
    for i in range(max_iterations):
        await send_ws_msg({"type": "iteration_start", "iteration": i+1})
        
        payload = {
            "model": model,
            "prompt": context,
            "stream": True
        }
        
        full_response = ""
        await send_ws_msg({"type": "llm_start"})
        
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", OLLAMA_HOST, json=payload, timeout=120.0) as response:
                    async for chunk in response.aiter_lines():
                        if chunk:
                            data = json.loads(chunk)
                            token = data.get("response", "")
                            full_response += token
                            await send_ws_msg({"type": "token", "content": token})
                            
                            if data.get("done"):
                                break
        except Exception as e:
            await send_ws_msg({"type": "error", "content": str(e)})
            break

        await send_ws_msg({"type": "llm_end", "full_response": full_response})
        append_log(session_id, "llm_response", full_response)
        context += f"{full_response}\n"

        # Parse THOUGHT, ACTION, INPUT
        thought_match = re.search(r'THOUGHT:\s*(.*?)\nACTION:', full_response, re.DOTALL)
        action_match = re.search(r'ACTION:\s*([a-zA-Z_]+)', full_response)
        input_match = re.search(r'INPUT:\s*(\{.*?\})', full_response, re.DOTALL)

        if action_match and input_match:
            action = action_match.group(1)
            try:
                action_input = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                context += "SYSTEM: JSON parsing error in INPUT. Please format as valid JSON.\n"
                continue

            await send_ws_msg({"type": "tool_call", "tool": action, "input": action_input})
            append_log(session_id, "tool_call", {"tool": action, "input": action_input})
            
            if action == "task_complete":
                await send_ws_msg({"type": "complete", "summary": action_input.get("summary", "")})
                break
                
            tool_result = await execute_tool(session_id, action, action_input)
            
            # Truncate large outputs
            if len(tool_result) > 2000:
                tool_result = tool_result[:2000] + "\n...[TRUNCATED]"
                
            await send_ws_msg({"type": "tool_result", "tool": action, "result": tool_result})
            append_log(session_id, "tool_result", {"tool": action, "result": tool_result})
            
            context += f"OBSERVATION:\n{tool_result}\n"
        else:
            context += "SYSTEM: Invalid format. You must provide THOUGHT, ACTION, and INPUT.\n"
            
    await send_ws_msg({"type": "terminated", "reason": "Max iterations reached or task complete."})