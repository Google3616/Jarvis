import os
import time
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PIL import Image
import pytesseract
from datetime import datetime

DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")


def normalize_screenshot_path(path):
    """Normalize a macOS screenshot filename: remove leading dot and weird spaces."""
    dirname, filename = os.path.split(path)

    # Replace narrow no-break space (U+202F) with normal space
    filename = filename.replace("\u202f", " ").replace("\u00a0", " ")

    # Remove leading dot
    if filename.startswith("."):
        filename = filename[1:]

    # If changed, rename the file
    clean_path = os.path.join(dirname, filename)
    if clean_path != path:
        try:
            os.rename(path, clean_path)
            print(f"Normalized filename: {os.path.basename(clean_path)}")
        except FileNotFoundError:
            print("File disappeared before renaming (macOS temp behavior). Skipping.")
    return clean_path


def extract_largest_text(image_path):
    """Extract the text with the largest font (bounding box height) from an image."""
    try:
        data = pytesseract.image_to_data(Image.open(image_path), output_type=pytesseract.Output.DICT)
        max_height = 0
        largest_text = None

        for i, text in enumerate(data["text"]):
            text = text.strip()
            if text:
                height = data["height"][i]
                if height > max_height:
                    max_height = height
                    largest_text = text

        if largest_text:
            largest_text = re.sub(r"[^A-Za-z0-9]+", "_", largest_text.strip())
            return largest_text
        return None
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None


class ScreenshotHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return

        path = event.src_path
        # Normalize the file name *before* OCR
        normalized_path = normalize_screenshot_path(path)

        filename = os.path.basename(normalized_path)
        if filename.lower().startswith("screenshot") and filename.lower().endswith((".png", ".jpg", ".jpeg")):
            print(f"Detected screenshot: {filename}")
            time.sleep(1)  # Wait for file to finish writing

            text = extract_largest_text(normalized_path)
            if text:
                date_str = datetime.now().strftime("%Y-%m-%d")
                ext = os.path.splitext(filename)[1]
                new_name = f"{text}_{date_str}{ext}"
                new_path = os.path.join(DESKTOP_PATH, new_name)
                os.rename(normalized_path, new_path)
                print(f"✅ Renamed to: {new_name}")
            else:
                print("No text found — keeping original name.")


if __name__ == "__main__":
    observer = Observer()
    handler = ScreenshotHandler()
    observer.schedule(handler, DESKTOP_PATH, recursive=False)
    observer.start()

    print("📸 Watching Desktop for new screenshots... (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
