import os
from openai import OpenAI

# ── Application Configuration ──────────────────────────────────────────────
class Config:
    SECRET_KEY = os.environ.get("THANZI_SECRET_KEY", "thanzi-malawi-2026-secure-key-change-in-production")
    DATABASE_PATH = os.environ.get("THANZI_DB_PATH", "thanzi.db")
    DEBUG = os.environ.get("THANZI_DEBUG", "true").lower() == "true"

    # Session configuration
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 28800  # 8 hours in seconds

    # Pagination
    RECORDS_PER_PAGE = 25

    # Risk level constants
    RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"]

    # User role constants
    USER_ROLES = ["ADMIN", "CHW", "SUPERVISOR", "DHO"]

    # Supported languages
    SUPPORTED_LANGUAGES = ["English", "Chichewa", "Mixed"]


# ── Azure AI Foundry Client (Microsoft Phi-4 via GitHub Models) ────────────
def get_ai_client():
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        raise EnvironmentError(
            "GITHUB_TOKEN is not set.\n"
            "Run: set GITHUB_TOKEN=your_token_here (Windows)\n"
            "Run: export GITHUB_TOKEN=your_token_here (Mac/Linux)"
        )
    return OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=github_token,
    )


# ── Model Configuration ─────────────────────────────────────────────────────
class ModelConfig:
    PRIMARY_MODEL = "Phi-4"
    MAX_TOKENS_EXTRACTION = 800
    MAX_TOKENS_ASSESSMENT = 1200
    MAX_TOKENS_TRIAGE = 1500
    MAX_TOKENS_ESCALATION = 1200
    MAX_TOKENS_SUPERVISOR = 1000
    MAX_TOKENS_TRANSLATION = 600
    RESPONSE_FORMAT_JSON = {"type": "json_object"}
    PLATFORM_LABEL = "Microsoft Phi-4 via Azure AI Foundry"