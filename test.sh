# See which DB path your app is actually using
python - <<'PY'
from backend.db import engine
from pathlib import Path
print("SQLAlchemy URL:", engine.url)
p = Path(str(engine.url).replace("sqlite:///",""))
print("Absolute path:", p.resolve())
print("Exists:", p.exists())
PY

# Check ownership & permissions of the file and its directory (SQLite needs to write WAL/SHM files in the same dir)
DB="./data.db"  # replace if the print above shows a different path
ls -l "$DB" 2>/dev/null || echo "No $DB yet"
ls -ld "$(dirname "$DB")"

# Is anything holding the DB open? (optional)
lsof -nP "$DB" 2>/dev/null || true

