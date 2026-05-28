import os
from dataclasses import dataclass, field

TRUTHY = {"1", "true", "True", "YES", "yes"}
PRODUCTION_ENVS = {"prod", "production"}
PLACEHOLDER_KEY_MARKERS = ("CHANGE_ME", "YOUR_", "EXAMPLE", "DEV-KEY", "TEST-KEY", "DEFAULT")


@dataclass(frozen=True)
class Settings:
    env: str = field(default_factory=lambda: os.getenv("FACTOR_PLATFORM_ENV", "dev"))
    timezone: str = field(default_factory=lambda: os.getenv("FACTOR_PLATFORM_TZ", "Asia/Shanghai"))
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:factorplatform_dev_password@localhost:5432/factor_platform",
        )
    )
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    require_db: bool = field(default_factory=lambda: os.getenv("FACTOR_PLATFORM_REQUIRE_DB", "0") in TRUTHY)
    require_auth: bool = field(default_factory=lambda: os.getenv("FACTOR_PLATFORM_REQUIRE_AUTH", "0") in TRUTHY)
    api_keys: str = field(default_factory=lambda: os.getenv("FACTOR_PLATFORM_API_KEYS", ""))
    market_data_backend: str = field(default_factory=lambda: os.getenv("FACTOR_PLATFORM_MARKET_DATA_BACKEND", "files"))
    artifact_root: str = field(default_factory=lambda: os.getenv("FACTOR_PLATFORM_ARTIFACT_ROOT", "data/artifacts"))
    roadshow_seed_dump: str = field(default_factory=lambda: os.getenv("FACTOR_PLATFORM_ROADSHOW_SEED_DUMP", "data/db_dumps/roadshow_demo.dump"))


def get_settings() -> Settings:
    return Settings()


def _api_key_specs(raw: str) -> list[tuple[str, str]]:
    specs: list[tuple[str, str]] = []
    for item in (raw or "").split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue
        key, role = item.split(":", 1)
        key, role = key.strip(), role.strip()
        if key and role:
            specs.append((key, role))
    return specs


def _looks_like_placeholder(value: str) -> bool:
    upper = value.upper()
    return any(marker in upper for marker in PLACEHOLDER_KEY_MARKERS)


def validate_runtime_settings(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    env = settings.env.strip().lower()
    if env not in PRODUCTION_ENVS:
        return

    errors: list[str] = []
    if not settings.require_db:
        errors.append("FACTOR_PLATFORM_REQUIRE_DB must be enabled in production")
    if not settings.require_auth:
        errors.append("FACTOR_PLATFORM_REQUIRE_AUTH must be enabled in production")

    key_specs = _api_key_specs(settings.api_keys)
    if not key_specs:
        errors.append("FACTOR_PLATFORM_API_KEYS must contain at least one key:role pair in production")
    elif any(_looks_like_placeholder(key) for key, _ in key_specs):
        errors.append("FACTOR_PLATFORM_API_KEYS contains placeholder keys in production")

    if errors:
        raise ValueError("; ".join(errors))
