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

    def init_variable_update(self, variable_name: str, operation: int, nonce: int):  # CRDT related
        self.clear()
        self.msg_dict["msg_type"] = MSG_VARIABLE_UPDATE
        self.msg_dict["variable_name"] = variable_name
        self.msg_dict["operation"] = operation  # Q: do we need to cast to string?
        self.msg_dict["nonce"] = nonce
        return self

    def init_start_sync(self, variable_max_nonce_dict):
        self.clear()
        self.msg_dict["msg_type"] = MSG_START_SYNC
        self.msg_dict["variable_max_nonce_dict"] = variable_max_nonce_dict
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

    def init_nonce_request(self, variable_name: str, nonce_list: list[int]):
        self.clear()
        self.msg_dict["msg_type"] = MSG_NONCE_REQUEST
        self.msg_dict["variable_name"] = variable_name
        self.msg_dict["nonce_number_list"] = nonce_list
        return self

    def init_nonce_send(self, variable_name: str, nonce_dict: dict[int, int]):
        self.clear()
        self.msg_dict["msg_type"] = MSG_NONCE_SEND
        self.msg_dict["variable_name"] = variable_name
        self.msg_dict["nonce_dict"] = nonce_dict
        return self

    def init_sync_data(self, variable_name: str, previous_value: int, history: dict[int, int]):
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

    def convert_dict_to_dict(self, original_dict) -> dict[int, int]:
        new_dict = {int(key): value for key, value in original_dict.items()}
        return new_dict

