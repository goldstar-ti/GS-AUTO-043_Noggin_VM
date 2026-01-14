"""
Base Processor Module

Contains common functionality shared by all object type processors:
- API request handling with retry/backoff
- Attachment downloading and validation
- Graceful shutdown handling
- Progress tracking
- Folder structure creation

Object-type-specific logic is handled by:
- Field mappings from config (see field_processor.py)
- Report templates from config (see report_generator.py)
"""

from __future__ import annotations
import requests
import json
import logging
import uuid
import hashlib
import time
import signal
import atexit
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List, Callable

logger: logging.Logger = logging.getLogger(__name__)


class GracefulShutdownHandler:
    """Handles Ctrl+C and system shutdown signals"""

    def __init__(self, db_manager: 'DatabaseConnectionManager', 
                 logger_instance: logging.Logger,
                 on_shutdown: Optional[Callable] = None) -> None:
        self.db_manager: 'DatabaseConnectionManager' = db_manager
        self.logger: logging.Logger = logger_instance
        self.shutdown_requested: bool = False
        self.force_exit: bool = False
        self.current_tip: Optional[str] = None
        self.on_shutdown: Optional[Callable] = on_shutdown

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        atexit.register(self._cleanup_on_exit)

        self.logger.info("Graceful shutdown handler initialised")

    def _signal_handler(self, signum: int, frame: Any) -> None:
        signal_name: str = "SIGINT (Ctrl+C)" if signum == signal.SIGINT else f"Signal {signum}"

        if not self.shutdown_requested:
            self.shutdown_requested = True
            self.logger.warning(f"{signal_name} received. Finishing current TIP then shutting down...")
            self.logger.warning(f"Currently processing: {self.current_tip or 'None'}")
            self.logger.warning("Press Ctrl+C again to force immediate exit")
        else:
            self.logger.error("Second shutdown signal - forcing immediate exit")
            self.force_exit = True
            self._emergency_cleanup()

    def _emergency_cleanup(self) -> None:
        self.logger.warning("Emergency cleanup initiated")
        try:
            if self.db_manager:
                self.db_manager.close_all()
        except Exception as e:
            self.logger.error(f"Error during emergency cleanup: {e}")
        
        import sys
        sys.exit(1)

    def _cleanup_on_exit(self) -> None:
        self.logger.info("Normal exit cleanup")
        if self.on_shutdown:
            try:
                self.on_shutdown()
            except Exception as e:
                self.logger.error(f"Error in shutdown callback: {e}")
        
        try:
            if self.db_manager:
                self.db_manager.close_all()
        except Exception as e:
            self.logger.error(f"Error closing database connections: {e}")

    def should_continue(self) -> bool:
        return not self.shutdown_requested

    def set_current_tip(self, tip: Optional[str]) -> None:
        self.current_tip = tip


def sanitise_filename(text: str) -> str:
    """
    Sanitise string for use in filenames.
    Allows spaces to preserve formatting like 'TA - 00014'.
    """
    if not text:
        return "unknown"
    
    # Replace illegal filename characters with underscore
    sanitised: str = re.sub(r'[<>:"/\\|?*]', '_', str(text))
    
    # Replace whitespace characters (tabs, newlines) with standard space
    sanitised = re.sub(r'[\t\r\n]+', ' ', sanitised)
    
    # Collapse multiple spaces into one
    sanitised = re.sub(r'\s+', ' ', sanitised)
    
    # Remove leading/trailing spaces or underscores
    sanitised = sanitised.strip('_ ')
    
    return sanitised[:100] if sanitised else "unknown"


