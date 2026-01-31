#!/usr/bin/env python3
import json, datetime, pathlib, getpass, socket, ctypes, ctypes.wintypes, time, os, sys, select, subprocess

LOG   = pathlib.Path("canary.log")
BAIT  = pathlib.Path("Canary").resolve()

# ---------- cross-platform helpers ----------
def user():
    return getpass.getuser()

def hostname():
    return socket.gethostname()

def alert(bait_file, event):
    payload = {
        "time": datetime.datetime.now().isoformat(timespec='seconds'),
        "user": user(),
        "hostname": hostname(),
        "process_name": proc_name(),
        "process_exe": proc_exe(),
        "bait_file": str(bait_file),
        "event": event
    }
    # 1. log
    with LOG.open("a") as f:
        json.dump(payload, f)
        f.write("\n")
    # 2. voice (your Elara Kokoro TTS - calling via python for portability)
    try:
        # Security: Use subprocess.run with a list of arguments instead of os.system
        # to prevent potential command injection.
        subprocess.run(
            [sys.executable, "elara_tts.py", f"Canary tripped on {event}"],
            capture_output=True,
            text=True,
            timeout=10
        )
    except Exception as e:
        print(f"[-] TTS failed: {e}")
        
    print("[ALERT]", payload)

# ---------- process info ----------
def proc_name():
    if sys.platform == "win32":
        try:
            pid = ctypes.windll.kernel32.GetCurrentProcessId()
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid) # PROCESS_QUERY_LIMITED_INFORMATION
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.psapi.GetModuleFileNameExW(h, None, buf, 260)
            return pathlib.Path(buf.value).name
        except:
            return "unknown"
    else:
        try:
            return pathlib.Path("/proc/self/exe").readlink().name
        except:
            return "unknown"

def proc_exe():
    if sys.platform == "win32":
        try:
             # Re-using logic for simplicity
            pid = ctypes.windll.kernel32.GetCurrentProcessId()
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid) 
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.psapi.GetModuleFileNameExW(h, None, buf, 260)
            return buf.value
        except:
            return "unknown"
    else:
        try:
            return str(pathlib.Path("/proc/self/exe").readlink())
        except:
             return "unknown"

# ---------- Windows watcher ----------
def watch_win():
    FILE_LIST_DIRECTORY = 0x0001
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002 
    FILE_SHARE_DELETE = 0x00000004
    OPEN_EXISTING = 3
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000

    handle = ctypes.windll.kernel32.CreateFileW(
        str(BAIT), 
        FILE_LIST_DIRECTORY,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, 
        None, 
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS, 
        None
    )
    
    if handle == -1:
        raise RuntimeError(f"CreateFile failed: {ctypes.GetLastError()}")

    buf = ctypes.create_string_buffer(1024)
    print(f"[*] Started watching {BAIT}")
    
    while True:
        bytes_returned = ctypes.wintypes.DWORD()
        # *** 500 ms timeout to check for KeyboardInterrupt ***
        # WaitForSingleObject returns 0 (WAIT_OBJECT_0) if signaled
        if ctypes.windll.kernel32.WaitForSingleObject(handle, 500) == 0:
            ctypes.windll.kernel32.ReadDirectoryChangesW(
                handle, 
                buf, 
                len(buf), 
                True, # Watch subtree
                0x00000001 | 0x00000002 | 0x00000010 | 0x00000020,  # FILE_NOTIFY_CHANGE_FILE_NAME | DIR_NAME | LAST_WRITE | LAST_ACCESS
                ctypes.byref(bytes_returned), 
                None, 
                None
            )
            # crude: any change = trip
            alert("Canary/", "READ/WRITE/ACCESS")
            time.sleep(0.1)

# ---------- Linux/Mac watcher ----------
def watch_posix():
    try:
        libc = ctypes.CDLL("libc.so.6")
    except:
        try:
             libc = ctypes.CDLL(None) # fallback
        except:
            print("[-] Could not load libc")
            return

    inotify_init = libc.inotify_init
    inotify_add_watch = libc.inotify_add_watch
    inotify_init.restype = ctypes.c_int
    inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
    
    # inotify constants
    IN_ACCESS = 0x00000001
    IN_MODIFY = 0x00000002
    IN_OPEN   = 0x00000020
    
    fd = inotify_init()
    if fd < 0:
        raise RuntimeError("inotify_init failed")
        
    wd = inotify_add_watch(fd, str(BAIT).encode(), IN_ACCESS | IN_MODIFY | IN_OPEN)
    if wd < 0:
        raise RuntimeError("inotify_add_watch failed")

    print(f"[*] Started watching {BAIT} (inotify)")
    
    poll = select.poll()
    poll.register(fd, select.POLLIN)
    
    while True:
        # *** 500 ms timeout ***
        for (fd_, mask) in poll.poll(500):
            if mask & select.POLLIN:
                os.read(fd, 1024)
                alert("Canary/", "READ/WRITE/ACCESS")

# ---------- main ----------
def main():
    if not BAIT.exists():
        print("[-] Canary directory not found. Run bait_gen.py first.")
        return
    print("[*] Canary watching", BAIT)
    print("[*] Press Ctrl+C to stop")
    
    if sys.platform == "win32":
        watch_win()
    else:
        watch_posix()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[+] Canary stopped")
