# config.py — one place, explicit, fails loud
import os
from dataclasses import dataclass
from abstract_utilities import *

@dataclass(frozen=True)
class StorageConfig:
    videos_root: str
    documents_root: str
    js_runtime: str = "deno"  # or from env

    @classmethod
    def from_env(cls,videos_root=None,documents_root=None) -> "StorageConfig":
        missing = []
        videos_root = videos_root or get_env_value("VIDEOS_ROOT") or get_default_videos_dir()
        documents_root = documents_root or get_env_value("DOCUMENTS_ROOT") or get_default_documents_dir()
        if not videos_root:
            missing.append("VIDEOS_ROOT")
        if not documents_root:
            missing.append("DOCUMENTS_ROOT")
        if missing:
            raise EnvironmentError(
                f"Required env vars not set: {missing}. "
                f"Set them explicitly — no defaults are assumed."
            )
        return cls(
            videos_root=videos_root,
            documents_root=documents_root,
            js_runtime=get_env_value("YT_DLP_JS_RUNTIME") or "deno",
        )
