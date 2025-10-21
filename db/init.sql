-- Schema
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS todos (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  is_done BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Seed data (demo only; do not use plaintext passwords in production)
INSERT INTO users (email, password)
VALUES ('demo@example.com', 'demo123')
ON CONFLICT (email) DO NOTHING;

INSERT INTO todos (user_id, title, is_done)
VALUES 
  ((SELECT id FROM users WHERE email = 'demo@example.com'), 'Buy groceries', FALSE),
  ((SELECT id FROM users WHERE email = 'demo@example.com'), 'Read a book', TRUE)
ON CONFLICT DO NOTHING;


