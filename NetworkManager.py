from typing import Union, Dict, List
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
    MSG_SYNC_MISMATCH_REQUEST,
    MSG_SYNC_MISMATCH_DATA,
    LISTEN_BUFFER_SIZE
)
# import json
import socket
from threading import Thread, Timer
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
        self.variable_name_to_object: Dict[str, CRDT] = {}
        self.peers_variables_max_nonces: Dict[str, Dict[str, int]] = {}
        self.peers_sync_values: Dict[str, Dict[str, int]] = {}
        
        # Continiously check if all the nodes are in ready state, if so make changes accordingly
        # Thread(target=self._check_status).start()

    def get_peers(self):
        return self.peers

    def get_variable_name_to_object(self) -> Dict[str, CRDT]:
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

    def periodic_hello_broadcast(self, sleep_duration):
        while True:
            self.broadcast_threaded(Msg().init_hello(self.ip, self.current_status))
            time.sleep(sleep_duration)
    
    def _sync_broadcast(self) -> None:
        while True:
            for variable_name in self.variable_name_to_object:
                crdt = self.variable_name_to_object[variable_name]
                msg = Msg().init_sync_data(variable_name, crdt.before_sync_value, crdt.self_history)
                thread = Thread(target=self._broadcast, args=(msg,))
                thread.start()
            time.sleep(100)

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
        # print("SENDING:", jsonstr_msg)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((ip, self.port))
                s.sendall(jsonstr_msg.encode())
                s.close()
        except Exception as e:
            print("ERROR in _send: ", e)
            self._send(msg, ip)

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
                        data = conn.recv(LISTEN_BUFFER_SIZE)
                        if not data:
                            break
                        jsonstr_msg = data.decode()
                        msg = Msg().from_jsonstr(jsonstr_msg)

                        if self.ip == addr[0]:
                            conn.close()
                            s.close()
                            continue
                        
                        self._network_handler(msg, addr[0])  # addr[0] -> ip

                        self._crdt_handler(msg, addr[0])  # addr[0] -> ip

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
                jsonstr_msg, ip = result[0][0].recvfrom(LISTEN_BUFFER_SIZE)
                msg = Msg().from_jsonstr(jsonstr_msg.decode())

                #if msg.msg_dict["msg_type"] != "hello" and msg.msg_dict["msg_type"] != "hello":

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
            try:
                status = msg.__getitem__("status")
                ip_from_message = msg.__getitem__("ip")
                # print(f"ip is found as {ip}, {ip_from_message} with status: {status}")
                if ip not in self.peers:
                    for variable in self.variable_name_to_object:
                        crdt = self.variable_name_to_object[variable]
                        self.peers[ip_from_message] = status
                        self.send_threaded(
                            Msg().init_sync_data(variable, crdt.get_before_sync_value(), crdt.get_self_history()),
                            ip,
                        )
                    self.send_threaded(Msg().init_hello_received(self.current_status), ip)

                    if status == "work" and (self.current_status == "ready" or self.current_status == "sync"):
                        variable_max_nonce_dict: Dict[str, int] = {}
                        for variable_name in self.variable_name_to_object:
                            crdt = self.variable_name_to_object[variable_name]
                            variable_max_nonce_dict[variable_name] = crdt.current_nonce

                        start_sync_msg = Msg().init_start_sync(variable_max_nonce_dict)
                        self.send_threaded(start_sync_msg, ip_from_message)

            except Exception as e:
                print("Hello error:", e)

        if msg_type == MSG_HELLO_RECEIVED:
            try:
                status = msg.__getitem__("status")
                # print(f"ip is found as {ip}, {ip_from_message} with status: {status}")
                self.peers[ip] = status
            except Exception as e:
                print("Hello_received error:", e)

        if msg_type == MSG_STOP_SYNC:
            #print("GOT STOP SYNC", msg.to_string())
            try:
                variable_value_dict = msg.__getitem__("variable_value_dict")
                self.peers_sync_values[ip] = variable_value_dict
            except Exception as e:
                print("msg_stop_sync error:", e)

        if msg_type == MSG_START_SYNC:
            try:
                self.current_status = "sync"  # start the syncing process
                time.sleep(0.1)

                # this code is duplicate of the one on _handle_user_input
                variable_max_nonce_dict: Dict[str, int] = {}
                for variable_name in self.variable_name_to_object:
                    crdt = self.variable_name_to_object[variable_name]
                    variable_max_nonce_dict[variable_name] = crdt.current_nonce

                start_sync_msg = Msg().init_start_sync(variable_max_nonce_dict)
                for node_ip in self.peers:  # TODO: peers is not populated correctly.
                    # if node_ip != ip:
                    self.send_threaded(start_sync_msg, node_ip)

                # send the needed data to the sync requester
                variable_max_nonce_dict = msg.__getitem__("variable_max_nonce_dict")
                for variable_name in variable_max_nonce_dict:
                    if variable_name not in self.variable_name_to_object:
                        self.variable_name_to_object[variable_name] = CRDT(variable_name)

                    max_nonce = variable_max_nonce_dict[variable_name]
                    missing_nonce_list: List[int] = []
                    for nonce_number in range(max_nonce):
                        if nonce_number not in self.variable_name_to_object[variable_name].sync_history:
                            missing_nonce_list.append(nonce_number)

                    self.peers_variables_max_nonces[ip] = variable_max_nonce_dict
                    print(f"\nself.peers_variables_max_nonces: {self.peers_variables_max_nonces}\n")

                    msg = Msg().init_nonce_request(variable_name, missing_nonce_list)
                    self.send_threaded(msg, ip)
            except Exception as e:
                print("msg_start_sync error:", e)

        if msg_type == MSG_SYNC_MISMATCH_REQUEST:
            variable_max_nonce_dict: Dict[str, int] = {}
            for variable_name in self.variable_name_to_object:
                crdt = self.variable_name_to_object[variable_name]
                variable_max_nonce_dict[variable_name] = crdt.current_nonce

            msg = Msg().init_sync_mismatch_data(variable_max_nonce_dict)
            self.send_threaded(msg, ip)

        if msg_type == MSG_SYNC_MISMATCH_DATA:                
            variable_max_nonce_dict = msg.__getitem__("variable_max_nonce_dict")
            for variable_name in variable_max_nonce_dict:
                if variable_name not in self.variable_name_to_object:
                    self.variable_name_to_object[variable_name] = CRDT(variable_name)

                max_nonce = variable_max_nonce_dict[variable_name]
                missing_nonce_list: List[int] = []
                for nonce_number in range(max_nonce):
                    if nonce_number not in self.variable_name_to_object[variable_name].sync_history:
                        missing_nonce_list.append(nonce_number)

                self.peers_variables_max_nonces[ip] = variable_max_nonce_dict
                print(f"\nself.peers_variables_max_nonces: {self.peers_variables_max_nonces}\n")

                msg = Msg().init_nonce_request(variable_name, missing_nonce_list)
                self.send_threaded(msg, ip)

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
            print("GOT NONCE SEND: ", msg.to_string())
            try:
                variable_name = msg.__getitem__("variable_name")
                nonce_dict = msg.convert_dict_to_dict(msg.__getitem__("nonce_dict"))
                self.variable_name_to_object[variable_name].sync_history[ip].update(nonce_dict)

                self.variable_name_to_object[variable_name]._sync_with_history()

                # # TODO: check if the max_nonce values are achieved.
                # everything_is_ready = True
                # for node_id in self.peers_variables_max_nonces:
                #     variable_nonce_dict = self.peers_variables_max_nonces[node_id]
                #     for variable_name in variable_nonce_dict:
                #         max_nonce = variable_nonce_dict[variable_name]
                #         missing_nonce_list: List[int] = []
                #         for nonce_number in range(max_nonce):
                #             if nonce_number not in self.variable_name_to_object[node_id].sync_history:
                #                 missing_nonce_list.append(nonce_number)
                #                 everything_is_ready = False

                #         if len(missing_nonce_list) > 0:
                #             msg = Msg().init_nonce_request(variable_name, missing_nonce_list)
                #             self.send_threaded(msg, node_id)
                # if everything_is_ready:
                #     self.current_status = "ready"
                #     for node_ip in self.peers:  # TODO: peers is not populated correctly.
                #         self.send_threaded(Msg().init_status(self.current_status), node_ip)
            except Exception as e:
                print("msg_nonce_send error:", e)

        if msg_type == MSG_STATUS:
            try:
                self.peers[ip] = msg["status"]
                # print("MSG_STATUS:", msg["status"], ip, self.peers[ip])
            except Exception as e:
                print("msg_status error:", e)

        if msg_type == MSG_STATUS_REQUEST:
            try:
                self.send_threaded(Msg().init_status(self.current_status), ip)
            except Exception as e:
                print("msg_status_request error:", e)

