-- Reference-only schema for the Isaac closed loop.
-- Runtime creates the same tables through SQLAlchemy (Base.metadata.create_all).
-- Replace this folder with Alembic migrations when normalized domain tables land.
--
-- 웹 지시 → Isaac 실행 → Commit → 관리자 승인 → 맵 반영.
-- 맵 오브젝트 테이블은 일부러 두지 않습니다. 승인된 Commit이 곧 맵 오브젝트이며,
-- 승인을 되돌리면 맵에서도 즉시 사라집니다.

CREATE TABLE IF NOT EXISTS work_instructions (
  id VARCHAR(36) PRIMARY KEY,
  project_id VARCHAR(80) NOT NULL,
  kind VARCHAR(40) NOT NULL,
  params JSON NOT NULL,
  status VARCHAR(20) NOT NULL,   -- pending | dispatched | committed | approved | rejected
  note TEXT,
  created_by VARCHAR(36),
  created_by_username VARCHAR(80),
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  dispatched_at DATETIME
);
CREATE INDEX IF NOT EXISTS ix_work_instructions_project ON work_instructions (project_id);
CREATE INDEX IF NOT EXISTS ix_work_instructions_status ON work_instructions (status);
CREATE INDEX IF NOT EXISTS ix_work_instructions_created ON work_instructions (created_at);

CREATE TABLE IF NOT EXISTS execution_commits (
  id VARCHAR(36) PRIMARY KEY,
  instruction_id VARCHAR(36) NOT NULL REFERENCES work_instructions (id) ON DELETE CASCADE,
  attempt INTEGER NOT NULL,
  status VARCHAR(20) NOT NULL,          -- succeeded | failed
  result JSON NOT NULL,
  evidence JSON NOT NULL,               -- LiDAR/카메라/IMU는 storage_keys로 SSD를 가리킵니다
  adapter VARCHAR(60) NOT NULL,
  committed_by VARCHAR(80),
  committed_at DATETIME NOT NULL,
  review_status VARCHAR(20) NOT NULL,   -- pending | approved | rejected
  reviewed_by VARCHAR(80),
  reviewed_at DATETIME,
  review_note TEXT
);
CREATE INDEX IF NOT EXISTS ix_execution_commits_instruction ON execution_commits (instruction_id);
CREATE INDEX IF NOT EXISTS ix_execution_commits_committed ON execution_commits (committed_at);
CREATE INDEX IF NOT EXISTS ix_execution_commits_review ON execution_commits (review_status, committed_at);
