""" noggin_processor.py
    Module purpose
    ---------------
    This module processes "Load Compliance Check" (LCD) inspection records from a CSV
    of TIP identifiers, retrieves their JSON payloads from a remote API, stores
    metadata in PostgreSQL, downloads and validates attachment media, and writes
    human-readable inspection reports and attachment files to disk. It includes
    robust retry/backoff logic, a circuit breaker to protect the API, and graceful
    shutdown handling.
    High-level behaviour
    --------------------
    - Reads TIPs from a CSV file (expected column header: "tip").
    - For each TIP:
        - Uses an endpoint template ($tip) to build the API URL and GETs the JSON.
        - Inserts/updates a noggin_data row with parsed response fields and meta.
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
        Handles SIGINT/SIGTERM, closes DB connections on exit, and provides a
        should_continue_processing() method to let main stop gracefully.
    - sanitise_filename(text)
        Sanitises a string for safe use in filenames (removes or replaces unsafe
        characters).
    - flatten_json(nested_json, parent_key='', sep='_')
        Flattens arbitrarily nested JSON (dicts/lists) into a single-level dict with
        concatenated keys suitable for CSV or tabular storage.
    - create_inspection_folder_structure(date_str, lcd_inspection_id)
        Builds and creates a hierarchical path base_path/YYYY/MM/YYYY-MM-DD <id>
        for storing inspection payloads/attachments; falls back to base_path/unknown_date.
    - construct_attachment_filename(lcd_inspection_id, date_str, attachment_num)
        Returns a standardized filename for attachments including a sanitized inspection
        id, date (YYYYMMDD or "unknown") and zero-padded sequence number.
    - calculate_md5_hash(file_path)
        Computes and returns the MD5 hex digest for the specified file path.
        Returns empty string on error.
    - validate_attachment_file(file_path, expected_min_size=1024)
        Performs basic integrity checks on a downloaded file: existence, minimum
        size threshold, and a small header read to detect emptiness. Returns
        (is_valid, file_size_bytes, error_message).
    - save_formatted_payload_text_file(inspection_folder, response_data, lcd_inspection_id)
        Writes a human-readable inspection report (and optionally the full JSON
        payload) to a text file inside inspection_folder. Uses hash_manager to
        resolve hashed fields to human-readable names where available. Returns the
        saved file Path or None on I/O error.
    - make_api_request(url, headers, tip_value, max_retries=5, backoff_factor=2,
                    timeout=30, max_backoff=60)
        Performs a GET with exponential backoff and retries on transient
        connection/timeout errors. Attaches a private _retry_count attribute to the
        returned Response for bookkeeping.
    - handle_api_error(response, tip_value, request_url)
        Produces a detailed, human-friendly error string for logging and DB storage
        based on HTTP response code and body.
    - download_attachment(attachment_url, filename, lcd_inspection_id, attachment_tip,
                        inspection_folder, record_tip, attachment_sequence)
        Downloads a single attachment to disk (temporary .tmp file -> final rename),
        validates it, computes MD5, updates / inserts attachment row(s) and any
        related processing_errors. Returns a tuple:
        (success: bool, retry_count: int, file_size_mb: float, error_msg: Optional[str]).
    - process_attachments(response_data, lcd_inspection_id, tip_value)
        Orchestrates saving the payload file, creating the folder, iteratively
        downloading and validating attachments, updating noggin_data status fields
        (complete/partial/failed/interrupted) and logging a per-session record.
    - insert_noggin_data_record(tip_value, response_data)
        Parses response_data into typed fields (inspection_date, hashes, names,
        load_compliance, $meta etc.) and INSERTs or UPDATEs the noggin_data table.
        Also records the raw API payload and meta JSON for traceability.
    - calculate_next_retry_time(retry_count)
        Computes an exponential backoff next_retry_at datetime based on configured
        retry settings. Returns a datetime far in the future when retry_count
        exceeds configured max.
    - get_tips_to_process_from_database(limit=10)
        Convenience DB query that returns TIPs considered eligible for processing
        according to retry/backoff rules and processing_status priorities.
    - mark_permanently_failed(tip_value)
        Marks a TIP as permanently failed after max retries are exhausted.
    - should_process_tip(tip_value)
        Inspect the noggin_data record (if present) and determines whether the TIP
        should be processed now. Returns (should_process: bool, current_retry_count: Optional[int]).
    - get_total_tip_count(tip_csv_file_path)
        Counts valid (non-empty) TIPs in the CSV file for progress estimates.
    - update_progress_tracking(processed_count, total_count, start_time_val)
        Logs a progress update with TIPs/sec and ETA.
    - log_shutdown_summary(processed_count, total_count, start_time_val, reason="manual")
        Logs an overall shutdown summary including elapsed time and estimated
        remaining duration.
    - main()
        The main processing loop: reads tip.csv, iterates rows, coordinates
        circuit breaker interactions, API calling, DB updates, attachment processing,
        retries/backoff and graceful shutdown. Returns number of TIPs processed.
    Configuration and dependencies
    ------------------------------
    - Requires a ConfigLoader instance populated from:
        'config/base_config.ini' and 'config/load_compliance_check_driver_loader_config.ini'
    Expected config sections/keys used in this module (examples):
        - [api]: base_url, media_service_url
        - [processing]: too_many_requests_sleep_time, attachment_pause, max_api_retries,
                        api_backoff_factor, api_max_backoff, api_timeout
        - [output]: show_json_payload_in_text_file, show_compliance_status,
                    filename_image_stub, unknown_response_output_text
        - [paths]: base_output_path
        - [retry]: max_retry_attempts, retry_backoff_multiplier
        - object_type mapping via config.get_object_type_config()
    - Relies on the following helper classes from common:
        ConfigLoader, LoggerManager, DatabaseConnectionManager, HashManager,
        CircuitBreaker, CircuitBreakerError
    - External libraries used:
        requests, psycopg2 (indirectly via DatabaseConnectionManager), standard
        library modules (json, logging, pathlib, datetime, uuid, time, signal, sys,
        atexit, hashlib, typing, csv).
    Database schema expectations
    ---------------------------
    This module expects the following tables and important columns (non-exhaustive):
    - noggin_data
        - tip (primary key)
        - object_type, inspection_date, lcd_inspection_id, coupling_id
        - inspected_by, vehicle_hash, vehicle, vehicle_id, trailer_hash, trailer, trailer_id, ...
        - load_compliance, processing_status, last_error_message
        - retry_count, next_retry_at, last_retry_at, csv_imported_at
        - total_attachments, completed_attachment_count, all_attachments_complete
        - api_meta_created_date, api_meta_modified_date, api_meta_* fields
        - api_payload_raw, api_meta_raw, updated_at, permanently_failed, has_unknown_hashes
    - attachments
        - record_tip, attachment_tip (unique constraint)
        - attachment_sequence, filename, file_path
        - attachment_status ('downloading', 'complete', 'failed', ...)
        - attachment_validation_status ('not_validated', 'valid', 'validation_failed', ...)
        - file_size_bytes, file_hash_md5
        - download_started_at, download_completed_at, download_duration_seconds
        - validation_error_message, last_error_message
    - processing_errors
        - tip, error_type, error_message, error_details (JSON/text), created_at
    Side effects and filesystem behavior
    -----------------------------------
    - Writes per-inspection directories under configured base_output_path with
    subfolders year/month and a folder named "<YYYY-MM-DD> <lcd_inspection_id>".
    - Writes a human-readable inspection data text file (and optionally full JSON).
    - Downloads attachments into the inspection folder; temporary files use .tmp
    suffix until validation and rename succeed.
    - Uses session-specific logging via LoggerManager to write a session log with a
    header and per-record lines.
    Important operational notes
    ---------------------------
    - Circuit breaker: before making API calls circuit_breaker.before_request() is
    called; failures are recorded via circuit_breaker.record_failure() and a
    successful call invokes circuit_breaker.record_success(). The circuit breaker
    may prevent retries to avoid cascading failures.
    - Retries/backoff: API-level transient errors are retried with exponential
    backoff. Permanent HTTP errors (4xx/5xx) are stored in DB and the TIP is
    scheduled for future retry based on calculate_next_retry_time().
    - Graceful shutdown: the first SIGINT/SIGTERM will set an internal flag so the
    script finishes the current TIP and stops taking new TIPs. A second signal
    forces immediate cleanup and exit.
    - Concurrency: the module is written for single-process execution. If multiple
    workers/processes operate on the same DB, the schema must handle upserts and
    conflicts appropriately (the code uses ON CONFLICT for key operations).
    - Validation thresholds: validate_attachment_file() uses a default minimum file
    size (1024 bytes). Adjust this threshold via the function parameters if the
    media service produces smaller-but-valid files.
    Exit codes
    ----------
    - main() returns 1 when fatal startup errors occur (missing CSV or CSV format).
    - When executed as __main__, the script logs status and exits normally (0) on
    success; unexpected exceptions are re-raised after logging.
    Example usage
    -------------
    - Run from the system environment where config files and tip.csv are available:
        python noggin_processor.py
    - Ensure config files contain correct API endpoints, DB connection details (used
    by DatabaseConnectionManager), and output path permissions.
    Extensibility suggestions
    -------------------------
    - Abstract retry/backoff configuration to be injected for easier unit testing.
    - Replace direct requests.get calls with a wrapper interface to facilitate
    mocking in tests.
    - Add more granular attachment type detection (content-type / magic bytes)
    beyond basic size/header checks if required.
    Security and privacy
    --------------------
    - Ensure access tokens or API credentials used by headers are kept secure and not
    logged. This module attempts to avoid logging full payloads unless explicitly
    enabled by configuration (show_json_payload_in_text_file).
    - Attachment storage may contain sensitive images; secure file permissions and
    accessible output path accordingly.
    Limitations
    -----------
    - The module assumes stable database connectivity and that the DatabaseConnectionManager
    implements execute_query_dict and execute_update semantics shown. Errors closing
    DB connections are logged but not fatal during shutdown cleanup.
    - Date parsing uses datetime.fromisoformat after normalizing 'Z' to '+00:00';
    non-ISO date formats may be treated as unknown.
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
object_type: str = object_type_config['object_type']

shutdown_requested: bool = False
current_tip_being_processed: Optional[str] = None

logger.info("="*80)
logger.info(f"NOGGIN PROCESSOR - {object_type.upper()}")
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
session_logger.info("TIMESTAMP\tTIP\tINSPECTION_ID\tATTACHMENTS_COUNT\tATTACHMENT_FILENAMES")

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

def create_inspection_folder_structure(date_str: str, inspection_id: str) -> Path:
    """Create hierarchical folder structure for inspection using configured pattern.

    Pattern placeholders: {abbreviation}, {year}, {month}, {date}, {inspection_id}

    Args:
        date_str: Date string in ISO format (e.g. "2023-05-20" or "2023-05-20Z")
        inspection_id: Unique identifier for the inspection

    Returns:
        Path object pointing to the created inspection folder
    """
    try:
        date_obj: datetime = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        year: str = str(date_obj.year)
        month: str = f"{date_obj.month:02d}"
        formatted_date: str = date_obj.strftime('%Y-%m-%d')

        # Substitute pattern placeholders
        folder_path: str = folder_pattern.format(
            abbreviation=abbreviation,
            year=year,
            month=month,
            date=formatted_date,
            inspection_id=inspection_id
        )

        inspection_folder: Path = base_path / folder_path
        inspection_folder.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created inspection folder: {inspection_folder}")
        return inspection_folder
    except (ValueError, AttributeError) as e:
        logger.warning(f"Could not parse date '{date_str}': {e}")
        folder_name = f"unknown-date {inspection_id}"
        fallback_folder: Path = base_path / abbreviation / "unknown_date" / folder_name
        fallback_folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created fallback folder: {fallback_folder}")
        return fallback_folder

def construct_attachment_filename(inspection_id: str, date_str: str, attachment_num: int) -> str:
    """Construct attachment filename using configured pattern.
    
    Pattern placeholders: {abbreviation}, {inspection_id}, {date}, {stub}, {sequence}
    """
    sanitised_id: str = sanitise_filename(inspection_id)

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
                                    lcd_inspection_id: str) -> Optional[Path]:
    """Generate formatted text file with inspection data"""
    sanitised_lcd_id: str = sanitise_filename(lcd_inspection_id)
    payload_filename: str = f"{sanitised_lcd_id}_inspection_data.txt"
    payload_path: Path = inspection_folder / payload_filename

    try:
        with open(payload_path, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write("LOAD COMPLIANCE CHECK INSPECTION REPORT\n")
            f.write(f"RECORD GENERATED: {datetime.now().strftime('%d-%m-%Y')}\n")
            f.write("="*60 + "\n\n")

            f.write(f"LCD Inspection ID:     {response_data.get('lcdInspectionId', unknown_response_output_text)}\n\n")
            f.write(f"Date:                  {response_data.get('date', unknown_response_output_text)}\n\n")
            f.write(f"Inspected By:          {response_data.get('inspectedBy', unknown_response_output_text)}\n\n")

            vehicle_hash: str = response_data.get('vehicle', '')
            vehicle_name: str = hash_manager.lookup_hash('vehicle', vehicle_hash, response_data.get('tip', ''), lcd_inspection_id) if vehicle_hash else unknown_response_output_text
            f.write(f"Vehicle:               {vehicle_name}\n\n")
            f.write(f"Vehicle ID:            {response_data.get('vehicleId', unknown_response_output_text)}\n\n")

            trailer_hash: str = response_data.get('trailer', '')
            trailer_name: str = hash_manager.lookup_hash('trailer', trailer_hash, response_data.get('tip', ''), lcd_inspection_id) if trailer_hash else unknown_response_output_text
            f.write(f"Trailer:               {trailer_name}\n\n")
            f.write(f"Trailer ID:            {response_data.get('trailerId', unknown_response_output_text)}\n\n")

            trailer2_hash: str = response_data.get('trailer2', '')
            if trailer2_hash:
                trailer2_name: str = hash_manager.lookup_hash('trailer', trailer2_hash, response_data.get('tip', ''), lcd_inspection_id)
                f.write(f"Trailer 2:             {trailer2_name}\n\n")
                f.write(f"Trailer 2 ID:          {response_data.get('trailerId2', unknown_response_output_text)}\n\n")

            trailer3_hash: str = response_data.get('trailer3', '')
            if trailer3_hash:
                trailer3_name: str = hash_manager.lookup_hash('trailer', trailer3_hash, response_data.get('tip', ''), lcd_inspection_id)
                f.write(f"Trailer 3:             {trailer3_name}\n\n")
                f.write(f"Trailer 3 ID:          {response_data.get('trailerId3', unknown_response_output_text)}\n\n")

            f.write(f"Job Number:            {response_data.get('jobNumber', unknown_response_output_text)}\n\n")
            f.write(f"Run Number:            {response_data.get('runNumber', unknown_response_output_text)}\n\n")
            f.write(f"Driver/Loader Name:    {response_data.get('driverLoaderName', unknown_response_output_text)}\n\n")

            dept_hash: str = response_data.get('whichDepartmentDoesTheLoadBelongTo', '')
            dept_name: str = hash_manager.lookup_hash('department', dept_hash, response_data.get('tip', ''), lcd_inspection_id) if dept_hash else unknown_response_output_text
            f.write(f"Department:            {dept_name}\n\n")

            team_hash: str = response_data.get('team', '')
            team_name: str = hash_manager.lookup_hash('team', team_hash, response_data.get('tip', ''), lcd_inspection_id) if team_hash else unknown_response_output_text
            f.write(f"Team:                  {team_name}\n\n")

            if show_compliance_status:
                compliant_yes: bool = response_data.get('isYourLoadCompliantWithTheLoadRestraintGuide2004Ye', False)
                compliant_no: bool = response_data.get('isYourLoadCompliantWithTheLoadRestraintGuide2004No', False)
                if compliant_yes:
                    f.write("Load Compliance:       COMPLIANT\n\n")
                elif compliant_no:
                    f.write("Load Compliance:       NON-COMPLIANT\n\n")
                else:
                    f.write(f"Load Compliance:       {unknown_response_output_text}\n\n")

            straps_value = response_data.get('straps')
            if straps_value is not None:
                f.write(f"Straps:                {straps_value}\n\n")
                no_of_straps = response_data.get('noOfStraps', UNKNOWN_TEXT)
                f.write(f"Number of Straps:      {no_of_straps}\n\n")

            chains_value = response_data.get('chains')
            if chains_value is not None:
                f.write(f"Chains:                {chains_value}\n\n")

            mass_value = response_data.get('mass', UNKNOWN_TEXT)
            f.write(f"Mass:                  {mass_value}\n\n")

            attachment_count: int = len(response_data.get('attachments', []))
            f.write(f"Attachments:           {attachment_count}\n\n")

            if show_json_payload_in_text_file:
                f.write("-"*60 + "\n")
                f.write("COMPLETE TECHNICAL DATA (JSON FORMAT)\n")
                f.write("-"*60 + "\n\n")
                json.dump(response_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved formatted payload to: {payload_path}")
        return payload_path

    except IOError as e:
        logger.error(f"IOError saving payload {payload_path}: {e}", exc_info=True)
        return None

def make_api_request(url: str, headers: Dict[str, str], tip_value: str,
                    max_retries: int = 5, backoff_factor: int = 2,
                    timeout: int = 30, max_backoff: int = 60) -> requests.Response:
    """Make API request with exponential backoff retry logic"""
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            logger.debug(f"API request attempt {attempt + 1}/{max_retries} for TIP {tip_value}")
            response: requests.Response = requests.get(url, headers=headers, timeout=timeout)
            response._retry_count = attempt
            logger.debug(f"Request attempt {attempt + 1} succeeded for TIP {tip_value}")
            return response

        except requests.exceptions.ConnectionError as connection_error:
            last_exception = connection_error

            if attempt == max_retries - 1:
                logger.error(f"All {max_retries} connection attempts failed for TIP {tip_value}", exc_info=True)
                raise connection_error

            wait_time: float = min((backoff_factor ** attempt) * backoff_factor, max_backoff)
            logger.warning(f"Connection failed for TIP {tip_value}, retrying in {wait_time}s... "
                          f"(attempt {attempt + 1}/{max_retries})")
            time.sleep(wait_time)

        except requests.exceptions.Timeout as timeout_error:
            last_exception = timeout_error

            if attempt == max_retries - 1:
                logger.error(f"All {max_retries} timeout attempts failed for TIP {tip_value}", exc_info=True)
                raise timeout_error

            wait_time = min((backoff_factor ** attempt) * backoff_factor, max_backoff)
            logger.warning(f"Request timeout for TIP {tip_value}, retrying in {wait_time}s... "
                          f"(attempt {attempt + 1}/{max_retries})")
            time.sleep(wait_time)

        except requests.exceptions.RequestException as request_error:
            last_exception = request_error

            if attempt == max_retries - 1:
                logger.error(f"Request failed permanently for TIP {tip_value}: {str(request_error)}", exc_info=True)
                raise request_error

            wait_time = backoff_factor
            logger.warning(f"Request error for TIP {tip_value}, retrying in {wait_time}s... "
                          f"(attempt {attempt + 1}/{max_retries})")
            time.sleep(wait_time)

    if last_exception:
        raise last_exception
    else:
        raise Exception(f"Unexpected error in retry logic for TIP {tip_value}")

def handle_api_error(response: requests.Response, tip_value: str, request_url: str) -> str:
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

    if status_code == 401:
        error_message: str = (f"Authentication failed for TIP {tip_value}. "
                             f"Status code: {status_code} (Unauthorised). "
                             f"The access token is missing or invalid. "
                             f"URL: {request_url}{additional_info}")

    elif status_code == 403:
        error_message = (f"Access forbidden for TIP {tip_value}. "
                        f"Status code: {status_code} (Forbidden). "
                        f"You don't have permission to access this resource. "
                        f"URL: {request_url}{additional_info}")

    elif status_code == 404:
        error_message = (f"Resource not found for TIP {tip_value}. "
                        f"Status code: {status_code} (Not Found). "
                        f"The requested object does not exist. "
                        f"URL: {request_url}{additional_info}")

    elif status_code == 429:
        error_message = (f"Rate limit exceeded for TIP {tip_value}. "
                        f"Status code: {status_code} (Too Many Requests). "
                        f"URL: {request_url}{additional_info}")

    elif 400 <= status_code < 500:
        error_message = (f"Client error for TIP {tip_value}. "
                        f"Status code: {status_code}. "
                        f"URL: {request_url}{additional_info}")

    elif 500 <= status_code < 600:
        error_message = (f"Server error for TIP {tip_value}. "
                        f"Status code: {status_code}. "
                        f"URL: {request_url}{additional_info}")

    else:
        error_message = (f"Unexpected response for TIP {tip_value}. "
                        f"Status code: {status_code}. "
                        f"URL: {request_url}{additional_info}")

    return error_message

def download_attachment(attachment_url: str, filename: str, lcd_inspection_id: str,
                       attachment_tip: str, inspection_folder: Path,
                       record_tip: str, attachment_sequence: int) -> Tuple[bool, int, float, Optional[str]]:
    """Download and validate attachment with database tracking"""
    if attachment_url.startswith('/media'):
        attachment_url = attachment_url[6:]

    full_url: str = attachment_base_url + attachment_url
    output_path: Path = inspection_folder / filename
    temp_path: Path = output_path.with_suffix('.tmp')

    existing_attachment: List[Dict[str, Any]] = db_manager.execute_query_dict(
        "SELECT attachment_status, file_size_bytes FROM attachments WHERE record_tip = %s AND attachment_tip = %s",
        (record_tip, attachment_tip)
    )

    if existing_attachment and existing_attachment[0]['attachment_status'] == 'complete':
        if output_path.exists():
            is_valid, file_size, error_msg = validate_attachment_file(output_path)
            if is_valid:
                file_size_mb: float = file_size / (1024 * 1024)
                logger.info(f"Skipping existing valid attachment: {filename} ({file_size_mb:.2f} MB)")
                return True, 0, file_size_mb, None

    download_start_time: float = time.perf_counter()
    logger.info(f"Downloading {lcd_inspection_id}: {filename}")

    db_manager.execute_update(
        """
        INSERT INTO attachments (
            record_tip, attachment_tip, attachment_sequence, filename, file_path,
            attachment_status, attachment_validation_status, download_started_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (record_tip, attachment_tip)
        DO UPDATE SET
            attachment_status = EXCLUDED.attachment_status,
            download_started_at = EXCLUDED.download_started_at
        """,
        (record_tip, attachment_tip, attachment_sequence, filename, str(output_path.resolve()),
         'downloading', 'not_validated', datetime.now())
    )

    try:
        response: requests.Response = make_api_request(full_url, headers, f"attachment {filename}", timeout=60)
        retry_count: int = getattr(response, '_retry_count', 0)

        if response.status_code == 200:
            with open(temp_path, 'wb') as f:
                f.write(response.content)

            is_valid, file_size, validation_error = validate_attachment_file(temp_path)

            if is_valid:
                temp_path.rename(output_path)

                file_hash: str = calculate_md5_hash(output_path)
                download_duration: float = time.perf_counter() - download_start_time
                file_size_mb = file_size / (1024 * 1024)

                db_manager.execute_update(
                    """
                    UPDATE attachments
                    SET attachment_status = %s,
                        attachment_validation_status = %s,
                        file_size_bytes = %s,
                        file_hash_md5 = %s,
                        download_completed_at = %s,
                        download_duration_seconds = %s
                    WHERE record_tip = %s AND attachment_tip = %s
                    """,
                    ('complete', 'valid', file_size, file_hash, datetime.now(),
                     round(download_duration, 2), record_tip, attachment_tip)
                )

                logger.info(f"Downloaded: {filename} ({file_size_mb:.2f} MB) in {download_duration:.2f}s")
                return True, retry_count, file_size_mb, None
            else:
                if temp_path.exists():
                    temp_path.unlink()

                error_msg: str = f"Validation failed: {validation_error}"
                logger.error(f"Download validation failed: {error_msg}")

                db_manager.execute_update(
                    """
                    UPDATE attachments
                    SET attachment_status = %s,
                        attachment_validation_status = %s,
                        validation_error_message = %s,
                        last_error_message = %s
                    WHERE record_tip = %s AND attachment_tip = %s
                    """,
                    ('failed', 'validation_failed', validation_error, error_msg, record_tip, attachment_tip)
                )

                db_manager.execute_update(
                    """
                    INSERT INTO processing_errors (tip, error_type, error_message, error_details)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (record_tip, 'attachment_failed', error_msg, json.dumps({
                        'filename': filename,
                        'attachment_tip': attachment_tip,
                        'validation_error': validation_error
                    }))
                )

                return False, retry_count, 0, error_msg
        else:
            if temp_path.exists():
                temp_path.unlink()

            error_msg = f"HTTP {response.status_code}"
            download_duration = time.perf_counter() - download_start_time
            error_details: str = handle_api_error(response, f"attachment {filename}", full_url)
            logger.error(f"Download failed: {error_details}")

            db_manager.execute_update(
                """
                UPDATE attachments
                SET attachment_status = %s,
                    last_error_message = %s
                WHERE record_tip = %s AND attachment_tip = %s
                """,
                ('failed', error_msg, record_tip, attachment_tip)
            )

            db_manager.execute_update(
                """
                INSERT INTO processing_errors (tip, error_type, error_message, error_details)
                VALUES (%s, %s, %s, %s)
                """,
                (record_tip, 'attachment_failed', error_msg, json.dumps({
                    'filename': filename,
                    'attachment_tip': attachment_tip,
                    'http_status': response.status_code,
                    'url': full_url
                }))
            )

            return False, retry_count, 0, error_msg

    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()

        error_msg = f"Exception: {str(e)}"
        download_duration = time.perf_counter() - download_start_time
        logger.error(f"Download exception: {filename} - {error_msg}", exc_info=True)

        db_manager.execute_update(
            """
            UPDATE attachments
            SET attachment_status = %s,
                last_error_message = %s
            WHERE record_tip = %s AND attachment_tip = %s
            """,
            ('failed', error_msg, record_tip, attachment_tip)
        )

        db_manager.execute_update(
            """
            INSERT INTO processing_errors (tip, error_type, error_message, error_details)
            VALUES (%s, %s, %s, %s)
            """,
            (record_tip, 'attachment_failed', error_msg, json.dumps({
                'filename': filename,
                'attachment_tip': attachment_tip,
                'exception': str(e)
            }))
        )

        return False, 0, 0, error_msg

