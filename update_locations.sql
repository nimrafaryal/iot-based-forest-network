-- Run this in pgAdmin's Query Tool on the forestmonitering database
-- Sets real GPS coordinates for Node 1 and Node 2 (Taxila, Pakistan area)

UPDATE sensor_nodes
SET latitude = 33.7445, longitude = 72.7770
WHERE node_id = 1;

UPDATE sensor_nodes
SET latitude = 33.7460, longitude = 72.7790
WHERE node_id = 2;
