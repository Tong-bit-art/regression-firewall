import sqlite3

conn = sqlite3.connect("app.db")
conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
for name in ("alice", "bob"):
    conn.execute("INSERT INTO users(name) VALUES (?)", (name,))
conn.commit()
print("ok")
