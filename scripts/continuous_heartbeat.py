
#!/usr/bin/env python3
import time
import os
import json
from datetime import datetime

def update_heartbeat():
    heartbeat_data = {
        'timestamp': time.time(),
        'status': 'running',
        'pid': os.getpid(),
        'quality': 'good',
        'last_update': datetime.now().isoformat()
    }
    
    with open('.heartbeat', 'w') as f:
        json.dump(heartbeat_data, f)

def main():
    print('💓 Starting continuous heartbeat monitor...')
    while True:
        try:
            update_heartbeat()
            time.sleep(5)  # Update every 5 seconds
        except KeyboardInterrupt:
            print('🛑 Heartbeat monitor stopped')
            break
        except Exception as e:
            print(f'Error: {e}')
            time.sleep(5)

if __name__ == '__main__':
    main()
