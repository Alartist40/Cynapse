#!/usr/bin/env python3
"""
Canary Token v2.0 - High Performance Intrusion Detector
Optimized: Async monitoring, parallel alerting, cross-platform hardening
"""

import asyncio
import json
import datetime
import pathlib
import getpass
import socket
import ctypes
import os
import sys
import select
import subprocess
from typing import Optional

# Cynapse integration
BASE_DIR = pathlib.Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(BASE_DIR))
try:
    from cynapse import AuditLogger, LOG_FILE
except ImportError:
    class AuditLogger:
        def log(self, event, data): pass
    LOG_FILE = pathlib.Path("audit.log")

LOG = pathlib.Path("canary.log")
BAIT = pathlib.Path("Canary").resolve()

class CanaryWatcher:
    def __init__(self, hub=None):
        self.hub = hub
        self.audit = hub.logger if hub else AuditLogger(LOG_FILE)
        self.running = False

    async def start(self):
        if not BAIT.exists():
            print("[-] Canary directory missing. Run bait_gen.py first.")
            return

        self.running = True
        print(f"[*] Canary v2.0: Watching {BAIT}...")
        
        if sys.platform == "win32":
            await self._watch_win()
        else:
            await self._watch_posix()

    async def _alert(self, bait_file: str, event: str):
        """Async parallel alerting system"""
        timestamp = datetime.datetime.now().isoformat(timespec='seconds')
        payload = {
            "time": timestamp,
            "user": getpass.getuser(),
            "hostname": socket.gethostname(),
            "bait_file": str(bait_file),
            "event": event
        }

        # 1. Log locally
        def write_log():
            with LOG.open("a") as f:
                json.dump(payload, f)
                f.write("\n")
        await asyncio.to_thread(write_log)

        # 2. Hub Audit
        self.audit.log("canary_tripped", payload)

        # 3. Voice Notification (Parallel)
        async def trigger_voice():
            try:
                await asyncio.create_subprocess_exec(
                    sys.executable, "elara_tts.py", f"Canary tripped on {event}",
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except: pass

        asyncio.create_task(trigger_voice())
        print(f"\n[!] ALERT: {event} on {bait_file}")

    async def _watch_win(self):
        # Implementation using asyncio.to_thread for the blocking ReadDirectoryChangesW
        import ctypes.wintypes
        FILE_LIST_DIRECTORY = 0x0001
        FILE_SHARE_READ = 1; FILE_SHARE_WRITE = 2; FILE_SHARE_DELETE = 4
        OPEN_EXISTING = 3; FILE_FLAG_BACKUP_SEMANTICS = 0x02000000

        handle = ctypes.windll.kernel32.CreateFileW(
            str(BAIT), FILE_LIST_DIRECTORY,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None
        )

        if handle == -1: return

        buf = ctypes.create_string_buffer(1024)
        while self.running:
            def check_changes():
                bytes_ret = ctypes.wintypes.DWORD()
                if ctypes.windll.kernel32.WaitForSingleObject(handle, 500) == 0:
                    ctypes.windll.kernel32.ReadDirectoryChangesW(
                        handle, buf, len(buf), True,
                        0x1 | 0x2 | 0x10 | 0x20, ctypes.byref(bytes_ret), None, None
                    )
                    return True
                return False

            if await asyncio.to_thread(check_changes):
                await self._alert("Canary/", "READ/WRITE/ACCESS")
            await asyncio.sleep(0.1)

    async def _watch_posix(self):
        try:
            libc = ctypes.CDLL(None)
            inotify_init = libc.inotify_init
            inotify_add_watch = libc.inotify_add_watch

            fd = inotify_init()
            if fd < 0: return

            # IN_ACCESS | IN_MODIFY | IN_OPEN
            inotify_add_watch(fd, str(BAIT).encode(), 0x00000001 | 0x00000002 | 0x00000020)

            poll = select.poll()
            poll.register(fd, select.POLLIN)

            while self.running:
                # Use to_thread for the blocking poll
                events = await asyncio.to_thread(poll.poll, 500)
                for fd_, mask in events:
                    if mask & select.POLLIN:
                        os.read(fd, 1024)
                        await self._alert("Canary/", "READ/WRITE/ACCESS")
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Posix watch error: {e}")

async def main():
    watcher = CanaryWatcher()
    try:
        await watcher.start()
    except KeyboardInterrupt:
        watcher.running = False
        print("\n[+] Canary stopped")

if __name__ == "__main__":
    asyncio.run(main())
