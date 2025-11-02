python - <<'PY'
import sqlite3, os
db = os.path.abspath("data.db")      # replace if your DB path is different
con = sqlite3.connect(db)
cur = con.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS _write_test (id INTEGER PRIMARY KEY, t TEXT)")
cur.execute("INSERT INTO _write_test(t) VALUES (?)", ("ok",))
con.commit()
cur.execute("SELECT COUNT(*) FROM _write_test")
print("write_test rows:", cur.fetchone()[0])
con.close()
PY