# TODO: better naming for function

    def check_everything_is_ready(self) -> None:
        while True:
            try:
                for node_id in self.peers:
                    print("sending:", self.current_status)
                    self.send_threaded(Msg().init_status(self.current_status), node_id)

                time.sleep(3)
                if self.current_status == "work":
                    # print("in work mode")
                    continue

                elif self.current_status == "ready":
                    while True:
                        print("wait for peers ready")
                        all_in_ready_mode = True
                        for i in self.peers:
                            if self.peers[i] == "sync":
                                all_in_ready_mode = False
                        if all_in_ready_mode:
                            break

                    print("sending stop sync message")
                    variable_value_dict: dict[str, int] = {}
                    for variable_name in self.variable_name_to_object:
                        variable_value_dict[variable_name] = self.variable_name_to_object[variable_name].value
                        
                    msg = Msg().init_stop_sync(variable_value_dict)
                    for node_id in self.peers:
                        self.send_threaded(msg, node_id)

                    # print("here.....")
                    while True:
                        time.sleep(0.1)
                        all_variables_synced = True
                        # print("in while")
                        for variable_name in self.variable_name_to_object:
                            all_nodes_have_same_value = True
                            crdt = self.variable_name_to_object[variable_name]
                            for node_id in self.peers_sync_values:
                                print(11)
                                if variable_name not in self.peers_sync_values[node_id]:
                                    all_nodes_have_same_value = False
                                    all_variables_synced = False
                                    print(12, variable_name, node_id)

                                elif self.peers_sync_values[node_id][variable_name] != crdt.value:
                                    all_nodes_have_same_value = False
                                    all_variables_synced = False
                                    print(13, node_id, variable_name)

                                # TODO: ask for the sync value from node_id
                                    
                            if all_nodes_have_same_value:
                                print(14)
                                crdt.reset()
                                
                        if all_variables_synced:
                            self.current_status = "work"
                            for node_id in self.peers:
                                print(15)
                                self.send_threaded(Msg().init_status(self.current_status), node_id)
                            break
                
                elif self.current_status == "sync":
                    print("inside sync")
                    # TODO: check if the max_nonce values are achieved.
                    everything_is_ready = True
                    if len(self.peers_variables_max_nonces) != len(self.peers) and self.current_status == "sync":
                        # print(f"mismatch: {self.peers_variables_max_nonces}-{self.peers} --> {len(self.peers_variables_max_nonces)} {len(self.peers)}")
                        everything_is_ready = False
                        variable_max_nonce_dict: Dict[str, int] = {}
                        for variable_name in self.variable_name_to_object:
                            crdt = self.variable_name_to_object[variable_name]
                            variable_max_nonce_dict[variable_name] = crdt.current_nonce

                        sync_mismatch_msg = Msg().init_sync_mismatch_request()
                        for node_ip in self.peers: # TODO: only send to missing nodes
                            self.send_threaded(sync_mismatch_msg, node_ip)

                    for node_id in self.peers_variables_max_nonces:
                        variable_nonce_dict = self.peers_variables_max_nonces[node_id]
                        print(1)
                        for variable_name in variable_nonce_dict:
                            max_nonce = variable_nonce_dict[variable_name]
                            missing_nonce_list: List[int] = []
                            print(2)

                            for nonce_number in range(max_nonce):
                                if nonce_number not in self.variable_name_to_object[variable_name].sync_history[node_id]:
                                    missing_nonce_list.append(nonce_number)
                                    everything_is_ready = False
                                    print(3)

                            if len(missing_nonce_list) > 0:
                                msg = Msg().init_nonce_request(variable_name, missing_nonce_list)
                                self.send_threaded(msg, node_id)
                                print("missing nonce list:", missing_nonce_list)

                    if everything_is_ready:
                        print(5)
                        self.current_status = "ready"
                        for node_ip in self.peers:  # TODO: peers is not populated correctly.
                            print(6, node_ip)
                            self.send_threaded(Msg().init_status(self.current_status), node_ip)
                            self.peers_variables_max_nonces = {}
                            print(f"\nself.peers_variables_max_nonces reset: {self.peers_variables_max_nonces}\n")
            except Exception as e:
                print("check_everything exception:", e)


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


    def _start_full_sync(self):
        # TODO: implement sync in manual fashion first
        # network_manager.broadcast_threaded(Msg().init_start_sync())

        # TODO: Set current status to sync - Maybe do this for individual variables? Would be cooler. Like a distributed mutex lock...
        # TODO: need to add relevant checks for this on function calls
        self.current_status = "sync"
        time.sleep(0.1)  # sleep, since we don't use locks. nonce value could be changed by another thread

        # TODO: send sync initiating message to all the nodes via tcp, telling what variables and their max_nonce values
        variable_max_nonce_dict: Dict[str, int] = {}
        for variable_name in self.variable_name_to_object:
            crdt = self.variable_name_to_object[variable_name]
            variable_max_nonce_dict[variable_name] = crdt.current_nonce

        start_sync_msg = Msg().init_start_sync(variable_max_nonce_dict)
        print("self peers:", self.peers)
        for node_ip in self.peers:  # TODO: peers is not populated correctly.
            self.send_threaded(start_sync_msg, node_ip)

        print(f"'{start_sync_msg.to_string()}' is sent to all peers.")

        

        # # left as is for now
        # # # Check if all the peers are ready to sync, are in sync mode.
        # # # TODO: wait until all nodes-peers are in sync mode
        # while True:
        #     all_in_sync_mode = True
        #     for i in self.peers:
        #         if self.peers[i] != "sync":
        #             all_in_sync_mode = False
        #     if all_in_sync_mode:
        #         break

    def handle_user_input(self, operation_value: Union[str, int], variable_name: str):
        variable_name_to_object = self.variable_name_to_object



        if operation_value == "create":
            variable_name_to_object[variable_name] = CRDT(variable_name)
            return print(f"Created {variable_name} variable")

        try:
            crdt = variable_name_to_object[variable_name]
            if operation_value == "get":
                print(f"value for {variable_name}: {crdt.get_value()}\n")
            elif operation_value == "before":
                print(f"previous value of {variable_name}: {crdt.get_before_sync_value()}\n")
            elif operation_value == "history":
                print(f"{variable_name} - self history: : {crdt.get_self_history()}")
                print(f"{variable_name} - history: : {crdt.get_sync_history()}\n")
            elif operation_value == "s":
                # self._start_full_sync()
                self.schedule_full_sync()
            elif operation_value == "peers":
                print(f"peers: {self.peers}")
            elif operation_value == "variables":
                s = ""
                for i in self.variable_name_to_object:
                    s += f"'{i}' "
                print(f"all variables: {s}")
            elif operation_value == "status":
                print("current_status:", self.current_status)

                # TODO: start broadcasting sync packages for each crdt data OR start asking for missing nonce values



            elif operation_value == "missing":
                missing_nonce_list = crdt.get_missing_nonces()
                print(f"missing nonce list {missing_nonce_list}")

            elif operation_value == "populate":
                if self.current_status == "work":
                    for _ in range(0, 10):
                        number = random.randint(-10000, 10000)
                        crdt.operate(number)
                        self.broadcast_threaded(Msg().init_variable_update(variable_name, number, crdt.current_nonce - 1))
                else:
                    print("wait full-sync to finish")
                    #TODO: Maybe add message queue instead of blocking
            else:
                if self.current_status == "work":
                    try:
                        operation_value = int(operation_value)  # TODO: error handling
                        crdt.operate(operation_value)
                        self.broadcast_threaded(
                            Msg().init_variable_update(variable_name, operation_value, crdt.current_nonce - 1))
                    except Exception as e:
                        print(f"Encountered error: {e}")
                else:
                    print("wait full-sync to finish")
                    #TODO: Maybe add message queue instead of blocking
        except Exception as e:
            print(f"invalid variable name: {variable_name}")


    def _check_status(self) -> None:
        while True:
            if self.current_status == "ready":
                for i in self.peers:
                    if self.peers[i] == "ready":
                        variable_value_dict: dict[str, int] = {}
                        for variable_name in self.variable_name_to_object:
                            variable_value_dict[variable_name] = self.variable_name_to_object[variable_name].value
                            
                        msg = Msg().init_stop_sync(variable_value_dict)
                        for node_id in self.peers:
                            self.send_threaded(msg, node_id)

                        # TODO: if all the peers have the correct values, flush the history
                        while True:
                            all_variables_synced = True
                            for variable_name in self.variable_name_to_object:
                                all_nodes_have_same_value = True
                                crdt = self.variable_name_to_object[variable_name]
                                for node_id in self.peers_sync_values:
                                    if self.peers_sync_values[node_id][variable_name] != crdt.value:
                                        all_nodes_have_same_value = False
                                        all_variables_synced = False

                                if all_nodes_have_same_value:
                                    crdt.reset()
                                    
                            if all_variables_synced:
                                break
                Timer(60.0, self._start_full_sync).start()
            time.sleep(1)
            

    def schedule_full_sync(self) -> None:
        # # REMINDER: we might not accept new nodes during syncing

        # # TODO: wait for time to sync, reset this after sync is finished
        # time.sleep(60)

        # TODO: initiate the full-sync
        self._start_full_sync()

        # TODO: wait for all peers' init sync requests with their max nonce values
        # TODO: then, request any missing nonce or set the state to ready.

        
        # # TODO: right after, wait for own status to be ready
        # print("wait for self ready")
        # while True:
        #     if self.current_status == "ready":
        #         break
        # print("waited for self ready")

        # # TODO: after ready, wait for all other node's statuses to be ready
        # print("wait for peers ready")
        # while True:
        #     all_in_ready_mode = True
        #     for i in self.peers:
        #         if self.peers[i] == "sync":
        #             all_in_ready_mode = False
        #     if all_in_ready_mode:
        #         break
        # print("waited for peers ready")

            
        # # TODO: send stop sync message
        # print("sending stop sync message")
        # variable_value_dict: dict[str, int] = {}
        # for variable_name in self.variable_name_to_object:
        #     variable_value_dict[variable_name] = self.variable_name_to_object[variable_name].value
            
        # msg = Msg().init_stop_sync(variable_value_dict)
        # for node_id in self.peers:
        #     self.send_threaded(msg, node_id)

        # print("sent stop sync message:", msg.to_string())

        # TODO: if all the peers have the correct values, flush the history
        # print("here.....")
        # while True:
        #     all_variables_synced = True
        #     for variable_name in self.variable_name_to_object:
        #         all_nodes_have_same_value = True
        #         crdt = self.variable_name_to_object[variable_name]
        #         for node_id in self.peers_sync_values:
        #             if self.peers_sync_values[node_id][variable_name] != crdt.value:
        #                 all_nodes_have_same_value = False
        #                 all_variables_synced = False

        #         if all_nodes_have_same_value:
        #             crdt.reset()
                    
        #     if all_variables_synced:
        #         self.current_status = "work"
        #         break

        
        # self.schedule_full_sync()

    def handle_full_sync(self):

        # TODO: right after, wait for own status to be ready
        print("wait for self ready")
        while True:
            if self.current_status == "ready":
                break
        print("waited for self ready")

        # TODO: after ready, wait for all other node's statuses to be ready
        print("wait for peers ready")
        while True:
            all_in_ready_mode = True
            for i in self.peers:
                if self.peers[i] != "ready":
                    all_in_ready_mode = False
            if all_in_ready_mode:
                break
        print("waited for peers ready")

            
        # TODO: send stop sync message
        print("sending stop sync message")
        variable_value_dict: dict[str, int] = {}
        for variable_name in self.variable_name_to_object:
            variable_value_dict[variable_name] = self.variable_name_to_object[variable_name].value
            
        msg = Msg().init_stop_sync(variable_value_dict)
        for node_id in self.peers:
            self.send_threaded(msg, node_id)

        print("sent stop sync message:", msg.to_string())

        # TODO: if all the peers have the correct values, flush the history
        print("here.....")
        while True:
            all_variables_synced = True
            for variable_name in self.variable_name_to_object:
                all_nodes_have_same_value = True
                crdt = self.variable_name_to_object[variable_name]
                for node_id in self.peers_sync_values:
                    if self.peers_sync_values[node_id][variable_name] != crdt.value:
                        all_nodes_have_same_value = False
                        all_variables_synced = False

                if all_nodes_have_same_value:
                    crdt.reset()
                    
            if all_variables_synced:
                break