def process_attachments(response_data: Dict[str, Any], lcd_inspection_id: str, tip_value: str) -> None:
    """Process all attachments for an inspection with database tracking"""
    global shutdown_requested

    if shutdown_requested:
        logger.warning(f"Shutdown requested during {lcd_inspection_id}")
        db_manager.execute_update(
            "UPDATE noggin_data SET processing_status = %s WHERE tip = %s",
            ('interrupted', tip_value)
        )
        return

    processing_start_time: float = time.perf_counter()

    date_str: str = response_data.get('date', '')
    inspection_folder: Path = create_inspection_folder_structure(date_str, lcd_inspection_id)
    save_formatted_payload_text_file(inspection_folder, response_data, lcd_inspection_id)

    if 'attachments' not in response_data or not response_data['attachments']:
        processing_end_time: float = time.perf_counter()
        processing_duration: float = processing_end_time - processing_start_time

        logger.info(f"No attachments found for {lcd_inspection_id}")
        session_logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\t{tip_value}\t{lcd_inspection_id}\t0\tNONE")

        db_manager.execute_update(
            """
            UPDATE noggin_data
            SET processing_status = %s,
                total_attachments = 0,
                completed_attachment_count = 0,
                all_attachments_complete = TRUE
            WHERE tip = %s
            """,
            ('complete', tip_value)
        )
        return

    attachments: List[str] = response_data['attachments']
    logger.info(f"Processing {len(attachments)} attachments for {lcd_inspection_id}")

    db_manager.execute_update(
        "UPDATE noggin_data SET total_attachments = %s WHERE tip = %s",
        (len(attachments), tip_value)
    )

    successful_downloads: int = 0
    attachment_filenames: List[str] = []
    total_attachment_retries: int = 0
    total_file_size_mb: float = 0.0

    for i, attachment_url in enumerate(attachments, 1):
        if shutdown_requested:
            logger.warning(f"Shutdown during attachment {i}/{len(attachments)} for {lcd_inspection_id}")
            break

        attachment_tip: str = attachment_url.split('tip=')[-1] if 'tip=' in attachment_url else 'unknown'
        filename: str = construct_attachment_filename(lcd_inspection_id, date_str, i)

        success, retry_count, file_size_mb, error_msg = download_attachment(
            attachment_url, filename, lcd_inspection_id, attachment_tip,
            inspection_folder, tip_value, i
        )

        total_attachment_retries += retry_count

        if success:
            successful_downloads += 1
            attachment_filenames.append(filename)
            total_file_size_mb += file_size_mb

        if attachment_pause > 0 and i < len(attachments):
            logger.debug(f"Pausing {attachment_pause}s before next attachment")
            time.sleep(attachment_pause)

    processing_end_time = time.perf_counter()
    processing_duration = processing_end_time - processing_start_time

    if shutdown_requested:
        final_status: str = 'interrupted'
    elif successful_downloads == len(attachments):
        final_status = 'complete'
    elif successful_downloads > 0:
        final_status = 'partial'
    else:
        final_status = 'failed'

    db_manager.execute_update(
        """
        UPDATE noggin_data
        SET processing_status = %s
        WHERE tip = %s
        """,
        (final_status, tip_value)
    )

    logger.info(f"Inspection complete for {lcd_inspection_id}: {successful_downloads}/{len(attachments)} attachments")

    attachment_names_str: str = ";".join(attachment_filenames) if attachment_filenames else "FAILED"
    session_logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\t{tip_value}\t{lcd_inspection_id}\t{successful_downloads}\t{attachment_names_str}")

