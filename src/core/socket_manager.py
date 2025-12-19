from typing import List, Any

class SocketManager:
    """
    Stub for WebSocket state broadcasting.
    In the future, this will connect to a real WS server (FastAPI/Starlette).
    """
    def __init__(self):
        self.clients: List[Any] = []

    async def connect(self, client: Any):
        self.clients.append(client)
        print(f"Client connected. Total: {len(self.clients)}")

    async def broadcast(self, message: dict):
        """
        Simulate broadcasting a message to all connected clients.
        """
        # In a real app: await client.send_json(message)
        print(f"[WS BROADCAST] {message}")
