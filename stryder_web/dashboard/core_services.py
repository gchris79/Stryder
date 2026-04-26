from functools import lru_cache
import json
import sqlite3

from stryder_core.bootstrap import bootstrap_context_core
from stryder_core.db_schema import connect_db
from stryder_core.metrics import build_metrics
from stryder_core.profile_memory import load_json, CONFIG_PATH

from stryder_web.stryder_web import settings


class ProfileRequiredError(Exception):
    pass

class MissingDatabaseError(Exception):
    pass


@lru_cache(maxsize=1)
def get_bootstrap():
    """
    Runs once per Django process.
    Pure bootstrap: validates paths, resolves timezone, sets runtime_context.
    """
    try:
        core_config = get_core_config()
        bootstrap_context_core(core_config)
        return core_config
    
    except(FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        raise ProfileRequiredError("Invalid or missing profile") from e
    

def get_core_config():
    try:
        core_config = load_json(CONFIG_PATH)

        active_profile = core_config["active_profile"]
        profiles = core_config["profiles"]
        profile = profiles[active_profile]
        tz_str = profile["timezone"]

        return core_config
    
    except(FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        raise ProfileRequiredError("Invalid or missing profile") from e
    

@lru_cache(maxsize=1)
def get_metrics():
    """
    Metrics map is static -> cache it once.
    """
    get_bootstrap()
    return build_metrics("local")


def get_conn():
    try:
        conn = connect_db(settings.STRYDER_DB_PATH)
        cur = conn.cursor()

        cur.execute("""
            SELECT name 
            FROM sqlite_master 
            WHERE type='table' AND name='runs';
        """)   

        if cur.fetchone() is None:
            raise MissingDatabaseError("Database exists but is not initialized")

        return conn
    
    except(FileNotFoundError, sqlite3.OperationalError) as e:
        raise MissingDatabaseError("Invalid or missing database") from e