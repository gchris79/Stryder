from functools import lru_cache
from django.conf import settings
from stryder_core.bootstrap import bootstrap_context_core
from stryder_core.db_schema import connect_db
from stryder_core.metrics import build_metrics

@lru_cache(maxsize=1)
def get_bootstrap():
    """
    Runs once per Django process.
    Pure bootstrap: validates paths, resolves timezone, sets runtime_context.
    """
    return bootstrap_context_core(settings.STRYDER_CORE_CONFIG)

@lru_cache(maxsize=1)
def get_metrics():
    """
    Metrics map is static -> cache it once.
    """
    get_bootstrap()
    return build_metrics("local")


def get_conn():
    return connect_db(settings.STRYDER_DB_PATH)