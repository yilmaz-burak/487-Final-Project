# overall network stuff - furkan

# sending TCP message to specific address
def send_to_ip(message, ip):
    print(message, ip)

# broadcast message to everyone in the network:
def broadcast_message(message):
    print(message)

# scan the network to discover new nodes, if hello message are not received
def scan_network(): # returns list of nodes available
    print("available nodes")

# Ask all nodes if the sync is finished
# if all known nodes give the true flag, then this will return true
def is_sync_finished():
    print("is_sync_finished called")


# all nodes freeze the operations when they all start the sync after last sync is finished and 60s have passed.
def start_sync():
    print("initiating synchronization")

def freeze_operations():
    print("freezing operations")

def unfreeze_operations():
    print("unfreezing operations")

def exchange_variable_change_history(variable_history):
    print(variable_history) # this is the [{node_id, nonce, <value>}] --> list of operations that is done to the variable





# could even broadcast the finishing of the sync
def set_sync_finished():
    print("sync is finished by this node.") 

def handle_operation(message):
    print(message)

def operate_on(variable, number):
    print(variable, number)

def ask_missing_value(node_id, nonce):
    print(node_id, nonce)

def change_node_mode(mode):
    print(mode)






# Needs another meeting - sync

# handling the TCP message from specific address
def handle_message(message, from_ip):
    print(message, from_ip)
    # message_object = Message(message) --> Message class will handle the message
