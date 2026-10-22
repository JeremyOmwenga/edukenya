"""
Email verification tokens.

A token is the application id + its current nonce, signed with SECRET_KEY and
timestamped. It is rejected if it was tampered with, is older than
APPLICATION_VERIFY_MAX_AGE, or its nonce no longer matches (link already
used, or a newer link was sent).
"""
from django.conf import settings
from django.core import signing

SALT = "edukenya.onboarding.verify-email"


def make_token(application):
    return signing.dumps({"a": application.pk, "n": application.verification_nonce}, salt=SALT, compress=True)


def read_token(token):
    """Returns (application_id, nonce) or None if invalid/expired."""
    try:
        data = signing.loads(token, salt=SALT, max_age=settings.APPLICATION_VERIFY_MAX_AGE)
    except signing.BadSignature:  # includes SignatureExpired
        return None
    if not isinstance(data, dict) or not isinstance(data.get("a"), int) or not isinstance(data.get("n"), str):
        return None
    return data["a"], data["n"]
