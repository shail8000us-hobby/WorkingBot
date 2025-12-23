import os, time, hashlib, subprocess, json, sys
CFG = os.environ.get("GRID_CONFIG_PATH", "grid_config.env")
APPLY = os.environ.get("GRID_APPLY_CMD", "echo 'No APPLY cmd set' && exit 0")
AUDIT = os.environ.get("GRID_AUDIT_FILE", "audit/config_changes.jsonl")
POLL = float(os.environ.get("GRID_WATCH_POLL_SEC", "1.0"))
DEBOUNCE = float(os.environ.get("GRID_DEBOUNCE_SEC", "0.8"))

os.makedirs(os.path.dirname(AUDIT), exist_ok=True)

def fingerprint(path):
    if not os.path.exists(path): return None
    h = hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def load_env(path):
    env = {}
    if not os.path.exists(path): return env
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                k,v=line.split('=',1)
                env[k.strip()]=v.strip()
    return env

last_fp = None
last_mtime = 0
last_applied_ts = 0.0

print(f"[watch] Watching {CFG} every {POLL}s (debounce {DEBOUNCE}s)")
while True:
    try:
        if os.path.exists(CFG):
            mt = os.path.getmtime(CFG)
            fp = fingerprint(CFG)
            if fp != last_fp and (time.time() - last_applied_ts) > DEBOUNCE:
                # small debounce to avoid half-writes
                time.sleep(DEBOUNCE)
                new_env = load_env(CFG)
                # write audit entry
                entry = {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
                    "cfg_path": os.path.abspath(CFG),
                    "fingerprint": fp,
                    "env": new_env
                }
                with open(AUDIT, 'a', encoding='utf-8') as out:
                    out.write(json.dumps(entry) + "\n")
                print(f"[watch] Change detected → applying via: {APPLY}")
                # Apply: call the provided shell (typically the bot's reconcile/setter)
                subprocess.run(APPLY, shell=True, check=False)
                last_fp = fp
                last_mtime = mt
                last_applied_ts = time.time()
        time.sleep(POLL)
    except KeyboardInterrupt:
        print("[watch] Stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"[watch] Error: {e}")
        time.sleep(POLL)
