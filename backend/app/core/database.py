import logging
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.local import Local

logger = logging.getLogger(__name__)

# SQLAlchemy database instance
db = SQLAlchemy()

# Context-local storage to hold the current tenant ID during a request lifecycle
_tenant_context = Local()

def set_current_tenant(tenant_id: str):
    """Sets the tenant ID in the request context."""
    _tenant_context.current_tenant = tenant_id

def get_current_tenant() -> str:
    """Gets the current tenant ID from the request context."""
    return getattr(_tenant_context, "current_tenant", None)

def clear_current_tenant():
    """Clears the tenant ID from the request context."""
    if hasattr(_tenant_context, "current_tenant"):
        del _tenant_context.current_tenant

@event.listens_for(Engine, "before_cursor_execute")
def set_postgresql_rls_context(conn, cursor, statement, parameters, context, executemany):
    """
    SQLAlchemy event listener to bind the tenant ID to the PostgreSQL connection
    before executing any query. This enables native Row Level Security (RLS).
    """
    tenant_id = get_current_tenant()
    if not tenant_id:
        return

    # Only apply RLS SET LOCAL if running on PostgreSQL
    dialect_name = conn.dialect.name
    if dialect_name == "postgresql":
        try:
            # We run it directly on the cursor so it doesn't trigger nested event listeners
            cursor.execute("SET LOCAL app.current_tenant = %s;", (str(tenant_id),))
        except Exception as e:
            logger.error(f"Failed to set app.current_tenant session variable: {e}")
