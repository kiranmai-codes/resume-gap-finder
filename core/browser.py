"""Shared Chrome lifecycle. Auto-restarts if Chrome dies."""
import asyncio
import subprocess
from pathlib import Path
from playwright.async_api import async_playwright


class BrowserManager:
    def __init__(self, chrome_path: str, profile_dir: str, cdp_port: int,
                 notifier=None):
        self.chrome_path = chrome_path
        self.profile_dir = profile_dir
        self.cdp_port = cdp_port
        self.notifier = notifier
        self.chrome_proc = None
        self.browser = None
        self.pw = None

    async def start(self):
        self.pw = await async_playwright().start()
        await self._launch()

    async def _launch(self):
        Path(self.profile_dir).mkdir(parents=True, exist_ok=True)
        if not Path(self.chrome_path).exists():
            raise RuntimeError(f"Chrome binary not found: {self.chrome_path}")
        self.chrome_proc = subprocess.Popen([
            self.chrome_path,
            f"--remote-debugging-port={self.cdp_port}",
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run", "--no-default-browser-check",
            "--disable-popup-blocking", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await asyncio.sleep(2)
        for _ in range(30):
            try:
                self.browser = await self.pw.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{self.cdp_port}")
                return
            except Exception:
                await asyncio.sleep(1)
        raise RuntimeError("Failed to connect to Chrome over CDP")

    def is_alive(self) -> bool:
        return (self.browser is not None
                and self.browser.is_connected()
                and self.chrome_proc is not None
                and self.chrome_proc.poll() is None)

    async def ensure_alive(self):
        """Restart Chrome if it died mid-run."""
        if not self.is_alive():
            if self.notifier:
                self.notifier.warn("Chrome died mid-run — restarting")
            await self.stop()
            await self.start()

    async def get_page(self):
        await self.ensure_alive()
        ctx = self.browser.contexts[0] if self.browser.contexts \
              else await self.browser.new_context()
        return ctx.pages[0] if ctx.pages else await ctx.new_page()

    async def stop(self):
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        try:
            if self.chrome_proc:
                self.chrome_proc.terminate()
                self.chrome_proc.wait(timeout=5)
        except Exception:
            pass
        try:
            if self.pw:
                await self.pw.stop()
        except Exception:
            pass
