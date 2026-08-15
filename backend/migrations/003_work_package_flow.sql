CREATE TABLE IF NOT EXISTS work_packages (
  id VARCHAR(80) PRIMARY KEY, project_id VARCHAR(80) NOT NULL, work_type VARCHAR(40) NOT NULL,
  zone_id VARCHAR(80) NOT NULL, title VARCHAR(160) NOT NULL, description TEXT,
  target_json JSON NOT NULL, constraints_json JSON NOT NULL,
  completion_criteria_json JSON NOT NULL, required_results_json JSON NOT NULL,
  status VARCHAR(24) NOT NULL, predecessor_wp_id VARCHAR(80) REFERENCES work_packages(id),
  successor_wp_id VARCHAR(80) REFERENCES work_packages(id), parent_wp_id VARCHAR(80) REFERENCES work_packages(id),
  release_gate VARCHAR(16) NOT NULL, rework_reason TEXT, failed_criteria_json JSON NOT NULL,
  target_area_json JSON NOT NULL, created_by VARCHAR(80), created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_work_packages_project ON work_packages(project_id);
CREATE INDEX IF NOT EXISTS ix_work_packages_status ON work_packages(status);
CREATE TABLE IF NOT EXISTS work_package_execution_links (
  id VARCHAR(36) PRIMARY KEY, work_package_id VARCHAR(80) NOT NULL REFERENCES work_packages(id) ON DELETE CASCADE,
  instruction_id VARCHAR(36) NOT NULL REFERENCES work_instructions(id) ON DELETE CASCADE,
  execution_commit_id VARCHAR(36) REFERENCES execution_commits(id) ON DELETE SET NULL,
  created_at DATETIME NOT NULL, UNIQUE(work_package_id, instruction_id)
);
CREATE TABLE IF NOT EXISTS work_package_evaluations (
  id VARCHAR(36) PRIMARY KEY, work_package_id VARCHAR(80) NOT NULL REFERENCES work_packages(id) ON DELETE CASCADE,
  progress_json JSON NOT NULL, overall VARCHAR(16) NOT NULL, criteria_json JSON NOT NULL,
  recommended_action VARCHAR(24) NOT NULL, created_at DATETIME NOT NULL
);
CREATE TABLE IF NOT EXISTS version_events (
  id VARCHAR(36) PRIMARY KEY, work_package_id VARCHAR(80) NOT NULL REFERENCES work_packages(id) ON DELETE CASCADE,
  event_type VARCHAR(40) NOT NULL, from_status VARCHAR(24), to_status VARCHAR(24), actor VARCHAR(80),
  reason TEXT, reference_id VARCHAR(100), created_at DATETIME NOT NULL
);
