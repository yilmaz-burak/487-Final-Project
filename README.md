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
We have 2 modes: `Work` and `Sync`
`Sync` mode will only sync with the nodes with `node_id`s that it knows about. If a new one joins, they will make them wait until sync mode is over. Once the nodes are in `work` mode, they can again request a sync, which will happen and the node will enter the cluster.

`Sync` --> `Work` mode only happens if all the nodes have acknowledged each others full sync messages
 

