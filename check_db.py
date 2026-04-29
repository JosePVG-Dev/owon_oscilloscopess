from database import Database

db = Database()
rows = db.get_recent(10)
for r in rows:
    print(f"ID {r['id']} | {r['timestamp']} | {r['channel']} | {r['wave_type']} | {r['frequency']} Hz")