def flatten_json(nested_json: Any, parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
    """Flatten nested JSON into single-level dict with concatenated keys"""
    items: List[Tuple[str, Any]] = []
    
    if isinstance(nested_json, dict):
        for k, v in nested_json.items():
            new_key: str = f"{parent_key}{sep}{k}" if parent_key else k
            items.extend(flatten_json(v, new_key, sep).items())
    elif isinstance(nested_json, list):
        for i, v in enumerate(nested_json):
            new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
            items.extend(flatten_json(v, new_key, sep).items())
    else:
        items.append((parent_key, nested_json))
    
    return dict(items)


def calculate_md5_hash(file_path: Path) -> str:
    """Calculate MD5 hash of file"""
    try:
        hash_md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating MD5 for {file_path}: {e}")
        return ""


def validate_attachment_file(file_path: Path, expected_min_size: int = 1024) -> Tuple[bool, int, Optional[str]]:
    """
    Validate downloaded attachment file
    
    Returns:
        Tuple of (is_valid, file_size_bytes, error_message)
    """
    try:
        if not file_path.exists():
            return False, 0, "File does not exist"

        file_size: int = file_path.stat().st_size

        if file_size < expected_min_size:
            return False, file_size, f"File too small ({file_size} bytes)"

        with open(file_path, 'rb') as f:
            header_bytes: bytes = f.read(10)
            if len(header_bytes) == 0:
                return False, file_size, "File appears empty"

        return True, file_size, None

    except Exception as e:
        return False, 0, f"Validation error: {e}"


class APIClient:
    """Handles API requests with retry logic and circuit breaker integration"""
    
    def __init__(self, config: 'ConfigLoader', circuit_breaker: 'CircuitBreaker') -> None:
        self.config = config
        self.circuit_breaker = circuit_breaker
        
        self.base_url: str = config.get('api', 'base_url')
        self.attachment_base_url: str = config.get('api', 'media_service_url')
        self.headers: Dict[str, str] = config.get_api_headers()
        
        self.max_retries: int = config.getint('processing', 'max_api_retries')
        self.backoff_factor: int = config.getint('processing', 'api_backoff_factor')
        self.max_backoff: int = config.getint('processing', 'api_max_backoff')
        self.timeout: int = config.getint('processing', 'api_timeout')
        self.too_many_requests_sleep: int = config.getint('processing', 'too_many_requests_sleep_time')
    
    def make_request(self, url: str, tip_value: str) -> requests.Response:
        """Make API request with exponential backoff retry logic"""
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"API request attempt {attempt + 1}/{self.max_retries} for TIP {tip_value}")
                response: requests.Response = requests.get(url, headers=self.headers, timeout=self.timeout)
                response._retry_count = attempt
                logger.debug(f"Request attempt {attempt + 1} succeeded for TIP {tip_value}")
                return response

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt == self.max_retries - 1:
                    logger.error(f"All {self.max_retries} connection attempts failed for TIP {tip_value}")
                    raise
                wait_time: float = min((self.backoff_factor ** attempt) * self.backoff_factor, self.max_backoff)
                logger.warning(f"Connection failed for TIP {tip_value}, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})")
                time.sleep(wait_time)

            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt == self.max_retries - 1:
                    logger.error(f"All {self.max_retries} timeout attempts failed for TIP {tip_value}")
                    raise
                wait_time = min((self.backoff_factor ** attempt) * self.backoff_factor, self.max_backoff)
                logger.warning(f"Request timeout for TIP {tip_value}, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})")
                time.sleep(wait_time)

            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt == self.max_retries - 1:
                    logger.error(f"Request failed permanently for TIP {tip_value}: {e}")
                    raise
                wait_time = self.backoff_factor
                logger.warning(f"Request error for TIP {tip_value}, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})")
                time.sleep(wait_time)

        if last_exception:
            raise last_exception
        raise Exception(f"Unexpected error in retry logic for TIP {tip_value}")
    
    def handle_error(self, response: requests.Response, tip_value: str, request_url: str) -> str:
        """Generate detailed error message from API response"""
        status_code: int = response.status_code

        try:
            response_text: str = response.text
            if response_text:
                try:
                    error_json: Dict[str, Any] = response.json()
                    additional_info: str = f" Response body: {json.dumps(error_json, indent=2)}"
                except json.JSONDecodeError:
                    additional_info = f" Response body: {response_text[:500]}{'...' if len(response_text) > 500 else ''}"
            else:
                additional_info = " (No response body provided)"
        except Exception:
            additional_info = " (Could not read response body)"

        error_messages = {
            401: f"Authentication failed for TIP {tip_value}. Status code: {status_code} (Unauthorised). URL: {request_url}{additional_info}",
            403: f"Access forbidden for TIP {tip_value}. Status code: {status_code} (Forbidden). URL: {request_url}{additional_info}",
            404: f"Resource not found for TIP {tip_value}. Status code: {status_code} (Not Found). URL: {request_url}{additional_info}",
            429: f"Rate limit exceeded for TIP {tip_value}. Status code: {status_code} (Too Many Requests). URL: {request_url}{additional_info}",
        }

        if status_code in error_messages:
            return error_messages[status_code]
        elif 400 <= status_code < 500:
            return f"Client error for TIP {tip_value}. Status code: {status_code}. URL: {request_url}{additional_info}"
        elif 500 <= status_code < 600:
            return f"Server error for TIP {tip_value}. Status code: {status_code}. URL: {request_url}{additional_info}"
        else:
            return f"Unexpected response for TIP {tip_value}. Status code: {status_code}. URL: {request_url}{additional_info}"


