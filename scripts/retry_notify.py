import sys
import os
import asyncio
import sqlite3

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), 'webui')))

from backend.db.alerts_db import AlertsDB
from backend.services.notifications import NotificationService

async def main():
    settings = AlertsDB.get_settings()
    print(f"Loaded Token: {settings.get('telegram_bot_token')[:10]}...") 
    service = NotificationService(settings)
    
    # Get last 2 triggered alerts
    db_path = os.path.join(os.getcwd(), 'webui/data/alerts.db')
    conn = sqlite3.connect(db_path)
    # Use row_factory to get dict-like access
    conn.row_factory = sqlite3.Row
    alerts = conn.execute("SELECT * FROM price_alerts WHERE status='triggered' ORDER BY triggered_at DESC LIMIT 2").fetchall()
    
    for alert in alerts:
        alert_dict = dict(alert)
        print(f"Retrying alert {alert_dict['id']} ({alert_dict['target_price']})...")
        
        # We don't have the exact triggered price easily available here, using target price + epsilon
        triggered_price = alert_dict['target_price']
        
        result = await service.send_alert(alert_dict, triggered_price)
        print(f"Result for {alert_dict['id']}: {result}")

    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
