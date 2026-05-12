import os
import json
from sandbox_runner import run_code
from duckduckgo_search import DDGS

async def execute_tool(session_id: str, tool_name: str, args: dict) -> str:
    workspace_dir = os.path.join(os.getenv("WORKSPACE_BASE_PATH", "./workspaces"), session_id)
    os.makedirs(workspace_dir, exist_ok=True)

    try:
        if tool_name == "write_file":
            filepath = os.path.join(workspace_dir, args['filename'])
            with open(filepath, 'w') as f:
                f.write(args['content'])
            return f"Successfully wrote to {args['filename']}"

        elif tool_name == "read_file":
            filepath = os.path.join(workspace_dir, args['filename'])
            with open(filepath, 'r') as f:
                return f.read()

        elif tool_name == "list_files":
            files = []
            for root, _, filenames in os.walk(workspace_dir):
                for filename in filenames:
                    rel_dir = os.path.relpath(root, workspace_dir)
                    files.append(os.path.join(rel_dir if rel_dir != '.' else '', filename))
            return json.dumps(files)

        elif tool_name == "execute_code":
            cmd = args['command']
            res = await run_code(session_id, cmd)
            return f"Status: {res['status']}\nOutput:\n{res['output']}"

        elif tool_name == "web_search":
            with DDGS() as ddgs:
                results = [r for r in ddgs.text(args['query'], max_results=3)]
                return json.dumps(results)
        
        elif tool_name == "task_complete":
            return "Task marked as complete."

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        return f"Tool Execution Error: {str(e)}"