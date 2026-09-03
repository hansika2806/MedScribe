"""Scheduled cleanup tasks for MedScribe."""

import logging
import time
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

TEMP_DIR = Path("data/temp")
MAX_AGE_HOURS = 24  # Delete files older than 24 hours


def cleanup_temp_files(max_age_hours: int = MAX_AGE_HOURS) -> tuple[int, int]:
    """
    Clean up temporary files older than specified age.
    
    Args:
        max_age_hours: Maximum age of files to keep (default: 24 hours)
        
    Returns:
        Tuple of (files_deleted, errors_encountered)
        
    Example:
        >>> deleted, errors = cleanup_temp_files(24)
        >>> print(f"Deleted {deleted} files with {errors} errors")
    """
    if not TEMP_DIR.exists():
        logger.info("Temp directory does not exist, nothing to clean")
        return 0, 0
    
    cutoff_time = time.time() - (max_age_hours * 3600)
    deleted_count = 0
    error_count = 0
    
    logger.info(f"Starting cleanup of temp files older than {max_age_hours} hours")
    
    for file_path in TEMP_DIR.iterdir():
        if not file_path.is_file():
            continue
            
        try:
            # Check file age
            file_mtime = file_path.stat().st_mtime
            if file_mtime < cutoff_time:
                file_age_hours = (time.time() - file_mtime) / 3600
                file_path.unlink()
                deleted_count += 1
                logger.debug(f"Deleted temp file: {file_path.name} (age: {file_age_hours:.1f}h)")
        except Exception as e:
            error_count += 1
            logger.error(f"Failed to delete temp file {file_path.name}: {e}")
    
    logger.info(f"Cleanup complete: {deleted_count} files deleted, {error_count} errors")
    return deleted_count, error_count


def get_temp_dir_size() -> tuple[int, int]:
    """
    Get the size and file count of temp directory.
    
    Returns:
        Tuple of (total_size_bytes, file_count)
    """
    if not TEMP_DIR.exists():
        return 0, 0
    
    total_size = 0
    file_count = 0
    
    for file_path in TEMP_DIR.iterdir():
        if file_path.is_file():
            try:
                total_size += file_path.stat().st_size
                file_count += 1
            except Exception as e:
                logger.warning(f"Could not stat file {file_path.name}: {e}")
    
    return total_size, file_count


def monitor_temp_directory(warn_size_mb: int = 1000) -> None:
    """
    Monitor temp directory and log warning if it exceeds size threshold.
    
    Args:
        warn_size_mb: Size threshold in MB to trigger warning (default: 1000MB)
    """
    total_size, file_count = get_temp_dir_size()
    size_mb = total_size / (1024 * 1024)
    
    logger.info(f"Temp directory: {file_count} files, {size_mb:.1f} MB")
    
    if size_mb > warn_size_mb:
        logger.warning(
            f"Temp directory size ({size_mb:.1f} MB) exceeds threshold ({warn_size_mb} MB). "
            f"Consider running cleanup or increasing threshold."
        )


# Made with Bob