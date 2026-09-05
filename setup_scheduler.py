"""
Mahad Impex Email Marketing System — Windows Task Scheduler Setup
Creates a scheduled task to run the daily campaign automatically.
"""

import subprocess
import sys
import os
from pathlib import Path
from config import BASE_DIR


def create_scheduled_task():
    """
    Create a Windows Task Scheduler task that runs the campaign daily at 10 AM PKT.
    The task runs 'python main.py run' from the project directory.
    """
    python_path = sys.executable
    script_path = str(BASE_DIR / "main.py")
    working_dir = str(BASE_DIR)
    task_name = "MahadImpex_EmailCampaign"
    log_file = str(BASE_DIR / "data" / "logs" / "scheduler.log")

    # Build the command that Task Scheduler will execute
    # Redirects output to a log file for debugging
    action = (
        f'cmd /c ""{python_path}" "{script_path}" run '
        f'>> "{log_file}" 2>&1"'
    )

    # Create the scheduled task using schtasks
    # Runs daily at 10:00 AM
    cmd = [
        "schtasks", "/Create",
        "/TN", task_name,
        "/TR", action,
        "/SC", "DAILY",
        "/ST", "10:00",
        "/F",  # Force overwrite if exists
        "/RL", "HIGHEST",
        "/NP",  # No password prompt (runs whether logged in or not)
    ]

    print(f"\n{'='*55}")
    print(f"  Setting up Windows Task Scheduler")
    print(f"{'='*55}")
    print(f"\n  Task name:    {task_name}")
    print(f"  Schedule:     Daily at 10:00 AM")
    print(f"  Python:       {python_path}")
    print(f"  Script:       {script_path}")
    print(f"  Working dir:  {working_dir}")
    print(f"  Log file:     {log_file}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, shell=True
        )

        if result.returncode == 0:
            print(f"\n  ✓ Scheduled task created successfully!")
            print(f"\n  The system will now run automatically every day at 10:00 AM.")
            print(f"  No human intervention needed — it finds leads, writes emails,")
            print(f"  and sends them on autopilot.\n")
            print(f"  To verify: Open Task Scheduler > look for '{task_name}'")
            print(f"  To remove: schtasks /Delete /TN {task_name} /F")
            print(f"  To run now: schtasks /Run /TN {task_name}\n")
        else:
            print(f"\n  ✗ Failed to create scheduled task:")
            print(f"    {result.stderr.strip()}")
            print(f"\n  Try running this script as Administrator.\n")
            print(f"  Manual alternative:")
            print(f"    1. Open Task Scheduler (taskschd.msc)")
            print(f"    2. Create Basic Task > '{task_name}'")
            print(f"    3. Trigger: Daily at 10:00 AM")
            print(f"    4. Action: Start a Program")
            print(f"       Program: {python_path}")
            print(f'       Arguments: "{script_path}" run')
            print(f"       Start in: {working_dir}\n")

    except FileNotFoundError:
        print("\n  ✗ 'schtasks' command not found. Are you on Windows?\n")
    except Exception as e:
        print(f"\n  ✗ Error: {e}\n")


def remove_scheduled_task():
    """Remove the scheduled task."""
    task_name = "MahadImpex_EmailCampaign"
    try:
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            capture_output=True, text=True, shell=True
        )
        if result.returncode == 0:
            print(f"\n  ✓ Task '{task_name}' removed.\n")
        else:
            print(f"\n  ✗ {result.stderr.strip()}\n")
    except Exception as e:
        print(f"\n  ✗ Error: {e}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "remove":
        remove_scheduled_task()
    else:
        create_scheduled_task()