class AttachmentDownloader:
    """Handles attachment downloading with validation and database tracking"""
    
    def __init__(self, config: 'ConfigLoader', db_manager: 'DatabaseConnectionManager',
                 api_client: APIClient) -> None:
        self.config = config
        self.db_manager = db_manager
        self.api_client = api_client
        
        self.attachment_pause: int = config.getint('processing', 'attachment_pause')
        self.min_file_size: int = config.getint('processing', 'min_attachment_size', fallback=1024)
    
    def download(self, attachment_url: str, filename: str, inspection_id: str,
                attachment_tip: str, inspection_folder: Path,
                record_tip: str, attachment_sequence: int) -> Tuple[bool, int, float, Optional[str]]:
        """
        Download and validate attachment with database tracking
        
        Returns:
            Tuple of (success, retry_count, file_size_mb, error_message)
        """
        if attachment_url.startswith('/media'):
            attachment_url = attachment_url[6:]

        full_url: str = self.api_client.attachment_base_url + attachment_url
        output_path: Path = inspection_folder / filename
        temp_path: Path = output_path.with_suffix('.tmp')

        download_start: datetime = datetime.now()

        # Insert initial attachment record
        try:
            self.db_manager.execute_update(
                """
                INSERT INTO attachments (record_tip, attachment_tip, attachment_sequence, filename, 
                                        file_path, attachment_status, attachment_validation_status, download_started_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
                ON CONFLICT (record_tip, attachment_tip) DO UPDATE SET
                    attachment_status = 'downloading',
                    attachment_validation_status = 'pending',
                    download_started_at = EXCLUDED.download_started_at,
                    filename = EXCLUDED.filename,
                    file_path = EXCLUDED.file_path
                """,
                (record_tip, attachment_tip, attachment_sequence, filename, 
                 str(output_path), 'downloading', download_start)
            )
        except Exception as e:
            logger.warning(f"Could not insert attachment record: {e}")

        try:
            response = self.api_client.make_request(full_url, attachment_tip)
            retry_count: int = getattr(response, '_retry_count', 0)

            if response.status_code != 200:
                error_msg = self.api_client.handle_error(response, attachment_tip, full_url)
                self._update_attachment_failed(record_tip, attachment_tip, error_msg)
                return False, retry_count, 0, error_msg

            # Write to temp file then rename
            with open(temp_path, 'wb') as f:
                f.write(response.content)

            # Validate
            is_valid, file_size, validation_error = validate_attachment_file(temp_path, self.min_file_size)

            if not is_valid:
                temp_path.unlink(missing_ok=True)
                error_msg = f"Validation failed: {validation_error}"
                self._update_attachment_failed(record_tip, attachment_tip, error_msg)
                return False, retry_count, 0, error_msg

            # Rename temp to final
            temp_path.rename(output_path)

            # Calculate hash
            file_hash: str = calculate_md5_hash(output_path)

            download_end: datetime = datetime.now()
            download_duration: float = (download_end - download_start).total_seconds()

            # Update successful
            self.db_manager.execute_update(
                """
                UPDATE attachments SET
                    attachment_status = 'complete',
                    attachment_validation_status = 'valid',
                    file_size_bytes = %s,
                    file_hash_md5 = %s,
                    download_completed_at = %s,
                    download_duration_seconds = %s
                WHERE record_tip = %s AND attachment_tip = %s
                """,
                (file_size, file_hash, download_end, download_duration, record_tip, attachment_tip)
            )

            file_size_mb: float = file_size / (1024 * 1024)
            logger.info(f"Downloaded attachment {attachment_sequence}: {filename} ({file_size_mb:.2f} MB)")

            return True, retry_count, file_size_mb, None

        except Exception as e:
            error_msg = f"Download exception: {e}"
            logger.error(f"Attachment download failed for {inspection_id}: {error_msg}")
            temp_path.unlink(missing_ok=True)
            self._update_attachment_failed(record_tip, attachment_tip, error_msg)
            return False, 0, 0, error_msg
    
    def _update_attachment_failed(self, record_tip: str, attachment_tip: str, error_msg: str) -> None:
        """Update attachment record as failed"""
        try:
            self.db_manager.execute_update(
                """
                UPDATE attachments SET
                    attachment_status = 'failed',
                    attachment_validation_status = 'validation_failed',
                    last_error_message = %s
                WHERE record_tip = %s AND attachment_tip = %s
                """,
                (error_msg, record_tip, attachment_tip)
            )
        except Exception as e:
            logger.warning(f"Could not update attachment failure: {e}")


