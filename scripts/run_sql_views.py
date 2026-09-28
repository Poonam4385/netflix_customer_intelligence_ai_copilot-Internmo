from pathlib import Path
import sys
ROOT_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_PATH))
from sqlalchemy import create_engine
from src.utils.config import get_settings, ROOT
engine=create_engine(get_settings().database_url)
sql=(ROOT/"database"/"analytics_views.sql").read_text(encoding="utf-8")
with engine.begin() as conn: conn.exec_driver_sql(sql)
print("Analytics views created")
