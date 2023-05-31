from NetworkManager import NetworkManager, Msg
from CRDT import CRDT
from threading import Thread


def handle_user_input(network_manager: NetworkManager):
    global current_status
    global variable_name_to_object
    while True:
        user_input = input()
        try:
            operation_value, variable_name = user_input.split()  # TODO: add error handling
            thread = Thread(target=network_manager.handle_user_input, args=(operation_value, variable_name,))
            thread.start()
            
        except Exception as e:
            print(f"Exception occured: {e}")


if __name__ == "__main__":
    # TODO: ask to join the network and try to sync
    network_manager = NetworkManager(12345)
    network_manager.listen_tcp_threaded()
    network_manager.listen_udp_threaded()
    network_manager.schedule_sync_broadcast()
    #network_manager.broadcast_threaded(Msg().init_hello(network_manager.ip, network_manager.current_status))
    Thread(target=network_manager.periodic_hello_broadcast, args=(0.1,)).start()
    Thread(target=network_manager.check_everything_is_ready).start()

    # TODO: add a sync checker, which will start and/or listen for end of sync process between nodes
    # This will wait for all peers to be in sync mode. Then, all nonce values will be checked. This is done in network handlers, so no need for extra stuff
    # Continuously check other peers' statuses. If everyone is in ready status --> flush self_history and sync_history, then switch to working status

    thread = Thread(target=handle_user_input, args=(network_manager,))
    thread.start()

# TODO: keep state, whether the node is accepted to network or not.

# Q: Instead of giving crdt_handler as a distinct function, maybe call from network handler, depending on message type?

# TODO: self.peers should be thoroughly checked
# Implemented hello_received
# TODO: initial entrance to network OR network failure OR app crashed
# When new node joins, it sends a hello message start sync if other nodes are in work mode,
# starts full-sync if other nodes are in ready or sync mode
# TODO: full-sync mode-checker --> thread for infinite loop to continuously check states of other peers

