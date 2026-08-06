"""Mock SiteGit adapter.

This is not an Isaac Sim integration. It proves the API contract by logging in,
loading the shared project state, updating one Work Package, and saving it back.
Replace the simulated loop with ROS 2 / Isaac Sim callbacks later.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))
API = os.getenv("SITEGIT_API_URL", "http://localhost:8000/api/v1")
PROJECT_ID = os.getenv("SITEGIT_PROJECT_ID", "SASANG-001")
USERNAME = os.getenv("SITEGIT_USERNAME", "manager")
PASSWORD = os.getenv("SITEGIT_PASSWORD", "")


def main() -> None:
    session = requests.Session()
    login = session.post(f"{API}/auth/login", json={"username": USERNAME, "password": PASSWORD}, timeout=10)
    login.raise_for_status()

    response = session.get(f"{API}/state/{PROJECT_ID}", timeout=10)
    response.raise_for_status()
    record = response.json()
    state = record["payload"]

    target = next(wp for wp in state["workPackages"] if wp["id"] == "WP-SASANG-B01")
    for progress in (50, 60, 70):
        target["status"] = "executing"
        target["raw"] = progress
        target["qualified"] = max(0, progress - 4)
        target["remaining"] = round(target["target"] * (100 - target["qualified"]) / 100)
        saved = session.put(
            f"{API}/state/{PROJECT_ID}",
            json={"payload": state, "revision": record["revision"], "source": "mock-isaac-adapter"},
            timeout=10,
        )
        saved.raise_for_status()
        record = saved.json()
        state = record["payload"]
        print(f"revision={record['revision']} raw={progress}%")
        time.sleep(2)


if __name__ == "__main__":
    main()
