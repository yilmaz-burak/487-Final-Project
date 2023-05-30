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
from NetworkManager import NetworkManager, Msg
from CRDT import CRDT
from threading import Thread

variable_name_to_object: dict[str, CRDT] = {}
current_status = "work"

# TODO: we might need some locking mechanism


def handle_user_input(network_manager: NetworkManager):
    global current_status
    global variable_name_to_object
    while True:
        user_input = input()
        operation_value, variable_name = user_input.split()  # TODO: add error handling

        if variable_name not in variable_name_to_object:
            print(f"{variable_name} not found. Generating new variable with value 0")
            variable_name_to_object[variable_name] = CRDT()

        crdt = variable_name_to_object[variable_name]

        if operation_value == "get":
            print(f"value for {variable_name}: {crdt.get_value()}\n")
            continue
        elif operation_value == "before":
            print(f"previous value of {variable_name}: {crdt.get_before_sync_value()}\n")
            continue
        elif operation_value == "history":
            print(f"{variable_name} - self history: : {crdt.get_self_history()}")
            print(f"{variable_name} - history: : {crdt.get_sync_history()}\n")
            continue
        elif operation_value == "sync":
            print("This is not a valid user command. Just to make testing easier.")
            # TODO: implement sync in manual fashion first
            # current_status = "sync"
            # network_manager.broadcast_threaded(Msg().init_start_sync())


        operation_value = int(operation_value)  # TODO: error handling
        crdt.operate(operation_value)

        # TODO: Broadcast the operation done on the variable
        network_manager.broadcast_threaded(Msg().init_variable_update(variable_name, operation_value, crdt.current_nonce))


def crdt_handler(msg: Msg, ip: str):
    # TODO: We should call this from network_handler. Assuming all ips this function is called with are whitelisted.
    # if ip not in variable_name_to_object:
    #     print(f"node_id with ip: {ip} is not known.")
    #     return

    msg_type = msg.__getitem__("msg_type")  # TODO: this should be handled in network_handler function
    if msg_type == MSG_VARIABLE_UPDATE or msg_type == MSG_SYNC_DATA:
        variable_name = msg.__getitem__("variable_name")

        if variable_name not in variable_name_to_object:
            print(f"variable_name: {variable_name} does not exist on this node")
            variable_name_to_object[variable_name] = CRDT()
            # TODO: handle this case. Create a new crdt object and sync by maybe asking for whole history...

        crdt = variable_name_to_object[variable_name]
        crdt.handle_msg(msg, ip)


def network_handler(msg: Msg, ip: str, network_manager: NetworkManager):
    # TODO: add global for variable_name_to_object?

    msg_type = msg.__getitem__("msg_type")

    if msg_type == MSG_HELLO:
        status = msg.__getitem__("status")
        ip_from_message = msg.__getitem__("ip")
        print(f"ip is found as {ip}, {ip_from_message} with status: {status}")
        for variable in variable_name_to_object:
            crdt = variable_name_to_object[variable]
            network_manager.send_threaded(
                Msg().init_sync_data(variable, crdt.get_before_sync_value(), crdt.get_self_history()),
                ip,
            )

    if msg_type == MSG_SYNC_DATA:
        print("HERE, CRDT Handles...")


if __name__ == "__main__":
    # TODO: ask to join the network and try to sync
    network_manager = NetworkManager(12345)
    network_manager.listen_tcp_threaded(network_handler, crdt_handler, network_manager)
    network_manager.listen_udp_threaded(network_handler, crdt_handler, network_manager)
    network_manager.broadcast_threaded(Msg().init_hello(network_manager.ip, "work"))

    thread = Thread(target=handle_user_input, args=(network_manager,))
    thread.start()


# Q: Instead of giving crdt_handler as a distinct function, maybe call from network handler, depending on message type?
