"""Central request-context dependency boundary."""

from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Trusted server-derived request context.

    Authentication and organization membership will populate this boundary in
    later approved tasks. Client-supplied tenant identifiers are never trusted.
    """

    user_id: str | None = None
    organization_id: str | None = None


def get_request_context(request: Request) -> RequestContext:
    context = getattr(request.state, "request_context", None)
    if isinstance(context, RequestContext):
        return context
    return RequestContext()