"""File-based lock — prevents two scrapers running at once."""
import fcntl
from pathlib import Path


class ScraperLock:
    def __init__(self, path=".scraper.lock"):
        self.path = Path(path)
        self.fh = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "w")
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fh.write(str(__import__("os").getpid()))
            self.fh.flush()
            return True
        except BlockingIOError:
            self.fh.close()
            self.fh = None
            return False

    def release(self):
        if self.fh:
            try:
                fcntl.flock(self.fh, fcntl.LOCK_UN)
                self.fh.close()
            except Exception:
                pass
