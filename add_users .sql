-- Run this in pgAdmin's Query Tool on the forestmonitering database
-- Creates one Admin account and one regular User account for login testing.
-- NOTE: passwords are stored in plain text here for simplicity/demo purposes only.
-- For a real production system, passwords must be hashed (e.g. bcrypt) before storing.

INSERT INTO users (name, email, password, role) VALUES
    ('Areeba Shahid', 'admin@forest.com', 'admin123', 'Admin'),
    ('Forest Officer', 'officer@forest.com', 'user123', 'User');
