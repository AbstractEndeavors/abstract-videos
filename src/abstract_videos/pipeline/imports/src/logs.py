from .imports import *
LOG_FORMAT = (
    "[%(asctime)s] "
    "%(levelname)-8s "
    "%(name)s:%(lineno)d | "
    "%(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"




def get_logger(
    name: str,
    log_dir: str | Path = "logs",
    level: int = logging.INFO,
    console: bool = True,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
):
    logger = logging.getLogger(name)

    # Prevent duplicate handlers (VERY important)
    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # File handler (rotating)
    file_handler = RotatingFileHandler(
        log_dir / f"{name}.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    logger.propagate = False
    return logger
logger = get_logger("video_pipeline")

logger.info("Starting download")
logger.warning("Missing thumbnail")
logger.error("Download failed", exc_info=True)
