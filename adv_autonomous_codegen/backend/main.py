from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
from agent import run_agent
from db import init_db, save_session

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    init_db()
    os.makedirs(os.getenv("WORKSPACE_BASE_PATH", "./workspaces"), exist_ok=True)

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    async def send_msg(msg: dict):
        try: await websocket.send_json(msg)
        except: pass
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("command") == "start_task":
                save_session(session_id, data["task"], data.get("model", "llama3"))
                asyncio.create_task(run_agent(session_id, data["task"], data.get("model", "llama3"), int(data.get("max_iterations", 15)), send_msg))
    except WebSocketDisconnect: pass

@app.get("/files/{session_id}/{filename:path}")
def get_file(session_id: str, filename: str):
    path = os.path.join(os.getenv("WORKSPACE_BASE_PATH", "./workspaces"), session_id, filename)
    if os.path.exists(path):
        with open(path, 'r') as f: return {"content": f.read()}
    return {"error": "File not found"}