class FolderManager:
    """Manages folder structure creation for inspections"""
    
    def __init__(self, config: 'ConfigLoader', object_type_abbrev: str) -> None:
        self.config = config
        self.object_type_abbrev = object_type_abbrev
        self.base_path: Path = Path(config.get('paths', 'base_output_path'))
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Get folder pattern from config or use default
        output_patterns = config.get_output_patterns()
        self.folder_pattern: str = output_patterns.get('folder_pattern', 
            '{abbreviation}/{year}/{month}/{date} {inspection_id}')
        self.attachment_pattern: str = output_patterns.get('attachment_pattern',
            '{abbreviation}_{inspection_id}_{date}_{stub}_{sequence}.jpg')
        self.filename_stub: str = config.get('output', 'filename_image_stub', 
                                             fallback='photo', from_specific=True)
    
    def create_inspection_folder(self, date_str: str, inspection_id: str) -> Path:
        """Create folder structure for an inspection"""
        sanitised_id: str = sanitise_filename(inspection_id)
        
        try:
            if date_str:
                # Parse date
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                year: str = date_obj.strftime('%Y')
                month: str = date_obj.strftime('%m')
                date_formatted: str = date_obj.strftime('%Y-%m-%d')
            else:
                raise ValueError("Empty date")
        except (ValueError, AttributeError):
            year = 'unknown_year'
            month = 'unknown_month'
            date_formatted = 'unknown_date'
        
        # Apply folder pattern
        folder_name: str = self.folder_pattern.format(
            abbreviation=self.object_type_abbrev,
            year=year,
            month=month,
            date=date_formatted,
            inspection_id=sanitised_id
        )
        
        inspection_folder: Path = self.base_path / folder_name
        inspection_folder.mkdir(parents=True, exist_ok=True)
        
        return inspection_folder
    
    def construct_attachment_filename(self, inspection_id: str, date_str: str, 
                                      sequence: int) -> str:
        """Construct standardised attachment filename"""
        sanitised_id: str = sanitise_filename(inspection_id)
        
        try:
            if date_str:
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                date_formatted: str = date_obj.strftime('%Y%m%d')
            else:
                raise ValueError("Empty date")
        except (ValueError, AttributeError):
            date_formatted = 'unknown'
        
        filename: str = self.attachment_pattern.format(
            abbreviation=self.object_type_abbrev,
            inspection_id=sanitised_id,
            date=date_formatted,
            stub=self.filename_stub,
            sequence=str(sequence).zfill(3)
        )
        
        return filename


