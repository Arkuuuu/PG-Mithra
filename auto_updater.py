"""
Auto-Updater & Supervisor Daemon for 24/7 AWS EC2 Cloud Worker Nodes.

Monitors GitHub repository origin/main for new commits every 30 seconds.
When a new push occurs, automatically pulls updates and reloads main.py without interruption.
"""

import subprocess
import time
import sys
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (AutoUpdater) %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 30


def get_git_revision_hash(ref="HEAD") -> str:
    """Get exact git commit hash for a given ref."""
    try:
        res = subprocess.run(["git", "rev-parse", ref], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception as e:
        logger.warning(f"Failed to get git revision for {ref}: {e}")
        return ""


def pull_latest_code() -> bool:
    """Fetch and pull latest code changes from origin/main."""
    try:
        subprocess.run(["git", "fetch", "origin", "main"], check=True)
        res = subprocess.run(["git", "pull", "origin", "main"], capture_output=True, text=True, check=True)
        logger.info(f"Git Pull Output: {res.stdout.strip()}")
        return True
    except Exception as e:
        logger.error(f"Git pull failed: {e}")
        return False


def start_worker_process():
    """Launch main.py using current python executable."""
    python_bin = sys.executable
    cmd = [python_bin, "main.py"]
    logger.info(f"🚀 Launching Worker Process: {' '.join(cmd)}")
    return subprocess.Popen(cmd)


def main():
    logger.info("============================================================")
    logger.info("🤖 AWS EC2 24/7 Auto-Updater Supervisor Started")
    logger.info("============================================================")

    # Initial code sync
    pull_latest_code()
    current_commit = get_git_revision_hash("HEAD")
    logger.info(f"Current Running Commit Hash: {current_commit[:8]}")

    # Launch worker child process
    worker_proc = start_worker_process()

    try:
        while True:
            time.sleep(CHECK_INTERVAL_SECONDS)

            # Check if child process died unexpectedly
            poll_code = worker_proc.poll()
            if poll_code is not None:
                logger.warning(f"⚠️ Worker process exited unexpectedly with code {poll_code}. Auto-restarting worker...")
                worker_proc = start_worker_process()
                continue

            # Fetch remote git status
            try:
                subprocess.run(["git", "fetch", "origin", "main"], capture_output=True, check=True)
                remote_commit = get_git_revision_hash("origin/main")
                local_commit = get_git_revision_hash("HEAD")

                if remote_commit and remote_commit != local_commit:
                    logger.info(f"⚡ New code commit detected on GitHub!")
                    logger.info(f"   Local:  {local_commit[:8]}")
                    logger.info(f"   Remote: {remote_commit[:8]}")

                    # Terminate current worker process gracefully
                    logger.info(" Stopping existing worker process...")
                    worker_proc.terminate()
                    try:
                        worker_proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        logger.warning(" Worker process did not terminate in 10s, forcing kill...")
                        worker_proc.kill()

                    # Pull code updates
                    if pull_latest_code():
                        new_commit = get_git_revision_hash("HEAD")
                        logger.info(f"✅ Code updated successfully to commit {new_commit[:8]}. Relaunching worker...")
                    else:
                        logger.error("❌ Git pull failed. Restarting existing code...")

                    # Relaunch updated worker
                    worker_proc = start_worker_process()

            except Exception as e:
                logger.warning(f"Error checking git updates: {e}")

    except KeyboardInterrupt:
        logger.info("\n🛑 Auto-updater supervisor shutting down...")
        if worker_proc and worker_proc.poll() is None:
            worker_proc.terminate()
            worker_proc.wait()
        sys.exit(0)


if __name__ == "__main__":
    main()
