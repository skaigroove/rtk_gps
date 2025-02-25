import serial
import pynmea2
import socket
import orjson as json
from datetime import datetime, UTC
import time

class GPSClient:
    def __init__(self, serial_port: str, baudrate: int,
                 server_host: str, server_port: int, user_id: str):
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.server_host = server_host
        self.server_port = server_port
        self.user_id = user_id
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def read_and_send_gps(self):
        print(f"[GPSClient] Sending to {self.server_host}:{self.server_port}")
        with serial.Serial(self.serial_port, self.baudrate, timeout=0.1) as ser:
            while True:
                try:
                    line = ser.readline().decode('ascii', errors='ignore').strip()
                    if line.startswith('$'):
                        msg = pynmea2.parse(line)
                        # GGA/RMC 등 위치 정보가 있는 경우
                        if isinstance(msg, (pynmea2.types.talker.GGA, pynmea2.types.talker.RMC)):
                            data = {
                                "user_id": self.user_id,
                                "latitude": msg.latitude if hasattr(msg, 'latitude') else 0.0,
                                "longitude": msg.longitude if hasattr(msg, 'longitude') else 0.0,
                                "quality": getattr(msg, 'gps_qual', None),
                                "client_time": datetime.now(UTC).isoformat()
                            }
                            self.sock.sendto(json.dumps(data), (self.server_host, self.server_port))

                except pynmea2.ParseError:
                    # 잘못된 NMEA 문장 등 파싱 오류 발생 시
                    continue
                except Exception as e:
                    print(f"[GPSClient] Error: {e}")
                    time.sleep(1)

if __name__ == "__main__":
    # 이 부분을 실제 환경에 맞춰 수정하세요
    client = GPSClient(
        serial_port="/dev/ttyUSB0",   # GPS 포트 (예: '/dev/ttyUSB0')
        baudrate=115200,
        server_host="hkitserver.iptime.org",  # 서버 주소 (DNS 또는 IP)
        server_port=5005,             # 서버가 수신할 UDP 포트
        user_id="client1"             # 식별용 ID
    )
    client.read_and_send_gps()
