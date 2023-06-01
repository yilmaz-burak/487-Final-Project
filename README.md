# 487-Final-Project
We will implement a CRDT for a simple integer. Nodes will operate on their local data, and sync continuously to reach to the correct global value. Once in a while, they will have a full-sync mode,
where they will all stop the operations on the integer until all the nodes are synced.

## Data Types
```
[{node_id, nonce, <value>}] --> list of operations that is done to the variable
```

## Synchronization Logic
Every `X time unit`, we will freeze operations for some `Y time unit` to fully synchronize the nodes and flush the operations list, in order to keep the list small.

## Existing Nodes Sync With Each Other
They will sync via exchanging their operations lists, and then keeping track of missing `nonce` values for each of the `node_id`s, by communicating with relevant node.

## New Node Joins the Network
They can sync with any node, then, they will just ask for missing values by checking the `node_id - nonce` values it has in the operations list.

## When Data Is Changed
Any node that does an operation on the variable shall broadcast the operation for less overhead later when full-sync starts.

## Node Modes
We have 3 modes: `Work`, `Sync` and `Ready`
- `Sync` mode will only sync with the nodes with `node_id`s that it knows about.
- If a new one joins, they will make them join the syncing process.
- After all of the nodes have synchronized with each other, they will update their statuses as `Ready`.
- Once all the nodes are in `Ready` state, they will exchange their current values with each other.
- If/when they have a consensus with each other, they will reset their history with the common variable value as their before sync values.
- After that, they will update their statuses as `Work` and accept further operations.

`Sync` --> `Work` mode only happens if all the nodes have acknowledged each others full sync messages

## Sample User Inputs
```
<create - variables - get - history - before - sync - peers> <variable_name> --> get info related to <variable_name>
or
<+ or - integer OR 'populate'> <variable name> --> operate on <variable_name>
```

## Challenges and Shortcomings
### Full-Sync Scheduling
- Full sync scheduling between all nodes can become tricky, since some of them might trigger sync requests even right after the sync has just finished. There are potential solutions to this, such as a distributed lock, however, for simplicity and demonstration puposes, we have left this as a manual process.

### Edge Cases with Parallel Execution in Async Environment
- There can exist many edge cases that we haven't even thought of. Since we are using multiple threads, from time to time, we encountered some stability issues. Even though we have fixed most of them, we would need some deduplication or some sort of messaging queues to enable even better consisteny and reliability.

### Initial Entrance to Cluster
- A new node joining could also become problematic in certain cases, since we don't hold distributed locks. They could cause some data corruption. So far, we haven't encountered this.

### Overall Python Stuff
- There existed some cases, where some data types were not casted to intended ones. For examples, simple integers could be parsed from the json, however, once we dealt with dictionaries, integer values were parsed as strings and so on. This led to some high debugging effort.


## Run on a Single Machine
```
docker-compose up -d
```
This will create 2 containers running the same application. Then,
```
docker ps --> see the containers
on terminal 1 --> docker attach <container-id-1>
on terminal 2 --> docker attach <container-id-2>
```
These commands will bind your io to the one in the container.

To test different exiting / rejoining, `ctrl+c` from one of the terminals, and run 
```
docker-compose up -d
```
from the terminal that you killed the process. This way, it will be restarted, but the other one won't be affected. Then, attach your terminal by running 
```
on terminal --> docker attach <container-id>
```
again.


