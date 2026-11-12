from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)

@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    mode: str = "local"
    runtime_directory: str = ""
    database_url: str = ""
    qdrant_url: str = ""
    demo_identities: bool = True
    chat_model: str = "gpt-5.4-mini-2026-03-17"
    embedding_model: str = "text-embedding-3-small"
    judge_model: str = "gpt-5.5-2026-04-23"
    remote_tracing: bool = False
    auth_mode: str = "demo"

    @property
    def data_dir(self): return self.root / "data"

    @property
    def runtime(self):
        path = Path(self.runtime_directory) if self.runtime_directory else self.root / ".runtime"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def db_url(self):
        return self.database_url or f"sqlite:///{self.runtime / 'compass.db'}"

    @classmethod
    def from_env(cls):
        mode = os.getenv("COMPASS_MODE", "local")
        if mode not in {"local", "live"}:
            raise ValueError("COMPASS_MODE must be local or live")
        return cls(mode=mode, runtime_directory=os.getenv("COMPASS_RUNTIME_DIR", ""), database_url=os.getenv("DATABASE_URL", ""),
                   qdrant_url=os.getenv("QDRANT_URL", ""),
                   demo_identities=os.getenv("COMPASS_DEMO_IDENTITIES", "true").lower() == "true",
                   chat_model=os.getenv("COMPASS_CHAT_MODEL", cls.chat_model),
                   embedding_model=os.getenv("COMPASS_EMBEDDING_MODEL", cls.embedding_model),
                   judge_model=os.getenv("COMPASS_JUDGE_MODEL", cls.judge_model),
                   remote_tracing=os.getenv("COMPASS_REMOTE_TRACING", "false").lower() == "true",
                   auth_mode=os.getenv("COMPASS_AUTH_MODE", "demo"))
