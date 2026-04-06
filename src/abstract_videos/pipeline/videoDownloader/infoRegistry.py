# at top:
import portalocker
import fasteners
from .imports import *
from abstract_utilities import SingletonMeta
from abstract_webtools import get_corrected_url,get_video_id
def _save_registry_unlocked(self):
    # Caller holds write_lock (thread-safety); now add process-safety.
    tmp = f"{self.registry_path}.tmp"
    safe_dump_to_file(self.registry, tmp)
    # atomic replace still helps, but lock ensures we don't interleave writers
    with open(self.registry_path, "wb") as f:
        portalocker.lock(f, portalocker.LOCK_EX)
        with open(tmp, "rb") as src:
            f.write(src.read())
        f.flush()
        os.fsync(f.fileno())
        portalocker.unlock(f)
    os.remove(tmp)
def get_file_data(filepath, default=None):
    if not os.path.isfile(filepath):
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        safe_dump_to_file(default or {}, filepath)
    return safe_read_from_file(file_path=filepath)

def load_json_keys(filepath, main_data=None, default=None):
    base = default or {}
    main = dict(main_data or {})
    try:
        disk = get_file_data(filepath, default=base)
        for k, v in (main or {}).items():
            if isinstance(v, dict):
                v.update(disk.get(k, {}))
            else:
                main[k] = disk.get(k, v)
        # Also merge any keys present on disk but missing in main
        for k, v in disk.items():
            main.setdefault(k, v)
        return main
    except Exception:
        return main or base



def _first_existing(*paths):
    for p in paths:
        if p and os.path.isdir(p):
            return p
    return None

def get_videos_root(explicit: str | None = None, envPath: str | None = None) -> str:
    """
    Resolve the videos root with this priority:
      1) explicit arg
      2) env file (VIDEOS_ROOT or legacy DATA_DIRECTORY)
      3) process env (VIDEOS_ROOT or legacy DATA_DIRECTORY)
      4) hard default (/mnt/24T/media/DATA/videos)
    """
    # 1) explicit
    if explicit:
        os.makedirs(explicit, exist_ok=True)
        return explicit

    # 2) env file
    v_from_envfile = (
        get_env_value(key="VIDEOS_ROOT", path=envPath)
        or get_env_value(key="DATA_DIRECTORY", path=envPath)  # legacy
    )
    if v_from_envfile:
        os.makedirs(v_from_envfile, exist_ok=True)
        return v_from_envfile

    # 3) process env
    v_from_env = os.getenv("VIDEOS_ROOT") or os.getenv("DATA_DIRECTORY")  # legacy
    if v_from_env:
        os.makedirs(v_from_env, exist_ok=True)
        return v_from_env

    # 4) hard default
    os.makedirs(DEFAULT_VIDEOS_ROOT, exist_ok=True)
    return DEFAULT_VIDEOS_ROOT


def get_documents_root(explicit: str | None = None, envPath: str | None = None) -> str:
    """
    Same idea as get_videos_root, but for documents/registry.
    Priority: explicit -> env file DOCUMENTS_ROOT -> env DOCUMENTS_ROOT -> hard default.
    """
    if explicit:
        os.makedirs(explicit, exist_ok=True)
        return explicit

    d_from_envfile = get_env_value(key="DOCUMENTS_ROOT", path=envPath)
    if d_from_envfile:
        os.makedirs(d_from_envfile, exist_ok=True)
        return d_from_envfile

    d_from_env = os.getenv("DOCUMENTS_ROOT")
    if d_from_env:
        os.makedirs(d_from_env, exist_ok=True)
        return d_from_env

    os.makedirs(DEFAULT_DOCUMENTS_ROOT, exist_ok=True)
    return DEFAULT_DOCUMENTS_ROOT


def get_video_directory(key: str | None = None, envPath: str | None = None, videos_root: str | None = None) -> str:
    """
    Assure that a valid *videos* directory exists and return its path.

    Priority:
      - videos_root arg (if passed)
      - env file (VIDEOS_ROOT or legacy DATA_DIRECTORY)
      - process env (VIDEOS_ROOT or legacy DATA_DIRECTORY)
      - DEFAULT_VIDEOS_ROOT (/mnt/24T/media/DATA/videos)
    """
    # keep key/envPath for backward compatibility with callers that used an env file
    # but prefer the explicit arg if provided
    root = get_videos_root(explicit=videos_root, envPath=envPath)
    os.makedirs(root, exist_ok=True)
    logger.info(f"using videos root: {root}")
    return root


class infoRegistry(metaclass=SingletonMeta):
    def __init__(self, config: StorageConfig=None, videos_root=None, documents_root=None, flat_layout: bool = False, **kwargs):
        if not hasattr(self, "initialized"):
            self.initialized = True
            self.config = config or StorageConfig.from_env()
            self.videos_root = self.config.videos_root
            self.documents_root = self.config.documents_root
    def _upsert(self, video_id, data: dict):
        upsert_video(video_id, info=data)

    def get_video_info(self, url=None, video_id=None, video_path=None, force_refresh=False):
        url = get_corrected_url(url)
        if not video_id:
            if url:
                video_id = get_video_id(url)
            elif video_path:
                video_id = generate_video_id(video_path)

        if not force_refresh:
            row = get_video_record(video_id, hide_audio=False)
            if row:
                return row

        info = get_yt_dlp_info(url)  or {} if url else {}
        info_video_id = info.get('video_id')
        video_id = video_id or info_video_id
        if info_video_id != video_id:
            info['video_id'] = video_id
        info = ensure_standard_paths(
            info,
            video_id=video_id,
            root_dir=self.videos_root,
            video_url=url,
            video_path=video_path
        )
        if info:
            self._upsert(video_id, info)
            return {"video_id": video_id, "info": info}
        return None

    def edit_info(self, data, video_id=None, url=None, video_path=None):
        if not video_id:
            video_id = get_video_id(url) if url else generate_video_id(video_path)
        self._upsert(video_id, data)
        return self.get_video_info(video_id=video_id, force_refresh=True)
