from constants import (
    MSG_HELLO,
    MSG_HELLO_RECEIVED,
    MSG_VARIABLE_UPDATE,
    MSG_START_SYNC,
    MSG_STOP_SYNC,
    MSG_STATUS_REQUEST,
    MSG_STATUS,
    MSG_NONCE_REQUEST,
    MSG_NONCE_SEND,
    MSG_SYNC_DATA,
)
import json
import socket
from threading import Thread
import select

# Implemented message types
# {"msg_type": "hello", "ip": "self.ip"}

# {"msg_type": "hello_received", "status": <"work" or "sync">}

# variable_update_package
# {"msg_type": "variable_update", variable_name:<variable_name>, "operation": <5, 1, -1, etc, only 1 integer>}

# start_sync_package
# {"msg_type": "start_sync"}

# stop_sync_package
# {"msg_type": "stop_sync"}

# ask node status
# {"msg_type": "status_request"}

# send node status
# {"msg_type": "status", "status": <"work" or "sync">}

# request missing nonce package
# {"msg_type": "nonce_request", variable_name:<variable_name>, "nonce": <nonce-number>}

# send requested nonce package
# {"msg_type": "nonce_send", variable_name:<variable_name>, "nonce": <nonce-number>}

# send all updates during sync
# {"msg_type": "sync_data", variable_name:<variable_name>, "nonce_list": <history list>}


# Simple wrapper for msg dictionary, introduces a short way of creating dict items
# >>> msg = Msg().init_hello(ip)
# >>> ip = msg["ip"]
class Msg:
    def __init__(self):
        self.msg_dict = {}

    # Q: What if the key is not valid?
    def __getitem__(self, key):
        return self.msg_dict[key]

    def __setitem__(self, key, value):
        self.msg_dict[key] = value

    def clear(self):
        self.msg_dict = {}

    def init_hello(self, ip: str, status: str):
        self.clear()
        self.msg_dict["msg_type"] = MSG_HELLO
        self.msg_dict["status"] = status
        self.msg_dict["ip"] = ip
        return self

    def init_hello_received(self, status: str):
        self.clear()
        self.msg_dict["msg_type"] = MSG_HELLO_RECEIVED
        self.msg_dict["status"] = status
        return self

    def init_variable_update(
        self, variable_name: str, operation: int, nonce: int
    ):  # CRDT related
        self.clear()
        self.msg_dict["msg_type"] = MSG_VARIABLE_UPDATE
        self.msg_dict["variable_name"] = variable_name
        self.msg_dict["operation"] = operation  # Q: do we need to cast to string?
        self.msg_dict["nonce"] = nonce
        return self

    def init_start_sync(self):
        self.clear()
        self.msg_dict["msg_type"] = MSG_START_SYNC
        return self

    def init_stop_sync(self):
        self.clear()
        self.msg_dict["msg_type"] = MSG_STOP_SYNC
        return self

    def init_status_request(self):
        self.clear()
        self.msg_dict["msg_type"] = MSG_STATUS_REQUEST
        return self

    def init_status(self, status: str):
        self.clear()
        self.msg_dict["msg_type"] = MSG_STATUS
        self.msg_dict["status"] = status
        return self

    def init_nonce_request(self, variable_name: str, nonce: int):
        self.clear()
        self.msg_dict["msg_type"] = MSG_NONCE_REQUEST
        self.msg_dict["variable_name"] = variable_name
        self.msg_dict["nonce_number"] = nonce
        return self

    def init_nonce_send(self, variable_name: str, nonce: int):
        self.clear()
        self.msg_dict["msg_type"] = MSG_NONCE_SEND
        self.msg_dict["variable_name"] = variable_name
        self.msg_dict["nonce_number"] = nonce
        return self

    def init_sync_data(self, variable_name: str, previous_value: int, history: dict):
        self.clear()
        self.msg_dict["msg_type"] = MSG_SYNC_DATA
        self.msg_dict["variable_name"] = variable_name
        self.msg_dict["history"] = history
        self.msg_dict["previous_value"] = previous_value
        return self

    def from_jsonstr(self, jsonstr: str):
        self.clear()
        self.msg_dict = json.loads(jsonstr)
        return self

    def to_string(self):
        return self.msg_dict

    def to_jsonstr(self) -> str:
        return json.dumps(self.msg_dict)


# Generic class to perform tcp send, tcp listen, udp listen, udp broadcast
class NetworkManager:
    def __init__(self, port):
        self.peers = {}  # {ip: status}
        self.ip = self.get_myip()
        self.port = port

    def get_peers(self):
        return self.peers

    def get_myip(self) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            # doesn't even have to be reachable
            s.connect(("10.254.254.254", 1))
            ip = s.getsockname()[0]
        except Exception as e:
            print("ERROR in get_myip: ", e)
            ip = "127.0.0.1"
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

    def listen_tcp_threaded(
        self, network_msg_handler=None, crdt_msg_handler=None, network_manager=None
    ):
        thread = Thread(
            target=self._listen_tcp,
            args=(network_msg_handler, crdt_msg_handler, network_manager),
        )
        thread.start()

    def listen_udp_threaded(
        self, network_msg_handler=None, crdt_msg_handler=None, network_manager=None
    ):
        thread = Thread(
            target=self._listen_udp,
            args=(network_msg_handler, crdt_msg_handler, network_manager),
        )
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
            # s.bind(('', self.port)) # INFO: didn't work on macos, below one worked
            s.bind(("", 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(jsonstr_msg.encode(), ("<broadcast>", self.port))
            s.close()
        except Exception as e:
            s.close()
            print("ERROR in _broadcast: ", e)

    def _listen_tcp(self, network_msg_handler, crdt_msg_handler, network_manager):
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

                        if self.ip == addr[0]:
                            print("discarding own message")
                            conn.close()
                            s.close()
                            continue

                        if network_msg_handler:
                            network_msg_handler(
                                msg, addr[0], network_manager
                            )  # addr[0] -> ip
                        if crdt_msg_handler:
                            crdt_msg_handler(msg, addr[0])  # addr[0] -> ip

                        if not data:
                            break
                    conn.close()
                s.close()
            except Exception as e:
                s.close()
                print("ERROR in _listen_tcp: ", e)

    def _listen_udp(self, network_msg_handler, crdt_msg_handler, network_manager):
        while True:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("", self.port))
                s.setblocking(False)
                result = select.select([s], [], [])
                jsonstr_msg, ip = result[0][0].recvfrom(1024)
                msg = Msg().from_jsonstr(jsonstr_msg.decode())

                if self.ip == ip[0]:
                    print("discarding own message")
                    s.close()
                    continue

                if network_msg_handler:
                    network_msg_handler(msg, ip[0], network_manager)
                if crdt_msg_handler:
                    crdt_msg_handler(msg, ip[0])

                s.close()
            except Exception as e:
                s.close()
                print("ERROR in _listen_udp: ", e)


# if __name__ == "__main__":
#     def network_handler(msg: Msg, ip: str):
#         print(msg)
#         print(ip)

#     network_manager = NetworkManager(12345)
#     network_manager.listen_tcp_threaded(network_handler, None)
#     network_manager.listen_udp_threaded(network_handler, None)
#     network_manager.broadcast_threaded(Msg().init_hello(network_manager.ip, "work"))
