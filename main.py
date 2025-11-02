#!/usr/bin/env python3
"""
Listens for new files in ~/Downloads and renames them
based on the current Safari page URL.
Handles Safari's .download temporary files gracefully.
"""

import time
import subprocess
import re
import shutil
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


# === CONFIGURATION ===
DOWNLOADS = Path.home() / "Downloads"
DEST_DIR = DOWNLOADS / "safari_renamed"
WAIT_TIME = 2  # seconds to wait after file detected before renaming
DEST_DIR.mkdir(exist_ok=True)


# === HELPER FUNCTIONS ===
def get_safari_url() -> str:
    """Get the current Safari tab's URL via AppleScript."""
    script = '''
    tell application "Safari"
        if not (exists document 1) then
            return ""
        end if
        return URL of current tab of front window
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.stdout.strip()


def sanitize_filename(url: str) -> str:
    """Convert a URL into a filesystem-safe filename."""
    if not url:
        return "unknown_source"
    filename = re.sub(r'[<>:"/\\|?*]+', "_", url)
    return filename[:200]


def wait_for_download_complete(path: Path, timeout: int = 60) -> Path:
    """
    Waits until a Safari .download temporary file finishes downloading,
    then returns the final file path.
    """
    if path.suffix != ".download":
        return path

    print(f"⏳ Waiting for {path.name} to finish downloading...")
    start_time = time.time()

    # Wait for .download file to disappear and final file to appear
    final = Path(str(path)[:-9])  # remove ".download"

    while time.time() - start_time < timeout:
        if not path.exists() and final.exists():
            print(f"✅ Download complete: {final.name}")
            return final
        time.sleep(1)

    print(f"⚠️ Timed out waiting for {path.name} to finish")
    return path


# === EVENT HANDLER ===
class DownloadHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        self.process_event(Path(event.src_path))

    def on_moved(self, event):
        """Handle file renames (Safari .download → real file)."""
        if event.is_directory:
            return
        self.process_event(Path(event.dest_path))

    def process_event(self, path: Path):
        """Called for both created and moved events."""
        if not path.exists():
            return

        print(f"📥 New or updated file detected: {path.name}")
        path = wait_for_download_complete(path)

        time.sleep(WAIT_TIME)
        safari_url = get_safari_url()
        safe_name = sanitize_filename(safari_url)
        new_path = DEST_DIR / f"{safe_name}{path.suffix}"

        try:
            shutil.move(str(path), str(new_path))
            print(f"✅ Renamed & moved: {new_path.name}")
        except Exception as e:
            print(f"⚠️ Could not rename {path.name}: {e}")


# === MAIN LOOP ===
if __name__ == "__main__":
    print(f"👂 Listening for new files in {DOWNLOADS}...")
    handler = DownloadHandler()
    observer = Observer()
    observer.schedule(handler, str(DOWNLOADS), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("🛑 Stopped listener.")
    observer.join()
