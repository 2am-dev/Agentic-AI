from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio
import json
import uuid
from typing import Optional
from agent import AutonomousAgent
import logging
from pathlib import Path
import os

WORKSPACE_PATH = os.getenv("WORKSPACE_PATH", "/workspace")

app = FastAPI(title="Autonomous Code Generator")

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active sessions
sessions: dict[str, AutonomousAgent] = {}
websocket_connections: dict[str, WebSocket] = {}


class TaskRequest(BaseModel):
    task: str
    model: str = "deepseek-coder:6.7b"
    max_iterations: int = 15
    session_id: Optional[str] = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/models")
async def get_models():
    """Get available Ollama models"""
    import httpx
    import os
    ollama_host = os.getenv("OLLAMA_HOST", "host.docker.internal:11434")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://{ollama_host}/api/tags", timeout=10)
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}

@app.get("/files/{session_id}/{filename:path}")
async def serve_file(session_id: str, filename: str):
    """Serve a workspace file to the frontend"""
    from fastapi.responses import PlainTextResponse
    safe_path = Path(WORKSPACE_PATH) / session_id / filename
    # Prevent path traversal
    try:
        safe_path.resolve().relative_to(Path(WORKSPACE_PATH).resolve())
    except ValueError:
        return PlainTextResponse("Forbidden", status_code=403)
    if safe_path.exists() and safe_path.is_file():
        return PlainTextResponse(safe_path.read_text(encoding='utf-8'))
    return PlainTextResponse("Not found", status_code=404)


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    websocket_connections[session_id] = websocket
    logger.info(f"WebSocket connected: {session_id}")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message["type"] == "start_task":
                await handle_task(websocket, session_id, message)
            elif message["type"] == "stop":
                if session_id in sessions:
                    sessions[session_id].stop()
                    await websocket.send_json({
                        "type": "stopped",
                        "message": "Task stopped by user"
                    })
            elif message["type"] == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
        if session_id in sessions:
            sessions[session_id].stop()
        websocket_connections.pop(session_id, None)
        sessions.pop(session_id, None)


async def handle_task(websocket: WebSocket, session_id: str, message: dict):
    """Handle a new task request"""
    task = message.get("task", "")
    model = message.get("model", "deepseek-coder:6.7b")
    max_iterations = message.get("max_iterations", 15)

    if not task:
        await websocket.send_json({
            "type": "error",
            "message": "No task provided"
        })
        return

    # Create agent with callback for streaming
    async def send_update(update: dict):
        try:
            await websocket.send_json(update)
        except Exception as e:
            logger.error(f"Failed to send update: {e}")

    agent = AutonomousAgent(
        model=model,
        max_iterations=max_iterations,
        callback=send_update,
        session_id=session_id
    )
    sessions[session_id] = agent

    await websocket.send_json({
        "type": "task_started",
        "task": task,
        "session_id": session_id
    })

    # Run agent in background
    asyncio.create_task(run_agent(agent, task, websocket))


async def run_agent(agent: AutonomousAgent, task: str, websocket: WebSocket):
    """Run agent and handle completion"""
    try:
        result = await agent.run(task)
        await websocket.send_json({
            "type": "task_complete",
            "result": result
        })
    except Exception as e:
        logger.error(f"Agent error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
