"""Request identity is resolved server-side from sessions or API keys."""
from contextvars import ContextVar

tenant_context: ContextVar[str] = ContextVar("tenant", default="local")
