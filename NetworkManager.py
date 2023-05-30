from typing import Union
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
# import json
import socket
from threading import Thread
import select
import random
import time
from CRDT import CRDT
from Msg import Msg

# Generic class to perform tcp send, tcp listen, udp listen, udp broadcast
class NetworkManager:
    def __init__(self, port):
        self.peers = {}  # {ip: status}
        self.ip = self.get_myip()
        self.port = port
        self.current_status = "work"
        self.variable_name_to_object: dict[str, CRDT] = {}
        self.peers_variables_max_nonces: dict[str, dict[str, int]] = {}

    def get_peers(self):
        return self.peers
    
    def get_variable_name_to_object(self) -> dict[str, CRDT]:
        return self.variable_name_to_object 
        
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

    def _sync_broadcast(self) -> None:
        while True:
            for variable_name in self.variable_name_to_object:
                crdt = self.variable_name_to_object[variable_name]
                msg = Msg().init_sync_data(variable_name, crdt.before_sync_value, crdt.self_history)
                thread = Thread(target=self._broadcast, args=(msg,))
                thread.start()
            time.sleep(0.1)

    def schedule_sync_broadcast(self) -> None:
        Thread(target=self._sync_broadcast).start()

    # Sends given message to given ip with tcp
    def send_threaded(self, msg: Msg, ip: str):
        thread = Thread(target=self._send, args=(msg, ip))
        thread.start()

    # Sends given message to broadcast ip
    def broadcast_threaded(self, msg: Msg):
        thread = Thread(target=self._broadcast, args=(msg,))
        thread.start()

    def listen_tcp_threaded(
        self
    ):
        thread = Thread(
            target=self._listen_tcp,
        )
        thread.start()

    def listen_udp_threaded(
        self
    ):
        thread = Thread(
            target=self._listen_udp,
        )
        thread.start()

    def _send(self, msg: Msg, ip: str):
        jsonstr_msg = msg.to_jsonstr()
        print(123123123, jsonstr_msg)
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

    def _listen_tcp(self):
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
                            conn.close()
                            s.close()
                            continue

                        print("asdasdasd, msg:", msg.to_string())
                        self._network_handler(msg, addr[0])  # addr[0] -> ip

                        self._crdt_handler(msg, addr[0])  # addr[0] -> ip

                        if not data:
                            break
                    conn.close()
                s.close()
            except Exception as e:
                s.close()
                print("ERROR in _listen_tcp: ", e)

    def _listen_udp(self):
        while True:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("", self.port))
                s.setblocking(False)
                result = select.select([s], [], [])
                # jsonstr_msg, ip = result[0][0].recvfrom(1024)
                jsonstr_msg, ip = result[0][0].recvfrom(4096)
                msg = Msg().from_jsonstr(jsonstr_msg.decode())

                if self.ip == ip[0]:
                    s.close()
                    continue

                self._network_handler(msg, ip[0])

                self._crdt_handler(msg, ip[0])

                s.close()
            except Exception as e:
                s.close()
                print("ERROR in _listen_udp: ", e)

    def _network_handler(self, msg: Msg, ip: str):
        # TODO: add global for variable_name_to_object?

        msg_type = msg.__getitem__("msg_type")

        # check for status of the node
        if msg_type == MSG_HELLO:
            status = msg.__getitem__("status")
            ip_from_message = msg.__getitem__("ip")
            print(f"ip is found as {ip}, {ip_from_message} with status: {status}")
            for variable in self.variable_name_to_object:
                crdt = self.variable_name_to_object[variable]
                self.peers[ip_from_message] = status
                print("ASDASDASDASD", self.peers)
                self.send_threaded(
                    Msg().init_sync_data(variable, crdt.get_before_sync_value(), crdt.get_self_history()),
                    ip,
                )
                
        if msg_type == MSG_START_SYNC:
            try:
                self.current_status = "sync" # start the syncing process
                time.sleep(0.1)

                # this code is duplicate of the one on _handle_user_input
                variable_max_nonce_dict: dict[str, int] = {}
                for variable_name in self.variable_name_to_object:
                    crdt = self.variable_name_to_object[variable_name]
                    variable_max_nonce_dict[variable_name] = crdt.current_nonce
                    
                start_sync_msg = Msg().init_start_sync(variable_max_nonce_dict)
                for node_ip in self.peers: # TODO: peers is not populated correctly.
                    self.send_threaded(start_sync_msg, node_ip)

                # send the needed data to the sync requester
                variable_max_nonce_dict = msg.__getitem__("variable_max_nonce_dict")
                print(f"Values from the start_sync_request: {variable_max_nonce_dict}")
                for variable_name in variable_max_nonce_dict:
                    if variable_name not in self.variable_name_to_object:
                        self.variable_name_to_object[variable_name] = CRDT(variable_name)

                    max_nonce = variable_max_nonce_dict[variable_name]
                    missing_nonce_list: list[int] = []
                    for nonce_number in range(max_nonce):
                        if nonce_number not in self.variable_name_to_object[variable_name].sync_history:
                            missing_nonce_list.append(nonce_number)

                    msg = Msg().init_nonce_request(variable_name, missing_nonce_list)
                    self.send_threaded(msg, ip)
            except Exception as e:
                print("msg_start_sync error:", e)

        if msg_type == MSG_NONCE_REQUEST:
            try:
                variable_name = msg.__getitem__("variable_name")
                nonce_number_list = msg.__getitem__("nonce_number_list")
                crdt = self.variable_name_to_object[variable_name]
                nonce_dict = crdt._get_nonce_values(nonce_number_list)
                
                msg = Msg().init_nonce_send(variable_name, nonce_dict)
                self.send_threaded(msg, ip)
            except Exception as e:
                print("msg_nonce_request error:", e)

        if msg_type == MSG_NONCE_SEND:
            try:
                variable_name = msg.__getitem__("variable_name")
                nonce_dict = msg.__getitem__("nonce_dict")
                print(0)
                self.variable_name_to_object[variable_name].sync_history[ip].update(nonce_dict)
                print(1)

                self.variable_name_to_object[variable_name]._sync_with_history()
                print(2)

                # TODO: check if the max_nonce values are achieved.
                everything_is_ready = True
                for node_id in self.peers_variables_max_nonces:
                    variable_nonce_dict = self.peers_variables_max_nonces[node_id]
                    for variable_name in variable_nonce_dict:
                        max_nonce = variable_nonce_dict[variable_name]
                        missing_nonce_list: list[int] = []
                        print(3)
                        for nonce_number in range(max_nonce):
                            if nonce_number not in self.variable_name_to_object[node_id].sync_history:
                                missing_nonce_list.append(nonce_number)
                                everything_is_ready = False

                        print(4)
                        if len(missing_nonce_list) > 0:
                            msg = Msg().init_nonce_request(variable_name, missing_nonce_list)
                            self.send_threaded(msg, node_id)
                print(5)
                if everything_is_ready:
                    self.current_status = "ready"
                    # TOOD: send a status change message...
            except Exception as e:
                print("msg_nonce_send error:", e)

    def _crdt_handler(self, msg: Msg, ip: str):
    # TODO: We should call this from network_handler. Assuming all ips this function is called with are whitelisted.
    # if ip not in variable_name_to_object:
    #     print(f"node_id with ip: {ip} is not known.")
    #     return

        msg_type = msg.__getitem__("msg_type")  # TODO: this should be handled in network_handler function
        if msg_type == MSG_VARIABLE_UPDATE or msg_type == MSG_SYNC_DATA:
            variable_name = msg.__getitem__("variable_name")

            if variable_name not in self.variable_name_to_object:
                print(f"variable_name: {variable_name} does not exist on this node")
                self.variable_name_to_object[variable_name] = CRDT(variable_name)
                # TODO: handle this case. Create a new crdt object and sync by maybe asking for whole history...

            crdt = self.variable_name_to_object[variable_name]
            crdt.handle_msg(msg, ip)

    def handle_user_input(self, operation_value: Union[str, int], variable_name: str):
        variable_name_to_object = self.variable_name_to_object
        if variable_name not in variable_name_to_object:
            print(f"{variable_name} not found. Generating new variable with value 0")
            variable_name_to_object[variable_name] = CRDT(variable_name)

        crdt = variable_name_to_object[variable_name]

        if operation_value == "get":
            print(f"value for {variable_name}: {crdt.get_value()}\n")
        elif operation_value == "before":
            print(f"previous value of {variable_name}: {crdt.get_before_sync_value()}\n")
        elif operation_value == "history":
            print(f"{variable_name} - self history: : {crdt.get_self_history()}")
            print(f"{variable_name} - history: : {crdt.get_sync_history()}\n")
        elif operation_value == "full-sync":
            print("START FULL-SYNC")
            # TODO: implement sync in manual fashion first
            # network_manager.broadcast_threaded(Msg().init_start_sync())

            # TODO: Set current status to sync - Maybe do this for individual variables? Would be cooler. Like a distributed mutex lock...
            # TODO: need to add relevant checks for this on function calls
            self.current_status = "sync"
            time.sleep(0.1) # sleep, since we don't use locks. nonce value could be changed by another thread

            # TODO: send sync initiating message to all the nodes via tcp, telling what variables and their max_nonce values
            variable_max_nonce_dict: dict[str, int] = {}
            for variable_name in self.variable_name_to_object:
                crdt = self.variable_name_to_object[variable_name]
                variable_max_nonce_dict[variable_name] = crdt.current_nonce
                
            start_sync_msg = Msg().init_start_sync(variable_max_nonce_dict)
            print("self peers:", self.peers)
            for node_ip in self.peers: # TODO: peers is not populated correctly.
                self.send_threaded(start_sync_msg, node_ip)

            print(f"'{start_sync_msg.to_string()}' is sent to all peers.")

            # left as is for now
            # # Check if all the peers are ready to sync, are in sync mode.
            # # TODO: wait until all nodes-peers are in sync mode
            # while True:
            #     all_in_sync_mode = True
            #     for i in self.peers:
            #         if self.peers[i] != "sync":
            #             all_in_sync_mode = False
            #     if all_in_sync_mode:
            #         break

            # # TODO: start broadcasting sync packages for each crdt data OR start asking for missing nonce values



        elif operation_value == "missing":
            missing_nonce_list = crdt.get_missing_nonces()
            print(f"missing nonce list {missing_nonce_list}")

        elif operation_value == "populate":
            for _ in range(0,1000):
                number = random.randint(-10000, 10000)
                crdt.operate(number)
                self.broadcast_threaded(Msg().init_variable_update(variable_name, number, crdt.current_nonce - 1))
        else:
            try:
                operation_value = int(operation_value)  # TODO: error handling
                crdt.operate(operation_value)
                self.broadcast_threaded(Msg().init_variable_update(variable_name, operation_value, crdt.current_nonce - 1))
            except Exception as e:
                print(f"Encountered error: {e}")
