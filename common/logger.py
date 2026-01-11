import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import sys
import os

class AlignedFormatter(logging.Formatter):
    """
    Formatter that ensures strict column alignment by:
    1. Placing variable-length 'message' last.
    2. Truncating metadata fields that exceed their allocated width.
    3. Padding metadata fields to fixed width.
    """
    
    # Configuration Constants (Easy to change)
    LEVEL_WIDTH = 8
    PROCESS_WIDTH = 7
    THREAD_WIDTH = 15
    LOGGER_NAME_WIDTH = 40
    MODULE_WIDTH = 20
    LINENO_WIDTH = 4
    FUNC_NAME_WIDTH = 30

    def __init__(self, fmt: str = None, datefmt: str = None):
        super().__init__(fmt, datefmt)
        # Define strict widths for columns using the constants
        self.column_widths = {
            'levelname': self.LEVEL_WIDTH,
            'process': self.PROCESS_WIDTH,
            'threadName': self.THREAD_WIDTH,
            'name': self.LOGGER_NAME_WIDTH,
            'module': self.MODULE_WIDTH,
            'lineno': self.LINENO_WIDTH,
            'funcName': self.FUNC_NAME_WIDTH
        }

    def format(self, record: logging.LogRecord) -> str:
        # Create a copy to avoid modifying the original record permanently
        record_dict = record.__dict__.copy()
        
        # Process specific fields for alignment
        for key, width in self.column_widths.items():
            val = str(record_dict.get(key, ''))
            
            # Truncate if too long (reserving 1 char for ellipsis)
            if len(val) > width:
                val = val[:width-1] + '…'
            
            # Pad to fixed width
            record_dict[key] = val.ljust(width)
            
        # Format date manually to ensure millisecond precision consistency
        record_dict['asctime'] = self.formatTime(record, self.datefmt)
        
        # Ensure msecs is formatted as 3 digits
        record_dict['msecs'] = f"{record.msecs:03.0f}"

        # Construct the aligned string.
        # CRITICAL: Message is placed LAST to prevent shifting other columns.
        fmt = (
            "{asctime}.{msecs} | {levelname} | PID:{process} | THD:{threadName} | "
            "Logger:{name} | Loc:{module}:{lineno} | Func:{funcName} | {message}"
        )
        
        try:
            return fmt.format(**record_dict)
        except Exception as e:
            # Fallback in case of formatting error
            return f"LOG_FORMAT_ERROR: {e} | Original Message: {record.msg}"


