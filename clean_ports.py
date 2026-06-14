import subprocess
import os
import sys

PORTS_TO_KILL = [8770, 8769, 8765]
CURRENT_PID = os.getpid()
PARENT_PID = os.getppid()

def kill_port_safely(pid_str):
    try:
        pid = int(pid_str)
    except ValueError:
        return
    
    if pid == CURRENT_PID:
        print(f"  [SKIP] PID {pid} is the current process (safe).")
        return
    if pid == PARENT_PID:
        print(f"  [SKIP] PID {pid} is the parent process (safe).")
        return
    if pid == 4:
        print(f"  [SKIP] PID {pid} is a critical system process (safe).")
        return

    print(f"  [KILL] Targeting PID {pid}...")
    try:
        result = subprocess.run(
            ['taskkill', '/F', '/PID', str(pid)], 
            capture_output=True, 
            text=True
        )
        if result.returncode == 0:
            print(f"  [OK] Successfully killed PID {pid}")
        else:
            print(f"  [WARN] Failed to kill PID {pid}: {result.stderr.strip()}")
    except Exception as e:
        print(f"  [ERROR] Exception while killing PID {pid}: {e}")

def main():
    print(f"--- Surgical Port Cleaning ---")
    print(f"Current PID: {CURRENT_PID}, Parent PID: {PARENT_PID}")
    print(f"Scanning for processes listening on ports: {PORTS_TO_KILL}...")
    
    try:
        result = subprocess.run(
            ['netstat', '-aon'], 
            capture_output=True, 
            text=True, 
            encoding='utf-8', 
            errors='ignore'
        )
        lines = result.stdout.split('\n')
        
        for line in lines:
            if 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5:
                    local_addr = parts[1]
                    pid_str = parts[4]
                    
                    for port in PORTS_TO_KILL:
                        if local_addr.endswith(f":{port}"):
                            print(f"Found LISTENING on port {port}: PID {pid_str}")
                            kill_port_safely(pid_str)
                            break # Avoid double-processing the same line
                        
    except Exception as e:
        print(f"[ERROR] Error running netstat: {e}")
        
    print("--- Port cleaning completed safely. ---")

if __name__ == "__main__":
    main()