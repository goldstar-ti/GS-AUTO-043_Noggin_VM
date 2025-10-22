import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Optional
import sys


class LoggerManager:
    """Manages application logging configuration with daily rotation and multiple log types"""
    
    def __init__(self, config: 'ConfigLoader', script_name: Optional[str] = None) -> None:
        """
        Initialise logger manager
        
        Args:
            config: ConfigLoader instance
            script_name: Override script name (auto-detected if None)
        """
        self.config: 'ConfigLoader' = config
        self.script_name: str = script_name or self._detect_script_name()
        self.log_path: Path = Path(config.get('paths', 'base_log_path'))
        self.log_path.mkdir(parents=True, exist_ok=True)
        
        self._configured: bool = False
    
    def _detect_script_name(self) -> str:
        """Auto-detect script name from main module"""
        import __main__
        if hasattr(__main__, '__file__') and __main__.__file__ is not None:
            return Path(__main__.__file__).stem
        return 'noggin'
    
    def _build_log_filename(self, pattern: str) -> str:
        """
        Build log filename from pattern
        
        Args:
            pattern: Filename pattern with {script_name}, {date}, {time} placeholders
            
        Returns:
            Formatted filename
        """
        now: datetime = datetime.now()
        replacements: dict[str, str] = {
            'script_name': self.script_name,
            'date': now.strftime('%Y%m%d'),
            'time': now.strftime('%H%M%S')
        }
        return pattern.format(**replacements)
    
    def configure_application_logger(self) -> None:
        """Configure root logger with file and console handlers"""
        if self._configured:
            return
        
        root_logger: logging.Logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.DEBUG)
        
        log_pattern: str = self.config.get('logging', 'log_filename_pattern', 
                                          fallback='{script_name}_{date}.log')
        log_filename: str = self._build_log_filename(log_pattern)
        log_file: Path = self.log_path / log_filename
        
        console_level: str = self.config.get('logging', 'console_log_level', fallback='INFO')
        file_level: str = self.config.get('logging', 'file_log_level', fallback='DEBUG')
        
        console_formatter: logging.Formatter = logging.Formatter(
            # fmt='%(asctime)s\t%(levelname)-8s\t%(funcName)-40s\t%(message)s',
            # fmt='%(asctime)s\t%(levelname)-8s%(module)-15s%(funcName)-40s\t%(message)s\t[PID:%(process)d Line:%(lineno)d]'
            fmt=f'%(asctime)s\t%(levelname)-8s%(module)-30s:%(lineno)-4d\t%(funcName)-40s%(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler: logging.StreamHandler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, console_level))
        console_handler.setFormatter(console_formatter)
        
        file_formatter: logging.Formatter = logging.Formatter(
            # fmt='%(asctime)s\t%(levelname)-8s\t%(funcName)-20s\t%(message)s',
            fmt='%(asctime)s.%(msecs)03d | %(levelname)-8s | %(message)s | PID:%(process)-5d | THD:%(thread)d-%(threadName)-15s | Logger:%(name)-30s | Mod:%(module)-20s:%(lineno)-4d | Func:%(funcName)-30s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler: logging.FileHandler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, file_level))
        file_handler.setFormatter(file_formatter)
        
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        self._configured = True
        
        logger: logging.Logger = logging.getLogger(__name__)
        logger.info(f"Application logger configured: {log_file}")
        logger.info(f"Console level: {console_level}, File level: {file_level}")
    
    def create_session_logger(self, session_id: str) -> logging.Logger:
        """
        Create dedicated session logger with separate file
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Configured session logger
        """
        session_logger: logging.Logger = logging.getLogger('session')
        session_logger.handlers.clear()
        session_logger.setLevel(logging.INFO)
        session_logger.propagate = False
        
        session_log_file: Path = self.log_path / f'session_process_{session_id}.log'
        
        session_formatter: logging.Formatter = logging.Formatter('%(message)s')
        session_handler: logging.FileHandler = logging.FileHandler(session_log_file, encoding='utf-8')
        session_handler.setLevel(logging.INFO)
        session_handler.setFormatter(session_formatter)
        
        session_logger.addHandler(session_handler)
        
        main_logger: logging.Logger = logging.getLogger(__name__)
        main_logger.info(f"Session logger created: {session_log_file}")
        
        return session_logger
    
    def cleanup_old_logs(self, days_to_keep: Optional[int] = None) -> int:
        """
        Remove log files older than specified days
        
        Args:
            days_to_keep: Number of days to retain (from config if None)
            
        Returns:
            Number of files removed
        """
        if days_to_keep is None:
            days_to_keep = self.config.getint('logging', 'log_retention_days', fallback=30)
        
        cutoff_time: float = datetime.now().timestamp() - (days_to_keep * 86400)
        removed_count: int = 0
        
        log_file: Path
        for log_file in self.log_path.glob('*.log'):
            if log_file.stat().st_mtime < cutoff_time:
                try:
                    log_file.unlink()
                    removed_count += 1
                except Exception as e:
                    logger: logging.Logger = logging.getLogger(__name__)
                    logger.warning(f"Could not remove old log {log_file}: {e}")
        
        if removed_count > 0:
            logger = logging.getLogger(__name__)
            logger.info(f"Cleaned up {removed_count} old log files")
        
        return removed_count
    
    def compress_old_logs(self, days_before_compress: int = 7) -> int:
        """
        Compress log files older than specified days using gzip
        
        Args:
            days_before_compress: Compress logs older than this many days
            
        Returns:
            Number of files compressed
        """
        import gzip
        import shutil
        
        cutoff_time: float = datetime.now().timestamp() - (days_before_compress * 86400)
        compressed_count: int = 0
        
        log_file: Path
        for log_file in self.log_path.glob('*.log'):
            if log_file.stat().st_mtime < cutoff_time:
                gz_file: Path = log_file.with_suffix('.log.gz')
                
                if gz_file.exists():
                    continue
                
                try:
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(gz_file, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    log_file.unlink()
                    compressed_count += 1
                except Exception as e:
                    logger: logging.Logger = logging.getLogger(__name__)
                    logger.warning(f"Could not compress log {log_file}: {e}")
        
        if compressed_count > 0:
            logger = logging.getLogger(__name__)
            logger.info(f"Compressed {compressed_count} old log files")
        
        return compressed_count


if __name__ == "__main__":
    from .config import ConfigLoader
    
    try:
        config: ConfigLoader = ConfigLoader(
            '../config/base_config.ini',
            '../config/load_compliance_check_config.ini'
        )
        
        logger_manager: LoggerManager = LoggerManager(config, script_name='test_logger')
        logger_manager.configure_application_logger()
        
        logger: logging.Logger = logging.getLogger(__name__)
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        session_logger: logging.Logger = logger_manager.create_session_logger('test_session_123')
        session_logger.info("Session log entry")
        
        print("\n✓ Logger configured successfully")
        print(f"✓ Log files created in: {logger_manager.log_path}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()