class RetryManager:
    """Manages retry logic and backoff calculations"""
    
    def __init__(self, config: 'ConfigLoader') -> None:
        self.max_retries: int = config.getint('retry', 'max_retry_attempts')
        self.backoff_multiplier: float = config.getfloat('retry', 'retry_backoff_multiplier')
        self.base_delay_minutes: int = config.getint('retry', 'base_retry_delay_minutes', fallback=5)
        self.max_delay_hours: int = config.getint('retry', 'max_retry_delay_hours', fallback=24)
    
    def calculate_next_retry_time(self, retry_count: int) -> datetime:
        """Calculate next retry time with exponential backoff"""
        if retry_count >= self.max_retries:
            # Far future = permanently failed
            return datetime.now() + timedelta(days=365 * 10)
        
        delay_minutes: float = self.base_delay_minutes * (self.backoff_multiplier ** retry_count)
        max_delay_minutes: float = self.max_delay_hours * 60
        delay_minutes = min(delay_minutes, max_delay_minutes)
        
        return datetime.now() + timedelta(minutes=delay_minutes)
    
    def should_retry(self, retry_count: int) -> bool:
        """Check if more retries are allowed"""
        return retry_count < self.max_retries


class ProgressTracker:
    """Tracks processing progress and estimates"""
    
    def __init__(self, total_count: int) -> None:
        self.total_count: int = total_count
        self.processed_count: int = 0
        self.start_time: float = time.perf_counter()
        self.last_log_time: float = self.start_time
        self.log_interval: int = 10  # seconds
    
    def increment(self) -> None:
        self.processed_count += 1
    
    def should_log_progress(self) -> bool:
        current_time = time.perf_counter()
        if current_time - self.last_log_time >= self.log_interval:
            self.last_log_time = current_time
            return True
        return False
    
    def get_progress_stats(self) -> Dict[str, Any]:
        """Get current progress statistics"""
        elapsed: float = time.perf_counter() - self.start_time
        
        if self.processed_count > 0:
            rate: float = self.processed_count / elapsed
            remaining: int = self.total_count - self.processed_count
            eta_seconds: float = remaining / rate if rate > 0 else 0
        else:
            rate = 0
            eta_seconds = 0
        
        return {
            'processed': self.processed_count,
            'total': self.total_count,
            'elapsed_seconds': elapsed,
            'rate_per_second': rate,
            'eta_seconds': eta_seconds,
            'percent_complete': (self.processed_count / self.total_count * 100) if self.total_count > 0 else 0
        }
    
    def log_progress(self) -> None:
        """Log current progress"""
        stats = self.get_progress_stats()
        
        eta_minutes: float = stats['eta_seconds'] / 60
        elapsed_minutes: float = stats['elapsed_seconds'] / 60
        
        logger.info(
            f"Progress: {stats['processed']}/{stats['total']} "
            f"({stats['percent_complete']:.1f}%) - "
            f"{stats['rate_per_second']:.2f} TIPs/sec - "
            f"Elapsed: {elapsed_minutes:.1f}m - "
            f"ETA: {eta_minutes:.1f}m"
        )
    
    def log_shutdown_summary(self, reason: str = "complete") -> None:
        """Log final summary"""
        stats = self.get_progress_stats()
        elapsed_minutes: float = stats['elapsed_seconds'] / 60
        
        logger.info("=" * 60)
        logger.info(f"PROCESSING {reason.upper()}")
        logger.info(f"Processed: {stats['processed']}/{stats['total']} TIPs")
        logger.info(f"Duration: {elapsed_minutes:.1f} minutes")
        logger.info(f"Average rate: {stats['rate_per_second']:.2f} TIPs/sec")
        logger.info("=" * 60)