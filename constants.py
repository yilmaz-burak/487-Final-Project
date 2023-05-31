from enum import Enum

MSG_HELLO = "hello"
MSG_HELLO_RECEIVED = "hello_received"
MSG_VARIABLE_UPDATE = "variable_update"
MSG_START_SYNC = "start_sync"
MSG_STOP_SYNC = "stop_sync"
MSG_STATUS_REQUEST = "status_request"
MSG_STATUS = "status"
MSG_NONCE_REQUEST = "nonce_request"
MSG_NONCE_SEND = "nonce_send"
MSG_SYNC_DATA = "sync_data"

STATUS_WORK = "work"
STATUS_READY = "ready"
STATUS_SYNC = "sync"

LISTEN_BUFFER_SIZE = 4096
