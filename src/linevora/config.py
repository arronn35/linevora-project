"""Uygulama yapılandırması (ortam değişkenleri)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

DEFAULT_USERS = "admin:admin123:admin,uzman:uzman123:specialist,izleyici:izleyici123:viewer"


@dataclass(frozen=True)
class Settings:
    env: str  # dev | prod
    secret_key: str
    token_ttl_seconds: int
    users: dict[str, tuple[str, str, str]]  # kullanıcı adı -> (parola, rol, tenant)
    blob_dir: str
    snapshot_path: str
    db_path: str = ""
    model_url: str = ""
    model_api_key: str = ""
    model_name: str = ""
    model_timeout_seconds: float = 30.0
    rate_limit_per_minute: int = 60
    matcher: str = "lexical"  # lexical | vector | hybrid
    seed_demo: bool = True
    db_url: str = ""
    embedding_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""


def _parse_users(raw: str) -> dict[str, tuple[str, str, str]]:
    users: dict[str, tuple[str, str, str]] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.split(":")
        if len(parts) not in (3, 4) or not all(parts):
            raise ValueError(
                f"geçersiz kullanıcı kaydı: {item!r} (biçim: ad:parola:rol[:tenant])"
            )
        users[parts[0]] = (parts[1], parts[2], parts[3] if len(parts) == 4 else "default")
    if not users:
        raise ValueError("en az bir kullanıcı tanımlanmalı")
    return users


@lru_cache
def get_settings() -> Settings:
    env = os.environ.get("LINEVORA_ENV", "dev")
    if env not in ("dev", "prod"):
        raise ValueError("LINEVORA_ENV dev ya da prod olmalı")
    secret_key = os.environ.get("LINEVORA_SECRET_KEY", "dev-secret-change-me")
    users_raw = os.environ.get("LINEVORA_USERS", DEFAULT_USERS)
    db_path = os.environ.get("LINEVORA_DB_PATH", "")
    snapshot_path = os.environ.get("LINEVORA_SNAPSHOT_PATH", "")
    seed_demo = os.environ.get("LINEVORA_SEED_DEMO", "1") not in ("0", "false", "no")
    if env == "prod":
        if secret_key == "dev-secret-change-me":
            raise RuntimeError("üretimde LINEVORA_SECRET_KEY zorunlu")
        if users_raw == DEFAULT_USERS:
            raise RuntimeError("üretimde LINEVORA_USERS zorunlu")
        # Kalıcılık ve parola-karması zorunluluğu uygulama açılışında
        # (create_app) denetlenir; ayar okuma tek başına engellenmez.
        seed_demo = False
    return Settings(
        env=env,
        secret_key=secret_key,
        token_ttl_seconds=int(os.environ.get("LINEVORA_TOKEN_TTL", "3600")),
        users=_parse_users(users_raw),
        blob_dir=os.environ.get("LINEVORA_BLOB_DIR", "var/blobs"),
        snapshot_path=snapshot_path,
        db_path=db_path,
        seed_demo=seed_demo,
        model_url=os.environ.get("LINEVORA_MODEL_URL", ""),
        model_api_key=os.environ.get("LINEVORA_MODEL_API_KEY", ""),
        model_name=os.environ.get("LINEVORA_MODEL_NAME", ""),
        model_timeout_seconds=float(os.environ.get("LINEVORA_MODEL_TIMEOUT", "30")),
        rate_limit_per_minute=int(os.environ.get("LINEVORA_RATE_LIMIT_PER_MINUTE", "60")),
        matcher=os.environ.get("LINEVORA_MATCHER", "lexical"),
        db_url=os.environ.get("LINEVORA_DB_URL", ""),
        embedding_url=os.environ.get("LINEVORA_EMBEDDING_URL", ""),
        embedding_api_key=os.environ.get("LINEVORA_EMBEDDING_API_KEY", ""),
        embedding_model=os.environ.get("LINEVORA_EMBEDDING_MODEL", ""),
    )
