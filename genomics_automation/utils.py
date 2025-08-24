"""
Utility functions for file I/O, temporary directories, checksums, and retry logic.
"""

import hashlib
import shutil
import tempfile
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, Dict, List
import json
import csv
from datetime import datetime

T = TypeVar('T')


def generate_run_id() -> str:
    """Generate a unique run identifier."""
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def create_run_directory(base_dir: Path, run_id: str) -> Path:
    """
    Create a dated run directory.
    
    Args:
        base_dir: Base directory for runs
        run_id: Unique run identifier
    
    Returns:
        Path to created run directory
    """
    run_dir = base_dir / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def calculate_file_checksum(file_path: Path, algorithm: str = "md5") -> str:
    """
    Calculate checksum for a file.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm (md5, sha1, sha256)
    
    Returns:
        Hexadecimal hash string
    """
    hash_obj = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()


def safe_copy_file(src: Path, dst: Path, preserve_metadata: bool = True) -> bool:
    """
    Safely copy a file with error handling.
    
    Args:
        src: Source file path
        dst: Destination file path
        preserve_metadata: Whether to preserve file metadata
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if preserve_metadata:
            shutil.copy2(src, dst)
        else:
            shutil.copy(src, dst)
        return True
    except Exception as e:
        print(f"Error copying {src} to {dst}: {e}")
        return False


def ensure_directory(path: Path) -> Path:
    """Ensure directory exists, creating if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_temp_files(temp_dir: Path, preserve_on_error: bool = True) -> None:
    """
    Clean up temporary files and directories.
    
    Args:
        temp_dir: Temporary directory to clean
        preserve_on_error: Whether to preserve files if there were errors
    """
    if temp_dir.exists() and not preserve_on_error:
        shutil.rmtree(temp_dir)


def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying function calls on failure.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay on each retry
        exceptions: Tuple of exceptions to catch and retry on
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        print(f"Attempt {attempt + 1} failed: {e}. Retrying in {current_delay}s...")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        print(f"All {max_attempts} attempts failed.")
            
            raise last_exception
        
        return wrapper
    return decorator


class FileProcessor:
    """Helper class for processing files with error handling."""
    
    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or Path(tempfile.mkdtemp())
        self.processed_files: List[Path] = []
        self.errors: List[Dict[str, Any]] = []
    
    def add_error(self, file_path: Path, error: str, details: Optional[Dict] = None):
        """Add an error to the error log."""
        error_entry = {
            "file": str(file_path),
            "error": error,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.errors.append(error_entry)
    
    def write_error_log(self, output_path: Path) -> None:
        """Write error log to file."""
        with open(output_path, 'w') as f:
            json.dump(self.errors, f, indent=2)
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors."""
        error_types = {}
        for error in self.errors:
            error_type = error["error"]
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            "total_errors": len(self.errors),
            "error_types": error_types,
            "files_with_errors": len(set(error["file"] for error in self.errors))
        }


def read_csv_with_encoding_detection(file_path: Path) -> List[Dict[str, str]]:
    """
    Read CSV file with automatic encoding detection.
    
    Args:
        file_path: Path to CSV file
    
    Returns:
        List of dictionaries representing CSV rows
    """
    encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                return list(reader)
        except UnicodeDecodeError:
            continue
    
    raise ValueError(f"Could not decode {file_path} with any of the attempted encodings: {encodings}")


def write_csv_safely(data: List[Dict[str, Any]], file_path: Path, encoding: str = 'utf-8') -> bool:
    """
    Write CSV file with error handling.
    
    Args:
        data: List of dictionaries to write
        file_path: Output file path
        encoding: File encoding
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if not data:
            return False
        
        with open(file_path, 'w', newline='', encoding=encoding) as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        
        return True
    except Exception as e:
        print(f"Error writing CSV to {file_path}: {e}")
        return False


def validate_file_exists(file_path: Path, file_type: str = "file") -> bool:
    """
    Validate that a file exists and is readable.
    
    Args:
        file_path: Path to validate
        file_type: Description of file type for error messages
    
    Returns:
        True if valid, False otherwise
    """
    if not file_path.exists():
        print(f"Error: {file_type} not found at {file_path}")
        return False
    
    if not file_path.is_file():
        print(f"Error: {file_path} is not a file")
        return False
    
    try:
        with open(file_path, 'r') as f:
            f.read(1)  # Try to read one character
        return True
    except Exception as e:
        print(f"Error: Cannot read {file_type} at {file_path}: {e}")
        return False


def create_temp_file(suffix: str = "", prefix: str = "genomics_", directory: Optional[Path] = None) -> Path:
    """
    Create a temporary file with specified parameters.
    
    Args:
        suffix: File suffix/extension
        prefix: File prefix
        directory: Directory to create file in
    
    Returns:
        Path to created temporary file
    """
    fd, temp_path = tempfile.mkstemp(
        suffix=suffix,
        prefix=prefix,
        dir=str(directory) if directory else None
    )
    # Close the file descriptor since we just need the path
    import os
    os.close(fd)
    
    return Path(temp_path)
