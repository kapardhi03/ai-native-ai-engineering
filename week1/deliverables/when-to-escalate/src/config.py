"""
config.py — the single place configuration comes from.

Everything that used to be a module constant scattered through belief.py lives
here instead: which provider produces the belief, which models, where the belief
cache is written, and whether the rule-based fallback is permitted.

Two things this fixes.

1. `.env` was inert. Nothing in the project loaded it, so keys placed there had
   no effect and the SDKs only saw whatever was already exported in the shell.
   `load_settings()` loads `.env` explicitly, once.

2. The cache path was relative to the *working directory*. Running from the repo
   root and from `when-to-escalate/` silently wrote two different caches, which
   breaks the guarantee the cache exists to provide — that both policies score
   the same beliefs. Paths here are resolved against the repo root and returned
   absolute, so the working directory no longer changes where anything lands.

Provider policy (locked decision 0d + build decision 3): a belief is supposed to
come from a real LLM call. The keyword fallback stays available so the pipeline
runs offline, but it is no longer allowed to be invisible — `allow_rule_fallback`
gates it, and callers can see which provider actually produced a belief. Offline
smoke tests keep working; a real run cannot silently degrade to keywords.

No secret is ever logged or repr'd. See `Settings.__repr__` and `describe()`.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# --------------------------------------------------------------------------- #
# Defaults. Every one of these is overridable from .env.
# --------------------------------------------------------------------------- #

VALID_PROVIDERS = ("auto", "openai", "google", "rule")

DEFAULT_PROVIDER = "auto"
DEFAULT_ALLOW_RULE_FALLBACK = True
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GOOGLE_MODEL = "gemini-2.0-flash"
DEFAULT_CACHE_PATH = "week1/deliverables/when-to-escalate/data/belief_cache.json"

_TRUE_TOKENS = frozenset({"1", "true", "t", "yes", "y", "on"})
_FALSE_TOKENS = frozenset({"0", "false", "f", "no", "n", "off"})


class ConfigError(RuntimeError):
    """Configuration is missing or self-contradictory. Raised early, not at call time."""


# --------------------------------------------------------------------------- #
# Locating the repo
# --------------------------------------------------------------------------- #

def find_repo_root(start: Optional[Path] = None) -> Path:
    """Walk upward looking for the .git directory.

    Falls back to the known depth of this file inside the repo
    (week1/deliverables/when-to-escalate/src/config.py -> 4 levels up) so an
    exported copy without .git still resolves sanely instead of raising.
    """
    here = Path(start if start is not None else __file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists():
            return candidate
    fallback = Path(__file__).resolve().parents[4]
    logger.debug("No .git found; falling back to %s as repo root.", fallback)
    return fallback


def deliverable_root() -> Path:
    """The when-to-escalate/ directory — src/'s parent."""
    return Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# .env loading
# --------------------------------------------------------------------------- #

def _env_candidates() -> list[Path]:
    """Where a .env may live, nearest-scope last so it wins."""
    return [find_repo_root() / ".env", deliverable_root() / ".env"]


def load_env(override: bool = False) -> list[Path]:
    """Load .env files into os.environ. Returns the ones actually found.

    Real environment variables win by default (override=False), so CI secrets
    and an explicit `export` are not clobbered by a stale local file.
    """
    try:
        from dotenv import load_dotenv
    except ImportError as exc:  # pragma: no cover - depends on install state
        raise ConfigError(
            "python-dotenv is not installed, so .env cannot be read. "
            "Install it with:  pip install -r requirements.txt"
        ) from exc

    loaded: list[Path] = []
    for path in _env_candidates():
        if path.is_file():
            load_dotenv(path, override=override)
            loaded.append(path)
            logger.debug("Loaded env file: %s", path)

    if not loaded:
        logger.warning(
            "No .env found (looked in: %s). Falling back to the process "
            "environment only.",
            ", ".join(str(p) for p in _env_candidates()),
        )
    return loaded


# --------------------------------------------------------------------------- #
# Typed readers. Each names the variable in its error so a bad value is
# traceable to the line in .env that caused it.
# --------------------------------------------------------------------------- #

def _read_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


def _read_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    token = raw.strip().lower()
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    raise ConfigError(
        f"{name}={raw!r} is not a boolean. "
        f"Use one of: {', '.join(sorted(_TRUE_TOKENS | _FALSE_TOKENS))}."
    )


def _read_secret(name: str) -> Optional[str]:
    """Secrets are optional here. Absence is only fatal when actually used."""
    raw = os.environ.get(name)
    return raw.strip() if raw and raw.strip() else None


