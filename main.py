import os
from typing import List, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        await self.broadcast({"type": "system", "text": "Someone joined the chat.", "online": self.count})

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    @property
    def count(self) -> int:
        return len(self.active_connections)

    async def send_personal_message(self, message: dict, websocket: WebSocket) -> None:
        await websocket.send_json(message)

    async def broadcast(self, message: dict) -> None:
        to_remove: List[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                # If a connection is broken, mark for removal
                to_remove.append(connection)
        for ws in to_remove:
            self.active_connections.discard(ws)


manager = ConnectionManager()


@app.get("/")
def read_root():
    return {"message": "Anonymous chat backend is running", "online": manager.count}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Expecting {"type": "message", "text": "..."}
            text = str(data.get("text", "")).strip()
            if not text:
                continue
            payload = {"type": "message", "text": text}
            await manager.broadcast(payload)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        # Inform others someone left
        if manager.count > 0:
            await manager.broadcast({"type": "system", "text": "Someone left the chat.", "online": manager.count})
    except Exception:
        manager.disconnect(websocket)
        if manager.count > 0:
            await manager.broadcast({"type": "system", "text": "A connection was lost.", "online": manager.count})


@app.get("/test")
def test_database():
    """Compatibility endpoint from template."""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Used",
        "database_url": None,
        "database_name": None,
        "connection_status": "N/A",
        "collections": []
    }
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