class LoggerManager:
    """Manages application logging configuration with daily rotation and multiple log types"""
    
    def __init__(self, config: Any, script_name: Optional[str] = None) -> None:
        """
        Initialise logger manager
        
        Args:
            config: ConfigLoader instance
            script_name: Override script name (auto-detected if None)
        """
        self.config = config
        self.script_name: str = script_name or self._detect_script_name()
        
        # Robust path handling
        base_log_path = config.get('paths', 'base_log_path', fallback='./logs')
        self.log_path: Path = Path(base_log_path)
        
        try:
            self.log_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            sys.stderr.write(f"CRITICAL: Cannot create log directory at {self.log_path}\n")
            # Fallback to tmp or current directory if permission fails
            self.log_path = Path('./logs_fallback')
            self.log_path.mkdir(parents=True, exist_ok=True)

        self._configured: bool = False
    
    def _detect_script_name(self) -> str:
        """Auto-detect script name from main module"""
        import __main__
        if hasattr(__main__, '__file__') and __main__.__file__ is not None:
            return Path(__main__.__file__).stem
        return 'unknown_script'
    
    def _build_log_filename(self, pattern: str) -> str:
        """
        Build log filename from pattern
        
        Args:
            pattern: Filename pattern with {script_name}, {date}, {time} placeholders
        """
        now: datetime = datetime.now()
        replacements: Dict[str, str] = {
            'script_name': self.script_name,
            'date': now.strftime('%Y%m%d'),
            'time': now.strftime('%H%M%S')
        }
        return pattern.format(**replacements)
    
    def configure_application_logger(self) -> None:
        """Configure root logger with aligned file output and console handlers"""
        if self._configured:
            return
        
        root_logger: logging.Logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.DEBUG)
        
        # --- File Handler Setup ---
        log_pattern: str = self.config.get('logging', 'log_filename_pattern', 
                                         fallback='{script_name}_{date}.log')
        log_filename: str = self._build_log_filename(log_pattern)
        log_file: Path = self.log_path / log_filename
        
        file_level: str = self.config.get('logging', 'file_log_level', fallback='DEBUG')
        
        try:
            file_handler: logging.FileHandler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(getattr(logging, file_level.upper()))
            
            # Use the custom AlignedFormatter
            file_formatter = AlignedFormatter(datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
            
        except OSError as e:
            sys.stderr.write(f"Failed to setup file logging: {e}\n")

        # --- Console Handler Setup ---
        console_level: str = self.config.get('logging', 'console_log_level', fallback='INFO')
        
        console_formatter: logging.Formatter = logging.Formatter(
            # Simplified console output (less noisy than file)
            fmt='%(asctime)s | %(levelname)-8s | %(module)-20s | %(message)s',
            datefmt='%H:%M:%S'
        )
        
        console_handler: logging.StreamHandler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, console_level.upper()))
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        self._configured = True
        
        # Log startup info
        logger: logging.Logger = logging.getLogger(__name__)
        logger.info(f"Logger initialised. File: {log_file}")
        logger.debug(f"Configuration: Console={console_level}, File={file_level}")
    
    def create_session_logger(self, session_id: str) -> logging.Logger:
        """
        Create dedicated session logger with separate file
        """
        # Use a dot-notation name so it's technically a child, but we won't propagate
        session_logger_name = f"session.{session_id}"
        session_logger: logging.Logger = logging.getLogger(session_logger_name)
        
        # Prevent duplicate handlers if called multiple times for same session
        if session_logger.handlers:
            return session_logger

        session_logger.setLevel(logging.INFO)
        session_logger.propagate = False
        
        session_log_file: Path = self.log_path / f'session_{session_id}.log'
        
        try:
            # Session logs often just need the message, or a simpler format
            session_formatter: logging.Formatter = logging.Formatter(
                '%(asctime)s | %(message)s', 
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            session_handler: logging.FileHandler = logging.FileHandler(session_log_file, encoding='utf-8')
            session_handler.setLevel(logging.INFO)
            session_handler.setFormatter(session_formatter)
            session_logger.addHandler(session_handler)
            
            main_logger: logging.Logger = logging.getLogger(__name__)
            main_logger.info(f"Session logger created: {session_log_file}")
            
        except OSError as e:
            logging.error(f"Failed to create session log file: {e}")
            
        return session_logger
    
    def cleanup_old_logs(self, days_to_keep: Optional[int] = None) -> int:
        """Remove log files older than specified days"""
        if days_to_keep is None:
            days_to_keep = self.config.getint('logging', 'log_retention_days', fallback=30)
        
        cutoff_time: float = datetime.now().timestamp() - (days_to_keep * 86400)
        removed_count: int = 0
        
        logger: logging.Logger = logging.getLogger(__name__)
        
        try:
            for log_file in self.log_path.glob('*.log'):
                if log_file.stat().st_mtime < cutoff_time:
                    try:
                        log_file.unlink()
                        removed_count += 1
                    except OSError as e:
                        logger.warning(f"Could not remove old log {log_file}: {e}")
            
            for gz_file in self.log_path.glob('*.gz'):
                if gz_file.stat().st_mtime < cutoff_time:
                    try:
                        gz_file.unlink()
                        removed_count += 1
                    except OSError as e:
                        logger.warning(f"Could not remove old archive {gz_file}: {e}")
                        
        except Exception as e:
            logger.error(f"Error during log cleanup: {e}")
            
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old log files")
        
        return removed_count
    
    def compress_old_logs(self, days_before_compress: int = 7) -> int:
        """Compress log files older than specified days using gzip"""
        import gzip
        import shutil
        
        cutoff_time: float = datetime.now().timestamp() - (days_before_compress * 86400)
        compressed_count: int = 0
        logger: logging.Logger = logging.getLogger(__name__)
        
        for log_file in self.log_path.glob('*.log'):
            try:
                # Skip if active log file (rough check)
                if log_file.name.startswith(f"{self.script_name}_") and \
                   datetime.now().strftime('%Y%m%d') in log_file.name:
                    continue

                if log_file.stat().st_mtime < cutoff_time:
                    gz_file: Path = log_file.with_suffix('.log.gz')
                    
                    if gz_file.exists():
                        continue
                    
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(gz_file, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    log_file.unlink()
                    compressed_count += 1
            except Exception as e:
                logger.warning(f"Could not compress log {log_file}: {e}")
        
        if compressed_count > 0:
            logger.info(f"Compressed {compressed_count} old log files")
        
        return compressed_count

if __name__ == "__main__":
    # Mock ConfigLoader for testing
    class MockConfig:
        def get(self, section, key, fallback=None):
            return fallback
        def getint(self, section, key, fallback=None):
            return fallback

    try:
        print("Initialising Logger Manager...")
        config = MockConfig()
        logger_manager = LoggerManager(config, script_name='test_logger')
        logger_manager.configure_application_logger()
        
        logger = logging.getLogger("test_module")
        
        # Test varying lengths to demonstrate alignment
        logger.info("Short message")
        logger.info("A much longer message that usually breaks formatting in standard log files")
        
        # Simulate a different module/logger name
        db_logger = logging.getLogger("common.database.connection.pool")
        db_logger.warning("Connection lost")
        
        print("\nCheck the log file in ./logs to see the alignment!")
        
    except Exception as e:
        print(f"Test failed: {e}")