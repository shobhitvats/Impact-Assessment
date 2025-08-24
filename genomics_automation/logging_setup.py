"""
Structured logging configuration with fallback for missing structlog.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

# Try to import structlog, fallback to standard logging if not available
try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False
    # Create a mock structlog interface
    class MockStructlog:
        @staticmethod
        def get_logger(name=None):
            return logging.getLogger(name or __name__)
        
        class contextvars:
            @staticmethod
            def merge_contextvars():
                return lambda logger, method_name, event_dict: event_dict
        
        class processors:
            @staticmethod
            def add_log_level():
                return lambda logger, method_name, event_dict: event_dict
            
            @staticmethod
            def TimeStamper(fmt="ISO"):
                def add_timestamp(logger, method_name, event_dict):
                    event_dict["timestamp"] = datetime.now().isoformat()
                    return event_dict
                return add_timestamp
            
            @staticmethod
            def CallsiteParameterAdder(parameters=None):
                return lambda logger, method_name, event_dict: event_dict
            
            @staticmethod
            def dict_tracebacks():
                return lambda logger, method_name, event_dict: event_dict
            
            @staticmethod
            def JSONRenderer():
                return lambda logger, method_name, event_dict: str(event_dict)
            
            class CallsiteParameter:
                FUNC_NAME = "func_name"
        
        class dev:
            @staticmethod
            def ConsoleRenderer(colors=True):
                def render(logger, method_name, event_dict):
                    timestamp = event_dict.get("timestamp", "")
                    message = event_dict.get("event", "")
                    return f"[{timestamp}] {message}"
                return render
        
        @staticmethod
        def configure(*args, **kwargs):
            pass
        
        @staticmethod
        def make_filtering_bound_logger(level):
            return logging.Logger
        
        @staticmethod
        def WriteLoggerFactory():
            return logging.getLogger
    
    structlog = MockStructlog()


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    run_id: Optional[str] = None
):
    """
    Configure structured logging for the genomics pipeline.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for logging
        run_id: Optional run identifier for scoped logging
    
    Returns:
        Configured logger
    """
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )
    
    # Configure structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="ISO"),
    ]
    
    # Add run_id to context if provided
    if run_id:
        processors.append(
            structlog.processors.CallsiteParameterAdder(
                parameters=[structlog.processors.CallsiteParameter.FUNC_NAME]
            )
        )
    
    # Configure output format
    if log_file:
        # JSON format for file logging
        processors.extend([
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer()
        ])
        
        # Setup file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper()))
        logging.getLogger().addHandler(file_handler)
    else:
        # Human-readable format for console
        processors.extend([
            structlog.dev.ConsoleRenderer(colors=True)
        ])
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    logger = structlog.get_logger()
    
    if run_id:
        logger = logger.bind(run_id=run_id)
    
    return logger


def get_run_logger(run_dir: Path, run_id: str):
    """
    Get a run-scoped logger that writes to a specific run directory.
    
    Args:
        run_dir: Directory for the current run
        run_id: Unique identifier for the run
    
    Returns:
        Configured logger for the run
    """
    log_file = run_dir / f"pipeline_{run_id}.log"
    return setup_logging(
        level="DEBUG",
        log_file=log_file,
        run_id=run_id
    )


class LogCapture:
    """Context manager for capturing logs from external processes."""
    
    def __init__(self, logger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"Starting {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = datetime.now() - self.start_time
        
        if exc_type is None:
            self.logger.info(
                f"Completed {self.operation}",
                duration_seconds=duration.total_seconds()
            )
        else:
            self.logger.error(
                f"Failed {self.operation}",
                duration_seconds=duration.total_seconds(),
                error=str(exc_val),
                exc_info=True
            )
    
    def log_stdout(self, output: str):
        """Log stdout from external process."""
        if output.strip():
            self.logger.debug(f"{self.operation} stdout", output=output.strip())
    
    def log_stderr(self, output: str):
        """Log stderr from external process."""
        if output.strip():
            self.logger.warning(f"{self.operation} stderr", output=output.strip())


# Module-level logger
if HAS_STRUCTLOG:
    logger = structlog.get_logger(__name__)
else:
    logger = logging.getLogger(__name__)
