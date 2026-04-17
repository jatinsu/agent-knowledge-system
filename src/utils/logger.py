import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Global run ID for this execution
_current_run_id: Optional[str] = None
_run_logger: Optional[logging.Logger] = None


def get_run_id() -> str:
    """Get or create a unique run ID for this execution."""
    global _current_run_id
    if _current_run_id is None:
        _current_run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _current_run_id


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Set up a logger with console and file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Main log file
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "app.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Run-specific log file
    run_id = get_run_id()
    run_log_file = log_dir / f"run_{run_id}.log"
    run_handler = logging.FileHandler(run_log_file)
    run_handler.setLevel(logging.DEBUG)
    run_handler.setFormatter(formatter)
    logger.addHandler(run_handler)

    return logger


def setup_run_logger() -> logging.Logger:
    """Set up a dedicated logger for end-to-end run tracking."""
    global _run_logger

    if _run_logger is not None:
        return _run_logger

    run_id = get_run_id()
    _run_logger = logging.getLogger("run_tracker")
    _run_logger.setLevel(logging.INFO)

    # Prevent duplicate handlers
    if _run_logger.handlers:
        return _run_logger

    formatter = logging.Formatter(
        '%(asctime)s - [RUN] - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # End-to-end run log
    e2e_log_file = log_dir / f"e2e_run_{run_id}.log"
    e2e_handler = logging.FileHandler(e2e_log_file)
    e2e_handler.setLevel(logging.INFO)
    e2e_handler.setFormatter(formatter)
    _run_logger.addHandler(e2e_handler)

    # Also console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    _run_logger.addHandler(console_handler)

    _run_logger.info(f"=== Run {run_id} Started ===")
    _run_logger.info(f"End-to-end log: {e2e_log_file}")

    return _run_logger


def log_graph_query(query_type: str, query: str, result_count: int = 0, duration_ms: float = 0):
    """Log graph query operations."""
    logger = logging.getLogger("graph_queries")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        formatter = logging.Formatter(
            '%(asctime)s - GRAPH_QUERY - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Query-specific log file
        run_id = get_run_id()
        query_log_file = log_dir / f"graph_queries_{run_id}.log"
        file_handler = logging.FileHandler(query_log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.info(
        f"[{query_type}] query='{query}' | results={result_count} | duration={duration_ms:.2f}ms"
    )


def log_networkx_query(operation: str, params: dict, result_count: int = 0):
    """Log NetworkX graph operations."""
    logger = logging.getLogger("networkx_queries")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        formatter = logging.Formatter(
            '%(asctime)s - NETWORKX - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # NetworkX-specific log file
        run_id = get_run_id()
        nx_log_file = log_dir / f"networkx_queries_{run_id}.log"
        file_handler = logging.FileHandler(nx_log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    params_str = ", ".join([f"{k}={v}" for k, v in params.items()])
    logger.info(f"[{operation}] {params_str} | results={result_count}")