def insert_noggin_data_record(tip_value: str, response_data: Dict[str, Any]) -> None:
    """Insert or update noggin_data record with API response"""
    meta: Dict[str, Any] = response_data.get('$meta', {})

    lcd_inspection_id: Optional[str] = response_data.get('lcdInspectionId')
    coupling_id: Optional[str] = response_data.get('couplingId')

    inspection_date_str: Optional[str] = response_data.get('date')
    inspection_date: Optional[datetime] = None
    if inspection_date_str:
        try:
            inspection_date = datetime.fromisoformat(inspection_date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            logger.warning(f"Could not parse date: {inspection_date_str}")

    vehicle_hash: Optional[str] = response_data.get('vehicle')
    vehicle: Optional[str] = hash_manager.lookup_hash('vehicle', vehicle_hash, tip_value, lcd_inspection_id) if vehicle_hash else None
    if vehicle_hash:
        vehicle = hash_manager.lookup_hash('vehicle', vehicle_hash, tip_value, lcd_inspection_id)
        hash_manager.update_lookup_type_if_unknown(vehicle_hash, 'vehicle')

    trailer_hash: Optional[str] = response_data.get('trailer')
    trailer: Optional[str] = hash_manager.lookup_hash('trailer', trailer_hash, tip_value, lcd_inspection_id) if trailer_hash else None
    if trailer_hash:
        trailer = hash_manager.lookup_hash('trailer', trailer_hash, tip_value, lcd_inspection_id)
        hash_manager.update_lookup_type_if_unknown(trailer_hash, 'trailer')

    trailer2_hash: Optional[str] = response_data.get('trailer2')
    trailer2: Optional[str] = hash_manager.lookup_hash('trailer', trailer2_hash, tip_value, lcd_inspection_id) if trailer2_hash else None
    if trailer2_hash:
        trailer2 = hash_manager.lookup_hash('trailer', trailer2_hash, tip_value, lcd_inspection_id)
        hash_manager.update_lookup_type_if_unknown(trailer2_hash, 'trailer')
        
    trailer3_hash: Optional[str] = response_data.get('trailer3')
    trailer3: Optional[str] = hash_manager.lookup_hash('trailer', trailer3_hash, tip_value, lcd_inspection_id) if trailer3_hash else None
    if trailer3_hash:
        trailer3 = hash_manager.lookup_hash('trailer', trailer3_hash, tip_value, lcd_inspection_id)
        hash_manager.update_lookup_type_if_unknown(trailer3_hash, 'trailer')
        
    department_hash: Optional[str] = response_data.get('whichDepartmentDoesTheLoadBelongTo')
    department: Optional[str] = hash_manager.lookup_hash('department', department_hash, tip_value, lcd_inspection_id) if department_hash else None
    if department_hash:
        department = hash_manager.lookup_hash('department', department_hash, tip_value, lcd_inspection_id)
        hash_manager.update_lookup_type_if_unknown(department_hash, 'department')

    team_hash: Optional[str] = response_data.get('team')
    team: Optional[str] = hash_manager.lookup_hash('team', team_hash, tip_value, lcd_inspection_id) if team_hash else None
    if team_hash:
        team = hash_manager.lookup_hash('team', team_hash, tip_value, lcd_inspection_id)
        hash_manager.update_lookup_type_if_unknown(team_hash, 'team')

    compliant_yes: bool = response_data.get('isYourLoadCompliantWithTheLoadRestraintGuide2004Ye', False)
    compliant_no: bool = response_data.get('isYourLoadCompliantWithTheLoadRestraintGuide2004No', False)
    if compliant_yes:
        load_compliance: str = 'COMPLIANT'
    elif compliant_no:
        load_compliance = 'NON-COMPLIANT'
    else:
        load_compliance = 'UNKNOWN'

    has_unknown: bool = any([
        vehicle and vehicle.startswith('Unknown'),
        trailer and trailer.startswith('Unknown'),
        trailer2 and trailer2.startswith('Unknown'),
        trailer3 and trailer3.startswith('Unknown'),
        department and department.startswith('Unknown'),
        team and team.startswith('Unknown')
    ])

    api_meta_created: Optional[datetime] = None
    api_meta_modified: Optional[datetime] = None
    if meta.get('createdDate'):
        try:
            api_meta_created = datetime.fromisoformat(meta['createdDate'].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            pass
    if meta.get('modifiedDate'):
        try:
            api_meta_modified = datetime.fromisoformat(meta['modifiedDate'].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            pass

    parent_array: Optional[List[str]] = meta.get('parent')

    db_manager.execute_update(
        """
        INSERT INTO noggin_data (
            tip, object_type, inspection_date, lcd_inspection_id, coupling_id,
            inspected_by, vehicle_hash, vehicle, vehicle_id,
            trailer_hash, trailer, trailer_id,
            trailer2_hash, trailer2, trailer2_id,
            trailer3_hash, trailer3, trailer3_id,
            job_number, run_number, driver_loader_name,
            department_hash, department, team_hash, team,
            load_compliance, processing_status, has_unknown_hashes,
            total_attachments, csv_imported_at,
            straps, no_of_straps, chains, mass,
            api_meta_created_date, api_meta_modified_date,
            api_meta_security, api_meta_type, api_meta_tip,
            api_meta_sid, api_meta_branch, api_meta_parent,
            api_meta_errors, api_meta_raw, api_payload_raw, raw_json
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (tip) DO UPDATE SET
            object_type = EXCLUDED.object_type,
            inspection_date = EXCLUDED.inspection_date,
            lcd_inspection_id = EXCLUDED.lcd_inspection_id,
            coupling_id = EXCLUDED.coupling_id,
            inspected_by = EXCLUDED.inspected_by,
            vehicle_hash = EXCLUDED.vehicle_hash,
            vehicle = EXCLUDED.vehicle,
            vehicle_id = EXCLUDED.vehicle_id,
            trailer_hash = EXCLUDED.trailer_hash,
            trailer = EXCLUDED.trailer,
            trailer_id = EXCLUDED.trailer_id,
            trailer2_hash = EXCLUDED.trailer2_hash,
            trailer2 = EXCLUDED.trailer2,
            trailer2_id = EXCLUDED.trailer2_id,
            trailer3_hash = EXCLUDED.trailer3_hash,
            trailer3 = EXCLUDED.trailer3,
            trailer3_id = EXCLUDED.trailer3_id,
            job_number = EXCLUDED.job_number,
            run_number = EXCLUDED.run_number,
            driver_loader_name = EXCLUDED.driver_loader_name,
            department_hash = EXCLUDED.department_hash,
            department = EXCLUDED.department,
            team_hash = EXCLUDED.team_hash,
            team = EXCLUDED.team,
            load_compliance = EXCLUDED.load_compliance,
            processing_status = EXCLUDED.processing_status,
            has_unknown_hashes = EXCLUDED.has_unknown_hashes,
            total_attachments = EXCLUDED.total_attachments,
            straps = EXCLUDED.straps,
            no_of_straps = EXCLUDED.no_of_straps,
            chains = EXCLUDED.chains,
            mass = EXCLUDED.mass,
            api_meta_created_date = EXCLUDED.api_meta_created_date,
            api_meta_modified_date = EXCLUDED.api_meta_modified_date,
            api_meta_security = EXCLUDED.api_meta_security,
            api_meta_type = EXCLUDED.api_meta_type,
            api_meta_tip = EXCLUDED.api_meta_tip,
            api_meta_sid = EXCLUDED.api_meta_sid,
            api_meta_branch = EXCLUDED.api_meta_branch,
            api_meta_parent = EXCLUDED.api_meta_parent,
            api_meta_errors = EXCLUDED.api_meta_errors,
            api_meta_raw = EXCLUDED.api_meta_raw,
            api_payload_raw = EXCLUDED.api_payload_raw,
            raw_json = EXCLUDED.raw_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            tip_value, object_type, inspection_date, lcd_inspection_id, coupling_id,
            response_data.get('inspectedBy'), vehicle_hash, vehicle, response_data.get('vehicleId'),
            trailer_hash, trailer, response_data.get('trailerId'),
            trailer2_hash, trailer2, response_data.get('trailerId2'),
            trailer3_hash, trailer3, response_data.get('trailerId3'),
            response_data.get('jobNumber'), response_data.get('runNumber'), response_data.get('driverLoaderName'),
            department_hash, department, team_hash, team,
            load_compliance, 'api_success', has_unknown,
            len(response_data.get('attachments', [])), None,
            response_data.get('straps'), response_data.get('noOfStraps'), 
            response_data.get('chains'), response_data.get('mass'),
            api_meta_created, api_meta_modified,
            meta.get('security'), meta.get('type'), meta.get('tip'),
            meta.get('sid'), meta.get('branch'), parent_array,
            json.dumps(meta.get('errors', [])), json.dumps(meta), json.dumps(response_data),
            json.dumps(response_data)
        )
    )

    logger.debug(f"Inserted/updated noggin_data record for TIP {tip_value}")

def calculate_next_retry_time(retry_count: int) -> datetime:
    """Calculate next retry time with exponential backoff"""
    max_retry_attempts: int = config.getint('retry', 'max_retry_attempts')
    retry_backoff_multiplier: int = config.getint('retry', 'retry_backoff_multiplier')

    if retry_count >= max_retry_attempts:
        return datetime.now() + timedelta(days=365)

    backoff_seconds: int = (retry_backoff_multiplier ** retry_count) * 60
    max_backoff_seconds: int = 3600
    backoff_seconds = min(backoff_seconds, max_backoff_seconds)

    return datetime.now() + timedelta(seconds=backoff_seconds)


def get_tips_to_process_from_database(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Query database for TIPs that need processing
    Priority: failed â†’ interrupted â†’ partial â†’ api_failed â†’ pending
    """
    max_retry_attempts: int = config.getint('retry', 'max_retry_attempts')

    query: str = """
        SELECT tip, processing_status, retry_count, next_retry_at
        FROM noggin_data
        WHERE permanently_failed = FALSE
          AND (
              (processing_status IN ('failed', 'interrupted', 'partial', 'api_failed')
               AND retry_count < %s
               AND (next_retry_at IS NULL OR next_retry_at <= CURRENT_TIMESTAMP))
              OR processing_status = 'pending'
          )
        ORDER BY
            CASE processing_status
                WHEN 'failed' THEN 1
                WHEN 'interrupted' THEN 2
                WHEN 'partial' THEN 3
                WHEN 'api_failed' THEN 4
                WHEN 'pending' THEN 5
                ELSE 6
            END,
            csv_imported_at ASC
        LIMIT %s
    """

    tips: List[Dict[str, Any]] = db_manager.execute_query_dict(query, (max_retry_attempts, limit))
    return tips


def mark_permanently_failed(tip_value: str) -> None:
    """Mark TIP as permanently failed after max retries"""
    db_manager.execute_update(
        """
        UPDATE noggin_data
        SET permanently_failed = TRUE,
            processing_status = 'failed',
            last_error_message = 'Max retry attempts exceeded'
        WHERE tip = %s
        """,
        (tip_value,)
    )
    logger.warning(f"TIP {tip_value} marked as permanently failed")

def should_process_tip(tip_value: str) -> Tuple[bool, Optional[int]]:
    """
    Check if TIP should be processed based on database state

    Returns:
        Tuple of (should_process, current_retry_count)
    """
    result: List[Dict[str, Any]] = db_manager.execute_query_dict(
        """
        SELECT processing_status, all_attachments_complete, retry_count,
               permanently_failed, next_retry_at
        FROM noggin_data
        WHERE tip = %s
        """,
        (tip_value,)
    )

    if not result:
        logger.debug(f"TIP {tip_value} not in database - will process")
        return True, 0

    record: Dict[str, Any] = result[0]
    status: str = record['processing_status']
    all_complete: bool = record['all_attachments_complete']
    retry_count: int = record['retry_count'] or 0
    permanently_failed: bool = record['permanently_failed']
    next_retry_at: Optional[datetime] = record['next_retry_at']

    if permanently_failed:
        logger.info(f"TIP {tip_value} permanently failed - skipping")
        return False, retry_count

    if status == 'complete' and all_complete:
        logger.info(f"TIP {tip_value} already completed successfully - skipping")
        return False, retry_count

    if next_retry_at and datetime.now() < next_retry_at:
        wait_seconds: float = (next_retry_at - datetime.now()).total_seconds()
        logger.debug(f"TIP {tip_value} in backoff period - retry in {wait_seconds:.0f}s")
        return False, retry_count

    max_retry_attempts: int = config.getint('retry', 'max_retry_attempts')
    if retry_count >= max_retry_attempts:
        mark_permanently_failed(tip_value)
        return False, retry_count

    logger.info(f"TIP {tip_value} needs processing (status: {status}, retry: {retry_count})")
    return True, retry_count


def get_total_tip_count(tip_csv_file_path: Path) -> int:
    """Count valid TIPs in CSV for progress tracking"""
    try:
        import csv

        with open(tip_csv_file_path, 'r', newline='', encoding='utf-8') as file:
            tip_csv_reader = csv.reader(file)
            header: List[str] = next(tip_csv_reader)

            header = [col.strip().lower() for col in header]
            tip_column_index: int = header.index('tip')

            valid_tip_count: int = 0
            for row in tip_csv_reader:
                if row and len(row) > tip_column_index and row[tip_column_index].strip():
                    valid_tip_count += 1

            return valid_tip_count

    except Exception as e:
        logger.warning(f"Could not count TIPs: {e}")
        return 0


def update_progress_tracking(processed_count: int, total_count: int, start_time_val: float) -> None:
    """Display progress updates with time estimates"""
    if processed_count == 0:
        return

    elapsed_time: float = time.perf_counter() - start_time_val
    tips_per_second: float = processed_count / elapsed_time
    remaining_tips: int = total_count - processed_count

    if tips_per_second > 0:
        estimated_remaining_seconds: float = remaining_tips / tips_per_second

        if estimated_remaining_seconds >= 3600:
            time_estimate: str = f"{estimated_remaining_seconds/3600:.1f} hours"
        elif estimated_remaining_seconds >= 60:
            time_estimate = f"{estimated_remaining_seconds/60:.1f} minutes"
        else:
            time_estimate = f"{estimated_remaining_seconds:.1f} seconds"

        progress_percentage: float = (processed_count / total_count) * 100

        logger.info(f"Progress: {processed_count}/{total_count} ({progress_percentage:.1f}%) - "
                   f"Rate: {tips_per_second:.2f} TIPs/sec - ETA: {time_estimate}")


def log_shutdown_summary(processed_count: int, total_count: int, start_time_val: float, reason: str = "manual") -> None:
    """Log comprehensive shutdown summary"""
    elapsed_time: float = time.perf_counter() - start_time_val
    completion_percentage: float = (processed_count / total_count) * 100 if total_count > 0 else 0

    logger.info("="*80)
    logger.info("SHUTDOWN SUMMARY")
    logger.info("="*80)
    logger.info(f"Shutdown reason: {reason}")
    logger.info(f"TIPs processed:  {processed_count:,} of {total_count:,} ({completion_percentage:.1f}%)")
    logger.info(f"Processing time: {elapsed_time/3600:.1f} hours")
    if processed_count > 0:
        logger.info(f"Average rate: {processed_count/elapsed_time:.2f} TIPs/second")
        remaining_estimate: float = (total_count - processed_count) * (elapsed_time / processed_count)
        logger.info(f"Estimated time for remaining: {remaining_estimate/3600:.1f} hours")
    logger.info("All work saved to PostgreSQL database")
    logger.info("="*80)


def main() -> int:
    """Main processing function - DB Driven"""
    global current_tip_being_processed

    # Configuration for batch size
    batch_limit: int = 100
    
    logger.info("Fetching TIPs to process from database...")
    tips_to_process: List[Dict[str, Any]] = get_tips_to_process_from_database(limit=batch_limit)
    
    total_tip_count: int = len(tips_to_process)
    
    if total_tip_count == 0:
        logger.info("No eligible TIPs found in database (pending or due for retry).")
        return 0

    logger.info(f"Found {total_tip_count} TIPs to process")

    processed_count: int = 0
    main_start_time: float = time.perf_counter()

    for i, tip_record in enumerate(tips_to_process, start=1):
        if not shutdown_handler.should_continue_processing():
            logger.warning(f"Graceful shutdown after processing {processed_count} TIPs")
            break

        tip_value: str = tip_record['tip']
        
        # We can use the retry count directly from the DB record since we just queried it
        current_retry_count: int = tip_record.get('retry_count', 0)

        current_tip_being_processed = tip_value
        processed_count += 1

        if processed_count % 10 == 0:
            update_progress_tracking(processed_count, total_tip_count, main_start_time)

        try:
            circuit_breaker.before_request()
        except CircuitBreakerError as e:
            logger.warning(f"Circuit breaker blocked request for TIP {tip_value}: {e}")
            # If circuit breaker is open, we probably shouldn't hammer it with the rest of the batch
            time.sleep(10)
            continue

        endpoint: str = endpoint_template.replace('$tip', tip_value)
        url: str = base_url + endpoint
        logger.info(f"Processing TIP {processed_count}/{total_tip_count}: {tip_value} (retry: {current_retry_count})")
        logger.debug(f"Request URL: {url}")

        try:
            api_start_time: float = time.perf_counter()
            response: requests.Response = requests.get(url, headers=headers, timeout=api_timeout)
            circuit_breaker.record_success()
            api_retry_count: int = 0

            if response.status_code == 429:
                circuit_breaker.record_failure()
                logger.warning(f"Rate limited for TIP {tip_value}. Sleeping {too_many_requests_sleep_time}s")
                time.sleep(too_many_requests_sleep_time)
                try:
                    circuit_breaker.before_request()
                    response = requests.get(url, headers=headers, timeout=api_timeout)
                    circuit_breaker.record_success()
                    api_retry_count = 1
                except CircuitBreakerError as cb_error:
                    logger.warning(f"Circuit breaker blocked retry: {cb_error}")
                    
                    new_retry_count: int = current_retry_count + 1
                    next_retry: datetime = calculate_next_retry_time(new_retry_count)
                    
                    db_manager.execute_update(
                        """
                        INSERT INTO noggin_data (tip, object_type, processing_status, last_error_message, 
                                                retry_count, last_retry_at, next_retry_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (tip) DO UPDATE SET
                            processing_status = EXCLUDED.processing_status,
                            last_error_message = EXCLUDED.last_error_message,
                            retry_count = EXCLUDED.retry_count,
                            last_retry_at = EXCLUDED.last_retry_at,
                            next_retry_at = EXCLUDED.next_retry_at
                        """,
                        (tip_value, object_type, 'api_failed', str(cb_error), 
                         new_retry_count, datetime.now(), next_retry)
                    )
                    continue
                except requests.exceptions.RequestException as retry_error:
                    circuit_breaker.record_failure()
                    logger.error(f"Retry failed for TIP {tip_value}: {retry_error}", exc_info=True)

                    new_retry_count = current_retry_count + 1
                    next_retry = calculate_next_retry_time(new_retry_count)

                    db_manager.execute_update(
                        """
                        INSERT INTO noggin_data (tip, object_type, processing_status, last_error_message, 
                                                retry_count, last_retry_at, next_retry_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (tip) DO UPDATE SET
                            processing_status = EXCLUDED.processing_status,
                            last_error_message = EXCLUDED.last_error_message,
                            retry_count = EXCLUDED.retry_count,
                            last_retry_at = EXCLUDED.last_retry_at,
                            next_retry_at = EXCLUDED.next_retry_at
                        """,
                        (tip_value, object_type, 'api_failed', str(retry_error), 
                         new_retry_count, datetime.now(), next_retry)
                    )

                    db_manager.execute_update(
                        """
                        INSERT INTO processing_errors (tip, error_type, error_message, error_details)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (tip_value, 'api_failed', str(retry_error), json.dumps({'url': url}))
                    )
                    continue

            if response.status_code == 200:
                logger.info(f"Successful API response for TIP {tip_value}")
                response_data: Dict[str, Any] = response.json()

                insert_noggin_data_record(tip_value, response_data)

                lcd_inspection_id: str = response_data.get('lcdInspectionId', 'unknown')

                process_attachments(response_data, lcd_inspection_id, tip_value)

            else:
                circuit_breaker.record_failure()
                error_details: str = handle_api_error(response, tip_value, url)
                logger.error(error_details)
                session_logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\t{tip_value}\tAPI_ERROR_{response.status_code}\t0\tERROR")

                new_retry_count = current_retry_count + 1
                next_retry = calculate_next_retry_time(new_retry_count)

                db_manager.execute_update(
                    """
                    INSERT INTO noggin_data (tip, object_type, processing_status, last_error_message, 
                                            retry_count, last_retry_at, next_retry_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tip) DO UPDATE SET
                        processing_status = EXCLUDED.processing_status,
                        last_error_message = EXCLUDED.last_error_message,
                        retry_count = EXCLUDED.retry_count,
                        last_retry_at = EXCLUDED.last_retry_at,
                        next_retry_at = EXCLUDED.next_retry_at
                    """,
                    (tip_value, object_type, 'api_failed', error_details, 
                     new_retry_count, datetime.now(), next_retry)
                )

                db_manager.execute_update(
                    """
                    INSERT INTO processing_errors (tip, error_type, error_message, error_details)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (tip_value, 'api_failed', error_details, json.dumps({
                        'http_status': response.status_code,
                        'url': url
                    }))
                )

        except requests.exceptions.ConnectionError as connection_error:
            circuit_breaker.record_failure()
            logger.error(f"Connection error for TIP {tip_value}: {connection_error}", exc_info=True)

            new_retry_count = current_retry_count + 1
            next_retry = calculate_next_retry_time(new_retry_count)

            db_manager.execute_update(
                """
                INSERT INTO noggin_data (tip, object_type, processing_status, last_error_message, 
                                        retry_count, last_retry_at, next_retry_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tip) DO UPDATE SET
                    processing_status = EXCLUDED.processing_status,
                    last_error_message = EXCLUDED.last_error_message,
                    retry_count = EXCLUDED.retry_count,
                    last_retry_at = EXCLUDED.last_retry_at,
                    next_retry_at = EXCLUDED.next_retry_at
                """,
                (tip_value, object_type, 'api_failed', str(connection_error), 
                 new_retry_count, datetime.now(), next_retry)
            )
            continue

        except requests.exceptions.RequestException as request_error:
            circuit_breaker.record_failure()
            logger.error(f"Request error for TIP {tip_value}: {request_error}", exc_info=True)

            new_retry_count = current_retry_count + 1
            next_retry = calculate_next_retry_time(new_retry_count)

            db_manager.execute_update(
                """
                INSERT INTO noggin_data (tip, object_type, processing_status, last_error_message, 
                                        retry_count, last_retry_at, next_retry_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tip) DO UPDATE SET
                    processing_status = EXCLUDED.processing_status,
                    last_error_message = EXCLUDED.last_error_message,
                    retry_count = EXCLUDED.retry_count,
                    last_retry_at = EXCLUDED.last_retry_at,
                    next_retry_at = EXCLUDED.next_retry_at
                """,
                (tip_value, object_type, 'api_failed', str(request_error), 
                 new_retry_count, datetime.now(), next_retry)
            )
            continue

        except Exception as e:
            circuit_breaker.record_failure()
            logger.error(f"Unexpected error processing TIP {tip_value}: {e}", exc_info=True)

            new_retry_count = current_retry_count + 1
            next_retry = calculate_next_retry_time(new_retry_count)

            db_manager.execute_update(
                """
                INSERT INTO noggin_data (tip, object_type, processing_status, last_error_message, 
                                        retry_count, last_retry_at, next_retry_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tip) DO UPDATE SET
                    processing_status = EXCLUDED.processing_status,
                    last_error_message = EXCLUDED.last_error_message,
                    retry_count = EXCLUDED.retry_count,
                    last_retry_at = EXCLUDED.last_retry_at,
                    next_retry_at = EXCLUDED.next_retry_at
                """,
                (tip_value, object_type, 'failed', str(e), 
                 new_retry_count, datetime.now(), next_retry)
            )
            continue

        current_tip_being_processed = None

    return processed_count

if __name__ == "__main__":
    try:
        logger.info("Starting main processing loop")
        processed_count: int = main()

        logger.info(f"Processing completed. Total TIPs processed: {processed_count}")
        logger.info("Script completed successfully")

    except KeyboardInterrupt:
        logger.warning("Processing interrupted by user")
        log_shutdown_summary(0, 0, start_time, "keyboard_interrupt")

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        log_shutdown_summary(0, 0, start_time, "error")
        raise

    finally:
        if 'db_manager' in locals():
            db_manager.close_all()

        end_time: float = time.perf_counter()
        total_duration: float = end_time - start_time
        logger.info(f"Total execution time: {total_duration/3600:.2f} hours ({total_duration:.2f} seconds)")
        logger.info(f"Session ID: {batch_session_id}")
        logger.info("="*80)

        session_logger.info(f"\nSESSION END: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        session_logger.info(f"TOTAL EXECUTION TIME: {total_duration:.2f} seconds")