def _resolve_path(raw: str) -> Path:
    """Relative paths resolve against the repo root, never the cwd."""
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = find_repo_root() / path
    return path.resolve()


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Settings:
    """Immutable, fully-resolved configuration for one run."""

    provider: str                  # one of VALID_PROVIDERS
    allow_rule_fallback: bool
    openai_model: str
    google_model: str
    cache_path: Path               # absolute
    openai_api_key: Optional[str]
    google_api_key: Optional[str]
    env_files: tuple[Path, ...] = ()

    # -- secrets never appear in logs or tracebacks -------------------------- #

    def __repr__(self) -> str:
        return (
            f"Settings(provider={self.provider!r}, "
            f"allow_rule_fallback={self.allow_rule_fallback}, "
            f"openai_model={self.openai_model!r}, "
            f"google_model={self.google_model!r}, "
            f"cache_path={str(self.cache_path)!r}, "
            f"openai_api_key={self._mask(self.openai_api_key)}, "
            f"google_api_key={self._mask(self.google_api_key)})"
        )

    @staticmethod
    def _mask(secret: Optional[str]) -> str:
        if not secret:
            return "<unset>"
        return f"<set:{len(secret)} chars, ...{secret[-4:]}>"

    # -- queries -------------------------------------------------------------#

    def has_key(self, provider: str) -> bool:
        return bool({"openai": self.openai_api_key,
                     "google": self.google_api_key}.get(provider))

    @property
    def live_providers(self) -> tuple[str, ...]:
        """LLM providers with a key present, in chain order."""
        return tuple(p for p in ("openai", "google") if self.has_key(p))

    def require_key(self, provider: str) -> str:
        """Fetch a key or explain precisely what is missing."""
        key = {"openai": self.openai_api_key,
               "google": self.google_api_key}.get(provider)
        if not key:
            var = "OPENAI_API_KEY" if provider == "openai" else "GOOGLE_API_KEY"
            raise ConfigError(
                f"Provider {provider!r} needs {var}, which is not set. "
                f"Add it to .env (checked: "
                f"{', '.join(str(p) for p in _env_candidates())})."
            )
        return key

    def describe(self) -> str:
        """Redacted multi-line summary, safe to write into a run log."""
        env = ", ".join(str(p) for p in self.env_files) or "none found"
        return "\n".join([
            "Belief configuration",
            f"  env files loaded : {env}",
            f"  provider         : {self.provider}",
            f"  rule fallback    : {'allowed' if self.allow_rule_fallback else 'BLOCKED'}",
            f"  openai model     : {self.openai_model} "
            f"({'key set' if self.openai_api_key else 'NO KEY'})",
            f"  google model     : {self.google_model} "
            f"({'key set' if self.google_api_key else 'NO KEY'})",
            f"  cache path       : {self.cache_path}",
        ])

    def with_overrides(self, **kwargs) -> "Settings":
        """A copy with fields replaced. For tests; does not touch os.environ."""
        return _validate(replace(self, **kwargs))


# --------------------------------------------------------------------------- #
# Validation — contradictions surface at load, not mid-experiment
# --------------------------------------------------------------------------- #

def _validate(settings: Settings) -> Settings:
    if settings.provider not in VALID_PROVIDERS:
        raise ConfigError(
            f"BELIEF_PROVIDER={settings.provider!r} is not recognised. "
            f"Valid values: {', '.join(VALID_PROVIDERS)}."
        )

    if settings.provider == "rule" and not settings.allow_rule_fallback:
        raise ConfigError(
            "BELIEF_PROVIDER=rule contradicts BELIEF_ALLOW_RULE_FALLBACK=false. "
            "Pick one: allow the fallback, or choose a real LLM provider."
        )

    if settings.provider in ("openai", "google"):
        settings.require_key(settings.provider)

    # The failure mode worth catching early: a strict run with no way to satisfy
    # it. Left to fail at call time it would burn the whole run first.
    if (settings.provider == "auto"
            and not settings.allow_rule_fallback
            and not settings.live_providers):
        raise ConfigError(
            "BELIEF_ALLOW_RULE_FALLBACK=false requires a real LLM call, but "
            "neither OPENAI_API_KEY nor GOOGLE_API_KEY is set, so no provider "
            "can produce a belief. Add a key, or allow the fallback."
        )

    return settings


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

_cached: Optional[Settings] = None


def load_settings(*, reload: bool = False, load_env_files: bool = True) -> Settings:
    """Build (and memoise) the Settings for this process.

    Cached because a run must not see configuration change halfway through.
    Pass reload=True after deliberately mutating os.environ.
    """
    global _cached
    if _cached is not None and not reload:
        return _cached

    env_files = tuple(load_env()) if load_env_files else ()

    settings = _validate(Settings(
        provider=_read_str("BELIEF_PROVIDER", DEFAULT_PROVIDER).lower(),
        allow_rule_fallback=_read_bool(
            "BELIEF_ALLOW_RULE_FALLBACK", DEFAULT_ALLOW_RULE_FALLBACK),
        openai_model=_read_str("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        google_model=_read_str("GOOGLE_MODEL", DEFAULT_GOOGLE_MODEL),
        cache_path=_resolve_path(_read_str("BELIEF_CACHE_PATH", DEFAULT_CACHE_PATH)),
        openai_api_key=_read_secret("OPENAI_API_KEY"),
        google_api_key=_read_secret("GEMINI_API_KEY") or _read_secret("GOOGLE_API_KEY"),
        env_files=env_files,
    ))

    logger.info("Configuration loaded.\n%s", settings.describe())
    _cached = settings
    return settings


def reset_cache() -> None:
    """Drop the memoised Settings. For tests."""
    global _cached
    _cached = None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    print(load_settings().describe())
