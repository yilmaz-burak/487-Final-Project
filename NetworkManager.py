import json
import socket
from threading import Thread
import select


# Implemented message types
# {"msg_type": "hello", "ip": "self.ip"}


# Other msg types should be implemented as well
# Simple wrapper for msg dictionary, introduces a short way of creating dict items
# >>> msg = Msg().init_hello(ip)
class Msg:
    def __init__(self):
        self.msg_dict = {}

    def __getitem__(self, key):
        return self.msg_dict[key]

    def __setitem__(self, key, value):
        self.msg_dict[key] = value

    def clear(self):
        self.msg_dict = {}

    def init_hello(self, ip: str):
        self.clear()
        self.msg_dict["msg_type"] = "hello"
        self.msg_dict["ip"] = ip

    def from_jsonstr(self, jsonstr: str):
        self.clear()
        self.msg_dict = json.loads(jsonstr)
        return self

    def to_jsonstr(self) -> str:
        return json.dumps(self.msg_dict)


# Generic class to perform tcp send, tcp listen, udp listen, udp broadcast
class NetworkManager:
    def __init__(self, port):
        self.peers = []  # [[ip, status]]
        self.ip = self.get_myip()
        self.port = port

    def get_myip(self) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            # doesn't even have to be reachable
            s.connect(('10.254.254.254', 1))
            ip = s.getsockname()[0]
        except Exception as e:
            print("ERROR in get_myip: ", e)
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    # Sends given message to given ip with tcp
    def send_threaded(self, msg: Msg, ip: str):
        thread = Thread(target=self._send, args=(msg, ip))
        thread.start()

    # Sends given message to broadcast ip
    def broadcast_threaded(self, msg: Msg):
        thread = Thread(target=self._broadcast, args=(msg,))
        thread.start()

    def listen_tcp_threaded(self, network_msg_handler=None, crdt_msg_handler=None):
        thread = Thread(target=self._listen_tcp, args=(network_msg_handler, crdt_msg_handler))
        thread.start()

    def listen_udp_threaded(self, network_msg_handler=None, crdt_msg_handler=None):
        thread = Thread(target=self._listen_udp, args=(network_msg_handler, crdt_msg_handler))
        thread.start()

    def _send(self, msg: Msg, ip: str):
        jsonstr_msg = msg.to_jsonstr()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((ip, self.port))
                s.sendall(jsonstr_msg.encode())
                s.close()
        except Exception as e:
            print("ERROR in _send: ", e)

    def _broadcast(self, msg: Msg):
        jsonstr_msg = msg.to_jsonstr()
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('', self.port))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(jsonstr_msg.encode(), ('<broadcast>', self.port))
            s.close()
        except Exception as e:
            s.close()
            print("ERROR in _broadcast: ", e)

    def _listen_tcp(self, network_msg_handler, crdt_msg_handler):
        while True:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("", self.port))
                s.listen()
                conn, addr = s.accept()
                with conn:
                    while True:
                        data = conn.recv(2048)
                        jsonstr_msg = data.decode()
                        msg = Msg().from_jsonstr(jsonstr_msg)

                        if network_msg_handler:
                            network_msg_handler(msg)
                        if crdt_msg_handler:
                            crdt_msg_handler(msg)

                        if not data:
                            break
                    conn.close()
                s.close()
            except Exception as e:
                s.close()
                print("ERROR in _listen_tcp: ", e)

    def _listen_udp(self, network_msg_handler, crdt_msg_handler):
        while True:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('', self.port))
                s.setblocking(False)
                result = select.select([s], [], [])
                jsonstr_msg, ip = result[0][0].recvfrom(1024)
                msg = Msg().from_jsonstr(jsonstr_msg.decode())

                if network_msg_handler:
                    network_msg_handler(msg)
                if crdt_msg_handler:
                    crdt_msg_handler(msg)

                s.close()
            except Exception as e:
                s.close()
                print("ERROR in _listen_udp: ", e)


if __name__ == "__main__":
    network_manager = NetworkManager(12345)
    network_manager.listen_tcp_threaded()
    network_manager.listen_udp_threaded()
