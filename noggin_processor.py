""" noggin_processor.py
    Module purpose
    ---------------
    This module processes "Load Compliance Check" (LCD) inspection records by querying
    a PostgreSQL database for eligible TIP identifiers. It retrieves JSON payloads
    from a remote API, stores metadata in PostgreSQL, downloads and validates
    attachment media, and writes human-readable inspection reports and attachment
    files to disk. It includes robust retry/backoff logic, a circuit breaker to
    protect the API, and graceful shutdown handling.

    High-level behaviour
    --------------------
    - Queries the 'noggin_data' table for a batch of TIPs that are 'pending',
      'csv_imported', or eligible for retry.
    - Processing priority is strictly enforced:
      failed -> interrupted -> partial -> api_failed -> pending -> csv_imported.
    - For each TIP:
        - Checks the Circuit Breaker status before making requests.
        - Uses an endpoint template ($tip) to build the API URL and GETs the JSON.
        - Updates the existing noggin_data row with parsed response fields and meta.
        - Creates a dated folder structure and writes a formatted text payload file.
        - Downloads listed attachments, validates file integrity, computes MD5 and
          records attachment state in the attachments table.
        - Tracks errors in processing_errors and updates retry/backoff state on errors.
    - Honors graceful shutdown (SIGINT/SIGTERM) finishing the current TIP when
      possible; a second signal forces immediate exit.
    - Emits logging to both application logger and a session logger file.

    Primary public functions/classes
    -------------------------------
    - GracefulShutdownHandler(db_conn, logger_instance)
        Handles SIGINT/SIGTERM, closes DB connections on exit.
    - create_inspection_folder_structure(date_str, noggin_reference)
        Builds and creates a hierarchical path base_path/YYYY/MM/YYYY-MM-DD <id>.
    - save_formatted_payload_text_file(inspection_folder, response_data, noggin_reference)
        Writes a human-readable inspection report to a text file.
    - download_attachment(attachment_url, filename, noggin_reference, ...)
        Downloads, validates, and hashes a single attachment; updates DB records.
    - process_attachments(response_data, noggin_reference, tip_value)
        Orchestrates saving the payload file and iteratively downloading attachments.
    - insert_noggin_data_record(tip_value, response_data)
        Parses response_data and UPDATEs the existing noggin_data table record.
    - get_tips_to_process_from_database(limit=10)
        Retrieves a batch of TIPs eligible for processing based on priority logic.
    - main()
        The main processing loop: fetches a batch of TIPs from the DB, coordinates
        circuit breaker, API calls, DB updates, and attachment processing.
"""
from __future__ import annotations
import requests
import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import time
import signal
import sys
import atexit
import hashlib
from typing import Optional, List, Dict, Any, Tuple

from common import ConfigLoader, LoggerManager, DatabaseConnectionManager, HashManager, CircuitBreaker, CircuitBreakerError, UNKNOWN_TEXT

start_time: float = time.perf_counter()

config: ConfigLoader = ConfigLoader(
    'config/base_config.ini',
    'config/load_compliance_check_driver_loader_config.ini'
)

batch_session_id: str = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_batch_{str(uuid.uuid4())[:8].upper()}"

logger_manager: LoggerManager = LoggerManager(config, script_name=Path(__file__).stem)
logger_manager.configure_application_logger()
session_logger: logging.Logger = logger_manager.create_session_logger(batch_session_id)

logger: logging.Logger = logging.getLogger(__name__)

db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)
hash_manager: HashManager = HashManager(config, db_manager)
circuit_breaker: CircuitBreaker = CircuitBreaker(config)

base_url: str = config.get('api', 'base_url')
attachment_base_url: str = config.get('api', 'media_service_url')
headers: Dict[str, str] = config.get_api_headers()

base_path: Path = Path(config.get('paths', 'base_output_path'))
base_path.mkdir(parents=True, exist_ok=True)

too_many_requests_sleep_time: int = config.getint('processing', 'too_many_requests_sleep_time')
attachment_pause: int = config.getint('processing', 'attachment_pause')
max_api_retries: int = config.getint('processing', 'max_api_retries')
api_backoff_factor: int = config.getint('processing', 'api_backoff_factor')
api_max_backoff: int = config.getint('processing', 'api_max_backoff')
api_timeout: int = config.getint('processing', 'api_timeout')

show_json_payload_in_text_file: bool = config.getboolean('output', 'show_json_payload_in_text_file', from_specific=True)
show_compliance_status: bool = config.getboolean('output', 'show_compliance_status', from_specific=True)
filename_image_stub: str = config.get('output', 'filename_image_stub', from_specific=True)
unknown_response_output_text: str = config.get('output', 'unknown_response_output_text', from_specific=True)
folder_pattern: str = config.get('output', 'folder_pattern', from_specific=True)
attachment_pattern: str = config.get('output', 'attachment_pattern', from_specific=True)

