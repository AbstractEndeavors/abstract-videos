from abstract_database import (
    execute_query,
    insert_any_combo,
    fetch_any_combo_,
    update_any_combo,
    connectionManager,
    create_connection
)
from abstract_utilities  import get_env_value

def init_db(env_vars=None):
    env_vars = env_vars or [
    "ABSTRACT_DATABASE_USER",
    "ABSTRACT_DATABASE_PORT",
    "ABSTRACT_DATABASE_DBNAME",
    "ABSTRACT_DATABASE_HOST",
    "ABSTRACT_DATABASE_PASSWORD",
    ]
    env_values = {key.split('_')[-1].lower():get_env_value(key) for key in env_vars}
    create_connection(**env_values)
    return execute_query("""
        CREATE TABLE IF NOT EXISTS videos (
            id SERIAL PRIMARY KEY,
            video_id TEXT UNIQUE NOT NULL,
            info JSONB,
            metadata JSONB,
            whisper JSONB,
            captions JSONB,
            thumbnails JSONB,
            total_info JSONB,
            aggregated JSONB,
            seodata JSONB,
            audio_path TEXT,
            audio_format TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """, fetch=False)

def upsert_video(video_id: str, **fields):
    existing = fetch_any_combo_(
        table_name="videos",
        search_map={"video_id": video_id},
    )
    if existing:
        return update_any_combo(
            table_name="videos",
            update_map={**fields, "updated_at": "NOW()"},
            search_map={"video_id": video_id},
        )
    else:
        return insert_any_combo(
            table_name="videos",
            insert_map={"video_id": video_id, **fields},
        )

def get_video_record(video_id: str, hide_audio: bool = True) -> dict | None:
    rows = fetch_any_combo_(
        table_name="videos",
        search_map={"video_id": video_id},
    )
    if not rows:
        return None
    record = rows[0]
    if hide_audio and "audio" in record:
        record["audio"] = f"<{len(record['audio'])} bytes>" if record["audio"] else None
    return record

init_db()
