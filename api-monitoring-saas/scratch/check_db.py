from backend.models import get_db
db = get_db()
user_id = '3568d76e-096c-4a3b-b849-ddf90317e07e'
endpoints = db.execute("SELECT id, name, url FROM api_endpoints WHERE user_id = %s", (user_id,)).fetchall()
print(f"Endpoints for {user_id}: {len(endpoints)}")
for ep in endpoints:
    print(f" - {ep['name']} ({ep['url']})")

logs = db.execute("SELECT COUNT(*) as count FROM monitoring_logs WHERE endpoint_id IN (SELECT id FROM api_endpoints WHERE user_id = %s)", (user_id,)).fetchone()
print(f"Total logs: {logs['count']}")
