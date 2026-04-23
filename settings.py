from dataclasses import dataclass
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


ENV_FILE = Path(__file__).resolve().parent / ".env"

if DOTENV_AVAILABLE:
    # 让 .env 覆盖同名系统环境变量，避免页面长期显示旧配置。
    load_dotenv(dotenv_path=ENV_FILE, override=True)


@dataclass
class AppSettings:
    default_api_key: str
    default_base_url: str
    default_question_model: str
    default_evaluation_model: str
    default_whisper_model: str
    sqlite_path: str
    supabase_url: str
    supabase_anon_key: str
    supabase_bucket: str
    retention_days: int
    encryption_key: str
    max_api_requests_per_minute: int
    enable_cloud_sync: bool


def load_settings() -> AppSettings:
    enable_cloud_sync = os.getenv("ENABLE_SUPABASE", "false").lower() in {"1", "true", "yes"}
    default_base_url = os.getenv("OPENAI_BASE_URL", "") or os.getenv("VOLCENGINE_BASE_URL", "")
    default_api_key = os.getenv("OPENAI_API_KEY", "") or os.getenv("VOLCENGINE_API_KEY", "")
    return AppSettings(
        default_api_key=default_api_key,
        default_base_url=default_base_url,
        default_question_model=os.getenv("QUESTION_MODEL", "gpt-4o-mini"),
        default_evaluation_model=os.getenv("EVALUATION_MODEL", "gpt-4o-mini"),
        default_whisper_model=os.getenv("WHISPER_MODEL", "whisper-1"),
        sqlite_path=os.getenv("SQLITE_DB_PATH", "interview_records.db"),
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
        supabase_bucket=os.getenv("SUPABASE_BUCKET", "interview-audio"),
        retention_days=int(os.getenv("RETENTION_DAYS", "30")),
        encryption_key=os.getenv("PRIVACY_ENCRYPTION_KEY", ""),
        max_api_requests_per_minute=int(os.getenv("MAX_API_REQUESTS_PER_MIN", "20")),
        enable_cloud_sync=enable_cloud_sync,
    )
