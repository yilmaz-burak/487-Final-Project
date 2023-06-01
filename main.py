from NetworkManager import NetworkManager, Msg
from CRDT import CRDT
from threading import Thread


def handle_user_input(network_manager: NetworkManager):
    global current_status
    global variable_name_to_object
    while True:
        user_input = input()
        try:
            operation_value, variable_name = user_input.split()
            thread = Thread(target=network_manager.handle_user_input, args=(operation_value, variable_name,))
            thread.start()
            
        except Exception as e:
            print(f"Exception occured: {e}")


if __name__ == "__main__":
    network_manager = NetworkManager(12345)
    network_manager.listen_tcp_threaded()
    network_manager.listen_udp_threaded()
    network_manager.schedule_sync_broadcast()
    Thread(target=network_manager.periodic_hello_broadcast, args=(0.1,)).start()
    Thread(target=network_manager.check_everything_is_ready).start()

    thread = Thread(target=handle_user_input, args=(network_manager,))
    thread.start()
