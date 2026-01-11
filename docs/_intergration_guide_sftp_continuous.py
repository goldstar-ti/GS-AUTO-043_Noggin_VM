"""
Integration Guide: Adding SFTP Download to Continuous Processor

This file shows the code changes needed to integrate sftp_download_tips.py
with noggin_continuous_processor.py

Copy the relevant sections into your existing noggin_continuous_processor.py
"""

# =============================================================================
# SECTION 1: Add import at top of noggin_continuous_processor.py
# =============================================================================

# Add this import near the other imports:
# from sftp_download_tips import run_sftp_download


# =============================================================================
# SECTION 2: Add new function for SFTP download cycle
# =============================================================================

def run_sftp_download_cycle(config, db_manager) -> dict:
    """
    Execute SFTP download cycle
    
    Args:
        config: ConfigLoader instance
        db_manager: DatabaseConnectionManager instance
        
    Returns:
        Dictionary with download statistics
    """
    from sftp_download_tips import run_sftp_download
    
    logger.info("Starting SFTP download cycle...")
    
    try:
        result = run_sftp_download(
            sftp_config_path='config/sftp_config.ini',
            base_config=config,
            db_manager=db_manager
        )
        
        if result['status'] == 'success':
            logger.info(
                f"SFTP download cycle complete: "
                f"{result['total_inserted']} TIPs inserted, "
                f"{result['total_duplicates']} duplicates skipped"
            )
        elif result['status'] == 'no_files':
            logger.info("SFTP download cycle complete: no new files on server")
        else:
            logger.warning(f"SFTP download cycle completed with status: {result['status']}")
        
        return result
        
    except Exception as e:
        logger.error(f"SFTP download cycle failed: {e}", exc_info=True)
        return {
            'status': 'error',
            'total_inserted': 0,
            'total_duplicates': 0,
            'total_errors': 1
        }


# =============================================================================
# SECTION 3: Add configuration to config/base_config.ini
# =============================================================================

"""
Add this to your [continuous] section in base_config.ini:

[continuous]
cycle_sleep_seconds = 300
import_csv_every_n_cycles = 3
resolve_hashes_every_n_cycles = 10
sftp_download_every_n_cycles = 6
"""


# =============================================================================
# SECTION 4: Modify main() function in noggin_continuous_processor.py
# =============================================================================

"""
In the main() function, add these lines after the existing config loading:

    # Add SFTP download frequency configuration
    sftp_download_frequency = config.getint('continuous', 'sftp_download_every_n_cycles', fallback=6)
    
    logger.info(f"  - SFTP download frequency: every {sftp_download_frequency} cycles")

Then inside the main while loop, add this block alongside the other cycle operations:

    # Run SFTP download cycle (every N cycles)
    if cycle_count % sftp_download_frequency == 0:
        sftp_result = run_sftp_download_cycle(config, db_manager)
        # Optionally track statistics
        if sftp_result.get('total_inserted', 0) > 0:
            logger.info(f"SFTP: Added {sftp_result['total_inserted']} new TIPs to queue")
"""


# =============================================================================
# SECTION 5: Complete modified main() example
# =============================================================================

def example_modified_main():
    """
    Example showing the complete modified main() structure
    (This is for reference - copy relevant parts to your actual file)
    """
    import signal
    from common import ConfigLoader, LoggerManager, DatabaseConnectionManager, CSVImporter, HashManager
    
    global shutdown_requested
    shutdown_requested = False
    
    def signal_handler(signum, frame):
        global shutdown_requested
        logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
        shutdown_requested = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        config = ConfigLoader(
            'config/base_config.ini',
            'config/load_compliance_check_config.ini'
        )
        
        logger_manager = LoggerManager(config, script_name='noggin_continuous_processor')
        logger_manager.configure_application_logger()
        
        # Load all cycle frequencies
        cycle_sleep = config.getint('continuous', 'cycle_sleep_seconds')
        csv_import_frequency = config.getint('continuous', 'import_csv_every_n_cycles')
        hash_resolution_frequency = config.getint('continuous', 'resolve_hashes_every_n_cycles', fallback=10)
        sftp_download_frequency = config.getint('continuous', 'sftp_download_every_n_cycles', fallback=6)
        
        logger.info("Noggin Continuous Processor started")
        logger.info(f"Configuration:")
        logger.info(f"  - Cycle sleep: {cycle_sleep} seconds")
        logger.info(f"  - CSV import frequency: every {csv_import_frequency} cycles")
        logger.info(f"  - Hash resolution frequency: every {hash_resolution_frequency} cycles")
        logger.info(f"  - SFTP download frequency: every {sftp_download_frequency} cycles")
        
        db_manager = DatabaseConnectionManager(config)
        
        cycle_count = 0
        
        while not shutdown_requested:
            cycle_count += 1
            
            logger.info(f"\n{'='*80}")
            logger.info(f"CYCLE {cycle_count}")
            logger.info(f"{'='*80}")
            
            # Run SFTP download cycle (every N cycles)
            # This should run BEFORE CSV import to get new files first
            if cycle_count % sftp_download_frequency == 0:
                sftp_result = run_sftp_download_cycle(config, db_manager)
            
            # Run CSV import cycle (every N cycles)
            if cycle_count % csv_import_frequency == 0:
                # Your existing csv import code
                pass
            
            # Run hash resolution cycle (every N cycles)
            if cycle_count % hash_resolution_frequency == 0:
                # Your existing hash resolution code
                pass
            
            # Run main processing cycle
            # Your existing processing code
            
            # Sleep before next cycle
            if not shutdown_requested:
                logger.info(f"Sleeping {cycle_sleep}s before next cycle...")
                import time
                time.sleep(cycle_sleep)
        
        return 0
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1
    
    finally:
        if 'db_manager' in locals():
            db_manager.close_all()


# =============================================================================
# SECTION 6: Cron setup for monthly archive
# =============================================================================

"""
To set up the monthly archive cron job on Ubuntu:

1. Edit crontab:
   crontab -e

2. Add this line (runs at 2 AM on the 1st of each month):
   0 2 1 * * /home/noggin_admin/scripts/.venv/bin/python /home/noggin_admin/scripts/archive_monthly_sftp.py >> /mnt/data/noggin/log/archive_cron.log 2>&1

3. Verify cron is running:
   systemctl status cron

4. View cron logs:
   grep CRON /var/log/syslog | tail -20


Alternative: Use systemd timer for more control:

1. Create /etc/systemd/system/noggin-archive.service:
   [Unit]
   Description=Noggin Monthly Archive
   
   [Service]
   Type=oneshot
   User=noggin_admin
   WorkingDirectory=/home/noggin_admin/scripts
   ExecStart=/home/noggin_admin/scripts/.venv/bin/python archive_monthly_sftp.py
   
2. Create /etc/systemd/system/noggin-archive.timer:
   [Unit]
   Description=Run Noggin Archive Monthly
   
   [Timer]
   OnCalendar=*-*-01 02:00:00
   Persistent=true
   
   [Install]
   WantedBy=timers.target

3. Enable and start:
   sudo systemctl daemon-reload
   sudo systemctl enable noggin-archive.timer
   sudo systemctl start noggin-archive.timer
   
4. Check status:
   systemctl list-timers noggin-archive.timer
"""