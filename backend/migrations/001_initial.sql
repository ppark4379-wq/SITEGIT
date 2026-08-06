-- Reference-only initial schema. Runtime currently creates the same tables through SQLAlchemy.
-- Replace this folder with Alembic migrations when normalized domain tables are introduced.
CREATE TABLE IF NOT EXISTS users (
  id VARCHAR(36) PRIMARY KEY,
  username VARCHAR(80) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  full_name VARCHAR(120) NOT NULL,
  role VARCHAR(30) NOT NULL,
  is_active BOOLEAN NOT NULL,
  created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS project_states (
  project_id VARCHAR(80) PRIMARY KEY,
  payload JSON NOT NULL,
  revision INTEGER NOT NULL,
  updated_by VARCHAR(36),
  updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36),
  username VARCHAR(80),
  action VARCHAR(100) NOT NULL,
  target_type VARCHAR(80) NOT NULL,
  target_id VARCHAR(100) NOT NULL,
  details JSON NOT NULL,
  created_at DATETIME NOT NULL
);