abbreviation: str = config.get('object_type', 'abbreviation', from_specific=True)

object_type_config: Dict[str, str] = config.get_object_type_config()
endpoint_template: str = object_type_config['endpoint']

# Hardcoded as per requirements
object_type: str = 'LCD'

shutdown_requested: bool = False
current_tip_being_processed: Optional[str] = None

logger.info("="*80)
logger.info(f"NOGGIN PROCESSOR - {object_type}")
logger.info("="*80)
logger.info(f"Session ID:         {batch_session_id}")
logger.info(f"Object Type:        {object_type}")
logger.info(f"Abbreviation:       {abbreviation}")
logger.info(f"Base Output Path:   {base_path}")
logger.info(f"Folder Pattern:     {folder_pattern}")
logger.info(f"Attachment Pattern: {attachment_pattern}")
logger.info("="*80)

session_logger.info(f"SESSION START: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
session_logger.info(f"SESSION ID: {batch_session_id}")
session_logger.info(f"OBJECT TYPE: {object_type}")
session_logger.info("")
session_logger.info("TIMESTAMP\tTIP\tNOGGIN_REFERENCE\tATTACHMENTS_COUNT\tATTACHMENT_FILENAMES")

class GracefulShutdownHandler:
    """Handles Ctrl+C and system shutdown signals"""

    def __init__(self, db_conn: DatabaseConnectionManager, logger_instance: logging.Logger) -> None:
        self.db_conn: DatabaseConnectionManager = db_conn
        self.logger: logging.Logger = logger_instance
        self.shutdown_requested: bool = False

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        atexit.register(self._cleanup_on_exit)

        self.logger.info("Graceful shutdown handler initialised")

    def _signal_handler(self, signum: int, frame: Any) -> None:
        global shutdown_requested
        signal_name: str = "SIGINT (Ctrl+C)" if signum == signal.SIGINT else f"Signal {signum}"

        if not self.shutdown_requested:
            self.shutdown_requested = True
            shutdown_requested = True
            self.logger.warning(f"\n{signal_name} received. Finishing current TIP then shutting down...")
            self.logger.warning(f"Currently processing: {current_tip_being_processed or 'None'}")
            self.logger.warning("Press Ctrl+C again to force immediate exit")
        else:
            self.logger.error("Second shutdown signal - forcing immediate exit")
            self._emergency_cleanup()
            sys.exit(1)

    def _cleanup_on_exit(self) -> None:
        if self.db_conn:
            try:
                self.db_conn.close_all()
            except Exception as e:
                self.logger.error(f"Error during exit cleanup: {e}")

    def _emergency_cleanup(self) -> None:
        try:
            if self.db_conn:
                self.db_conn.close_all()
        except:
            pass

    def should_continue_processing(self) -> bool:
        return not self.shutdown_requested

shutdown_handler: GracefulShutdownHandler = GracefulShutdownHandler(db_manager, logger)

def sanitise_filename(text: Optional[str]) -> str:
    """Sanitise text for use in filenames"""
    if not text:
        return "unknown"
    return (text.replace(" - ", "-").replace(" ", "_").replace("/", "")
            .replace("\\", "").replace("*", "").replace("<", "")
            .replace(">", "").replace("?", "").replace("|", "").replace(":", ""))

def flatten_json(nested_json: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
    """Flatten nested JSON structure"""
    items: List[Tuple[str, Any]] = []
    for key, value in nested_json.items():
        new_key: str = f"{parent_key}{sep}{key}" if parent_key else key

        if isinstance(value, dict):
            items.extend(flatten_json(value, new_key, sep=sep).items())
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    items.extend(flatten_json(item, f"{new_key}_{i}", sep=sep).items())
                else:
                    items.append((f"{new_key}_{i}", item))
        else:
            items.append((new_key, value))
    return dict(items)

def create_inspection_folder_structure(date_str: str, noggin_reference: str) -> Path:
    """Create hierarchical folder structure for inspection using configured pattern.

    Pattern placeholders: {abbreviation}, {year}, {month}, {date}, {inspection_id}
    """
    try:
        date_obj: datetime = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        year: str = str(date_obj.year)
        month: str = f"{date_obj.month:02d}"
        formatted_date: str = date_obj.strftime('%Y-%m-%d')

        # Substitute pattern placeholders (mapping noggin_reference to inspection_id)
        folder_path: str = folder_pattern.format(
            abbreviation=abbreviation,
            year=year,
            month=month,
            date=formatted_date,
            inspection_id=noggin_reference
        )

        inspection_folder: Path = base_path / folder_path
        inspection_folder.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created inspection folder: {inspection_folder}")
        return inspection_folder
    except (ValueError, AttributeError) as e:
        logger.warning(f"Could not parse date '{date_str}': {e}")
        folder_name = f"unknown-date {noggin_reference}"
        fallback_folder: Path = base_path / abbreviation / "unknown_date" / folder_name
        fallback_folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created fallback folder: {fallback_folder}")
        return fallback_folder

def construct_attachment_filename(noggin_reference: str, date_str: str, attachment_num: int) -> str:
    """Construct attachment filename using configured pattern."""
    sanitised_id: str = sanitise_filename(noggin_reference)

    try:
        date_obj: datetime = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        date_part: str = date_obj.strftime('%Y-%m-%d')
    except (ValueError, AttributeError):
        logger.warning(f"Could not parse date '{date_str}', using 'unknown'")
        date_part = "unknown"

    filename: str = attachment_pattern.format(
        abbreviation=abbreviation,
        inspection_id=sanitised_id,
        date=date_part,
        stub=filename_image_stub,
        sequence=f"{attachment_num:03d}"
    )
    return filename

def calculate_md5_hash(file_path: Path) -> str:
    """Calculate MD5 hash of file"""
    md5_hash: hashlib._Hash = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except Exception as e:
        logger.warning(f"Could not calculate MD5 for {file_path}: {e}")
        return ""

def validate_attachment_file(file_path: Path, expected_min_size: int = 1024) -> Tuple[bool, int, Optional[str]]:
    """Validate downloaded file integrity"""
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

def save_formatted_payload_text_file(inspection_folder: Path, response_data: Dict[str, Any],
                                    noggin_reference: str) -> Optional[Path]:
    """Generate formatted text file with inspection data"""
    sanitised_ref: str = sanitise_filename(noggin_reference)
    payload_filename: str = f"{sanitised_ref}_inspection_data.txt"
    payload_path: Path = inspection_folder / payload_filename

    try:
        with open(payload_path, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write("LOAD COMPLIANCE CHECK INSPECTION REPORT\n")
            f.write(f"RECORD GENERATED: {datetime.now().strftime('%d-%m-%Y')}\n")
            f.write("="*60 + "\n\n")

            f.write(f"Noggin Reference:      {response_data.get('lcdInspectionId', unknown_response_output_text)}\n\n")
            f.write(f"Date:                  {response_data.get('date', unknown_response_output_text)}\n\n")
            f.write(f"Inspected By:          {response_data.get('inspectedBy', unknown_response_output_text)}\n\n")

            vehicle_hash: str = response_data.get('vehicle', '')
            vehicle_name: str = hash_manager.lookup_hash('vehicle', vehicle_hash, response_data.get('tip', ''), noggin_reference) if vehicle_hash else unknown_response_output_text
            f.write(f"Vehicle:               {vehicle_name}\n\n")
            f.write(f"Vehicle ID:            {response_data.get('vehicleId', unknown_response_output_text)}\n\n")

            trailer_hash: str = response_data.get('trailer', '')
            trailer_name: str = hash_manager.lookup_hash('trailer', trailer_hash, response_data.get('tip', ''), noggin_reference) if trailer_hash else unknown_response_output_text
            f.write(f"Trailer:               {trailer_name}\n\n")
            f.write(f"Trailer ID:            {response_data.get('trailerId', unknown_response_output_text)}\n\n")

            trailer2_hash: str = response_data.get('trailer2', '')
            if trailer2_hash:
                trailer2_name: str = hash_manager.lookup_hash('trailer', trailer2_hash, response_data.get('tip', ''), noggin_reference)
                f.write(f"Trailer 2:             {trailer2_name}\n\n")
                f.write(f"Trailer 2 ID:          {response_data.get('trailerId2', unknown_response_output_text)}\n\n")

            trailer3_hash: str = response_data.get('trailer3', '')
            if trailer3_hash:
                trailer3_name: str = hash_manager.lookup_hash('trailer', trailer3_hash, response_data.get('tip', ''), noggin_reference)
                f.write(f"Trailer 3:             {trailer3_name}\n\n")
                f.write(f"Trailer 3 ID:          {response_data.get('trailerId3', unknown_response_output_text)}\n\n")

            f.write(f"Job Number:            {response_data.get('jobNumber', unknown_response_output_text)}\n\n")
            f.write(f"Run Number:            {response_data.get('runNumber', unknown_response_output_text)}\n\n