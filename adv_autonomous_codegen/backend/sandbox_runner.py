import docker
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

client = docker.from_env()
executor = ThreadPoolExecutor(max_workers=10)

def _run_in_sandbox(session_id: str, command: str, image="coder-sandbox:latest", timeout=30):
    workspace_dir = os.path.abspath(os.path.join(os.getenv("WORKSPACE_BASE_PATH", "./workspaces"), session_id))
    os.makedirs(workspace_dir, exist_ok=True)

    try:
        container = client.containers.run(
            image,
            command=f"bash -c '{command}'",
            volumes={workspace_dir: {'bind': '/workspace', 'mode': 'rw'}},
            working_dir="/workspace",
            detach=True,
            mem_limit="512m",
            network_disabled=False, # Toggleable based on package install needs
        )
        container.wait(timeout=timeout)
        logs = container.logs().decode('utf-8')
        container.remove(force=True)
        return {"status": "success", "output": logs}
    except Exception as e:
        return {"status": "error", "output": str(e)}

async def run_code(session_id: str, command: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _run_in_sandbox, session_id, command)