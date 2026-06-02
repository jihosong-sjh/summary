import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status

from app.core.config import get_settings


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"pbkdf2_sha256$210000${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, rounds, salt_b64, digest_b64 = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_token(subject: str, token_type: str, expires_delta: timedelta, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if extra:
        payload.update(extra)

    header_b64 = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_sig, _b64url_decode(signature_b64)):
            raise credentials_error
        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("type") != expected_type:
            raise credentials_error
        if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
            raise credentials_error
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        raise credentials_error from exc


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    return create_token(user_id, "access", timedelta(minutes=settings.access_token_minutes))


def create_refresh_token(user_id: str, token_version: int) -> str:
    settings = get_settings()
    return create_token(
        user_id,
        "refresh",
        timedelta(days=settings.refresh_token_days),
        {"version": token_version},
    )

