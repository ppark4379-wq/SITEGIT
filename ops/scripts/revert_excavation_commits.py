"""Safely revert explicitly selected approved excavation commits.

The script creates a consistent SQLite backup before changing any row and
records one audit entry per reverted commit. It never deletes commit history.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid


def main() -> None:
    """Preview or apply a narrowly scoped excavation-commit recovery."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--commit-id", action="append", required=True, dest="commit_ids")
    parser.add_argument("--apply", action="store_true", help="Create backup and apply recovery")
    args = parser.parse_args()

    database = args.database.resolve()
    if not database.is_file():
        raise SystemExit(f"Database not found: {database}")

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in args.commit_ids)
    rows = connection.execute(
        f"""
        SELECT c.id, c.review_status, c.result,
               i.id AS instruction_id, i.status AS instruction_status
        FROM execution_commits AS c
        JOIN work_instructions AS i ON i.id = c.instruction_id
        WHERE c.id IN ({placeholders})
        """,
        args.commit_ids,
    ).fetchall()
    found = {row["id"] for row in rows}
    missing = sorted(set(args.commit_ids) - found)
    if missing:
        connection.close()
        raise SystemExit(f"Commit not found: {', '.join(missing)}")

    print("Recovery targets:")
    for row in rows:
        result = json.loads(row["result"] or "{}")
        size = result.get("target_bounds_size") or {}
        print(
            f"  {row['id']} | {result.get('target_prim_path')} | "
            f"{float(size.get('x', 0)):.1f} x {float(size.get('y', 0)):.1f} m | "
            f"{row['review_status']}"
        )
    if not args.apply:
        connection.close()
        print("Dry run only. Add --apply to create a backup and recover these commits.")
        return

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = database.with_name(f"{database.stem}.before-excavation-revert-{timestamp}.db")
    backup_connection = sqlite3.connect(backup)
    try:
        connection.backup(backup_connection)
    finally:
        backup_connection.close()

    now = datetime.now(timezone.utc).isoformat(sep=" ")
    note = (
        "Automatic recovery: approval reverted because the selected Prim was an "
        "oversized site mesh, not an independent excavation target."
    )
    reverted_count = 0
    with connection:
        for row in rows:
            if row["review_status"] != "approved":
                continue
            cursor = connection.execute(
                """
                UPDATE execution_commits
                SET review_status = 'reverted', review_note = ?
                WHERE id = ? AND review_status = 'approved'
                """,
                (note, row["id"]),
            )
            if cursor.rowcount != 1:
                continue
            reverted_count += 1
            connection.execute(
                "UPDATE work_instructions SET status = 'rejected', updated_at = ? WHERE id = ?",
                (now, row["instruction_id"]),
            )
            connection.execute(
                """
                INSERT INTO audit_logs
                    (id, user_id, username, action, target_type, target_id, details, created_at)
                VALUES (?, NULL, 'codex-recovery', 'ISAAC_RESULT_REVERTED',
                        'execution_commit', ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    row["id"],
                    json.dumps(
                        {
                            "instruction_id": row["instruction_id"],
                            "reason": note,
                            "backup": str(backup),
                        },
                        ensure_ascii=False,
                    ),
                    now,
                ),
            )
    connection.close()
    print(f"Backup: {backup}")
    print(f"Recovered commits: {reverted_count}")


if __name__ == "__main__":
    main()
