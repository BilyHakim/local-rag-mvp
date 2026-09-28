"""Request identity comes exclusively from server-managed API keys."""
from contextvars import ContextVar

tenant_context: ContextVar[str] = ContextVar("tenant", default="local")
