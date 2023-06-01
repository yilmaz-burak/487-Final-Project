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
from Msg import Msg

HistoryObject = dict[int, int]
History = dict[str, HistoryObject]


class CRDT:
    def __init__(self, name):
        self.sync_history: History = {}
        self.self_history: HistoryObject = {}
        self.value = 0
        self.current_nonce = 0
        self.before_sync_value = 0
        self.name = name

    def reset(self) -> None:
        self.before_sync_value = self.value
        self.current_nonce = 0
        self.sync_history = {}
        self.self_history = {}

    def set_value(self, value: int) -> None:
        self.value = value

    def get_value(self) -> int:
        return self.value

    def get_before_sync_value(self) -> int:
        return self.before_sync_value

    def get_sync_history(self) -> History:
        return self.sync_history

    def get_self_history(self) -> HistoryObject:
        return self.self_history

    def get_nonce_value(self, nonce: int) -> int:
        return self.self_history[nonce]

    def operate(self, value: int) -> None:
        self.value += value
        self._add_to_self_history(value)

    def _add_to_self_history(self, value: int) -> None:
        self.self_history[self.current_nonce] = value
        self.current_nonce += 1

    def _add_to_sync_history(self, node_id: str, nonce: int, operation_value: int) -> None:
        self.sync_history[node_id][nonce] = operation_value

    def handle_msg(self, msg: Msg, ip: str) -> None:
        if ip not in self.sync_history:
            self.sync_history[ip] = {}

        if msg.__getitem__("msg_type") == MSG_VARIABLE_UPDATE:
            operation_value = msg.__getitem__("operation")
            nonce = msg.__getitem__("nonce")
            self._handle_variable_update(operation_value, nonce, ip)

        if msg.__getitem__("msg_type") == MSG_SYNC_DATA:
            history = msg.convert_dict_to_dict(msg.__getitem__("history"))
            previous_value = msg.__getitem__("previous_value")
            self._handle_sync_data(ip, previous_value, history)

    def _handle_variable_update(self, operation_value: int, nonce: int, node_id: str):
        self._add_to_sync_history(node_id, nonce, operation_value)
        self.value += operation_value

    def _handle_sync_data(self, node_id: str, previous_value: int, history: HistoryObject):
        self.before_sync_value = previous_value
        self.sync_history[node_id] = history
        self._sync_with_history()

    def _sync_with_history(self):
        expected_value = self.before_sync_value

        for key in self.self_history:
            expected_value += self.self_history[key]

        for node in self.sync_history:
            for key in self.sync_history[node]:
                expected_value += self.sync_history[node][key]

        if self.value != expected_value:
            print(f"{self.name} ==> current: {self.value} - expected: {expected_value}")
            self.value = expected_value

    def _get_nonce_values(self, nonce_list: list[int]) -> dict[int, int]:
        nonce_values: dict[int, int] = {}
        for nonce_index in nonce_list:
            nonce_values[nonce_index] = self.self_history[nonce_index]

        return nonce_values

    def get_missing_nonces(self) -> dict[str, list[int]]:
        missing_list: dict[str, list[int]] = {}

        for node_id in self.sync_history:
            node_history = self.sync_history[node_id]
            if len(node_history) > 0:
                highest_index = int(max(node_history.keys()))

                for i in range(highest_index):
                    if i not in node_history:
                        if node_id not in missing_list:
                            missing_list[node_id] = []

                        missing_list[node_id].append(i)

        return missing_list
