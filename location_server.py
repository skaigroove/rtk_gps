import asyncio
import websockets
import orjson as json
from datetime import datetime
from typing import Dict
from dataclasses import dataclass, asdict
import logging
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LocationServer")

@dataclass
class LocationData:
    user_id: str
    latitude: float
    longitude: float
    quality: int = None
    timestamp: str = ""
    client_time: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def is_valid(self) -> bool:
        return (-90 <= self.latitude <= 90 and -180 <= self.longitude <= 180)

class LocationServer:
    def __init__(self, ws_host="0.0.0.0", ws_port=5004, udp_port=5005):
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.udp_port = udp_port

        self.locations: Dict[str, LocationData] = {}
        self.connected_websockets = set()

    async def start(self):
        loop = asyncio.get_event_loop()
        self.udp_transport, _ = await loop.create_datagram_endpoint(
            lambda: UDPProtocol(self),
            local_addr=(self.ws_host, self.udp_port)
        )

        async with websockets.serve(
            self.handle_websocket,
            self.ws_host,
            self.ws_port,
            ping_interval=20
        ):
            logger.info(f"[LocationServer] Running - WS:{self.ws_port}, UDP:{self.udp_port}")
            while True:
                await asyncio.sleep(3600)

    async def handle_websocket(self, websocket):
        self.connected_websockets.add(websocket)
        try:
            await websocket.send(json.dumps({
                "type": "status",
                "message": "Connected to server",
                "client_count": len(self.connected_websockets)
            }))

            # 기존 위치가 있다면 초기 broadcast
            if self.locations:
                await self.broadcast_locations()

            async for _ in websocket:
                pass

        except websockets.ConnectionClosed:
            pass
        finally:
            self.connected_websockets.remove(websocket)

    async def broadcast_locations(self):
        if not self.connected_websockets:
            return

        message = {
            "type": "location_update",
            "timestamp": datetime.now().isoformat(),
            "client_count": len(self.connected_websockets),
            "locations": {
                user_id: asdict(loc)
                for user_id, loc in self.locations.items()
            }
        }

        websockets_to_remove = set()
        for ws in self.connected_websockets:
            try:
                await ws.send(json.dumps(message))
            except websockets.ConnectionClosed:
                websockets_to_remove.add(ws)
            except Exception as e:
                logger.error(f"[broadcast] Error: {e}")
                websockets_to_remove.add(ws)

        self.connected_websockets -= websockets_to_remove


class UDPProtocol:
    def __init__(self, server: LocationServer):
        self.server = server

    def datagram_received(self, data, addr):
        try:
            message = json.loads(data)
            loc = LocationData(
                user_id=message.get('user_id'),
                latitude=float(message.get('latitude', 0)),
                longitude=float(message.get('longitude', 0)),
                quality=message.get('quality'),
                client_time=message.get('client_time', '')
            )
            if loc.is_valid():
                self.server.locations[loc.user_id] = loc
                asyncio.create_task(self.server.broadcast_locations())
        except Exception as e:
            logger.error(f"[UDPProtocol] Error: {e}")

if __name__ == "__main__":
    server = LocationServer()
    asyncio.run(server.start())