import os
import psycopg2
from dotenv import load_dotenv

# Load env vars from .env file
load_dotenv()

# Pull values from environment
PG_PARAMS = {
    "host": os.getenv("PG_HOST"),
    "port": int(os.getenv("PG_PORT")),
    "dbname": os.getenv("PG_DBNAME"),
    "user": os.getenv("PG_USER"),
    "password": os.getenv("PG_PASSWORD"),
}

PROJECT_NAME = os.getenv("PROJECT_NAME", "WRR Images")
OUTPUT_PATH = f"/tmp/{PROJECT_NAME.replace(' ', '_')}.qgz"

# --- Connect to DB and fetch the project ---
conn = psycopg2.connect(**PG_PARAMS)
cur = conn.cursor()

cur.execute(
    """
    SELECT content
    FROM application_qgis.qgis_projects
    WHERE name = %s
""",
    (PROJECT_NAME,),
)

row = cur.fetchone()
if not row:
    raise ValueError(f"No project found with name '{PROJECT_NAME}'")

with open(OUTPUT_PATH, "wb") as f:
    f.write(row[0])

print(f"Project '{PROJECT_NAME}' written to: {OUTPUT_PATH}")

cur.close()
conn.close()
