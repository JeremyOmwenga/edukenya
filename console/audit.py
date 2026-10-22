from django.conf import settings
from django_tenants.utils import schema_context


def record(actor, action, target=None, *, ip=None, details=None, actor_email=None):
    """Write an audit event to the public schema, whatever schema is active."""
    from .models import AuditEvent

    email = actor_email or (getattr(actor, "email", "") if actor is not None else "")
    with schema_context(settings.PUBLIC_SCHEMA_NAME):
        AuditEvent.objects.create(
            actor_email=email or "",
            action=action,
            target_type=type(target).__name__ if target is not None else "",
            target_id=str(getattr(target, "pk", "") or ""),
            target_label=str(target)[:255] if target is not None else "",
            details=details or {},
            ip=ip,
        )
