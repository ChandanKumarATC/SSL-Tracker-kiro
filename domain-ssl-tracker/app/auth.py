"""
Simple session-based authentication.
Uses a signed cookie (itsdangerous) — no DB needed for auth.
"""
import hashlib
import hmac
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from app.config import ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY

SESSION_COOKIE = "ssl_tracker_session"
SESSION_VALUE  = "authenticated"


def _sign(value: str) -> str:
    """Create an HMAC signature for the session value."""
    sig = hmac.new(SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()
    return f"{value}.{sig}"


def _verify(signed: str) -> bool:
    """Verify a signed session cookie."""
    try:
        value, sig = signed.rsplit(".", 1)
        expected = hmac.new(SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected) and value == SESSION_VALUE
    except Exception:
        return False


def is_logged_in(request: Request) -> bool:
    """Return True if the request has a valid session cookie."""
    cookie = request.cookies.get(SESSION_COOKIE, "")
    return _verify(cookie)


def require_login(request: Request):
    """Dependency — raises redirect to /login if not authenticated."""
    if not is_logged_in(request):
        raise HTTPException(status_code=302, headers={"Location": f"/login?next={request.url.path}"})


def check_credentials(username: str, password: str) -> bool:
    """Validate username and password against config."""
    return (
        hmac.compare_digest(username.strip(), ADMIN_USERNAME) and
        hmac.compare_digest(password, ADMIN_PASSWORD)
    )


def make_session_cookie() -> str:
    """Return a signed session cookie value."""
    return _sign(SESSION_VALUE)
