from __future__ import annotations
import psycopg2
from psycopg2 import pool, extras
from typing import Optional, Any, List, Dict, Tuple, Generator, Sequence
import logging
import atexit
from contextlib import contextmanager

logger: logging.Logger = logging.getLogger(__name__)

class DatabaseConnectionError(Exception):
    """Raised when database connection fails"""
    pass


class DatabaseConnectionManager:
    """Manages PostgreSQL connection pool with health checks and graceful cleanup"""
    
    def __init__(self, config: 'ConfigLoader') -> None:
        """
        Initialise connection pool
        
        Args:
            config: ConfigLoader instance with PostgreSQL configuration
        """
        self.config: 'ConfigLoader' = config
        self.pool: Optional[pool.ThreadedConnectionPool] = None
        
        pg_config: Dict[str, Any] = config.get_postgresql_config()
        
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=pg_config.get('minconn', 2),
                maxconn=pg_config.get('maxconn', 10),
                host=pg_config['host'],
                port=pg_config['port'],
                database=pg_config['database'],
                user=pg_config['user'],
                password=pg_config['password'],
                options=f"-c search_path={pg_config.get('schema', 'noggin_schema')},public",
                keepalives=1,
                keepalives_idle=60,
                keepalives_interval=10,
                keepalives_count=5
            )
            
            logger.info(f"Database connection pool initialised: {pg_config['database']}@{pg_config['host']}")
            logger.info(f"Schema: {pg_config.get('schema', 'noggin_schema')}")
            logger.info(f"Pool size: min={pg_config.get('minconn', 2)}, max={pg_config.get('maxconn', 10)}")
            
            atexit.register(self.close_all)
            
        except psycopg2.Error as e:
            raise DatabaseConnectionError(f"Failed to create connection pool: {e}")
    
    def _health_check(self, conn: psycopg2.extensions.connection) -> bool:
        """
        Perform quick health check on connection
        
        Args:
            conn: Database connection to check
            
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return True
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            return False
    
    def get_connection(self) -> psycopg2.extensions.connection:
        """
        Get a healthy connection from the pool
        
        Returns:
            psycopg2 connection object
            
        Raises:
            DatabaseConnectionError if cannot get healthy connection
        """
        if not self.pool:
            raise DatabaseConnectionError("Connection pool not initialised")
        
        try:
            conn: psycopg2.extensions.connection = self.pool.getconn()
            
            if not self._health_check(conn):
                logger.warning("Stale connection detected, replacing...")
                self.pool.putconn(conn, close=True)
                conn = self.pool.getconn()
                
                if not self._health_check(conn):
                    raise DatabaseConnectionError("Unable to obtain healthy connection")
            
            return conn
            
        except psycopg2.pool.PoolError as e:
            raise DatabaseConnectionError(f"Pool error: {e}")
    
    def return_connection(self, conn: psycopg2.extensions.connection, close_conn: bool = False) -> None:
        """
        Return connection to pool
        
        Args:
            conn: Connection to return
            close_conn: If True, close connection instead of returning to pool
        """
        if not self.pool:
            return
        
        try:
            self.pool.putconn(conn, close=close_conn)
        except psycopg2.pool.PoolError as e:
            logger.error(f"Error returning connection to pool: {e}")
    
    @contextmanager
    def get_cursor(self, cursor_factory: Optional[Any] = None) -> Generator[psycopg2.extensions.cursor, None, None]:
        """
        Context manager for getting connection and cursor
        
        Args:
            cursor_factory: Optional cursor factory (e.g., RealDictCursor)
        
        Yields:
            Database cursor
            
        Usage:
            with db_manager.get_cursor() as cur:
                cur.execute("SELECT * FROM table")
                results = cur.fetchall()
        """
        conn: psycopg2.extensions.connection = self.get_connection()
        cursor: psycopg2.extensions.cursor = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database operation failed: {e}", exc_info=True)
            raise
        finally:
            cursor.close()
            self.return_connection(conn)
    
    def execute_query(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> List[Tuple[Any, ...]]:
        """
        Execute SELECT query and return results
        
        Args:
            query: SQL query string
            params: Query parameters (optional)
            
        Returns:
            List of tuples (query results)
        """
        with self.get_cursor() as cur:
            cur.execute(query, params)
            results: List[Tuple[Any, ...]] = cur.fetchall()
            return results
    
    def execute_query_dict(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> List[Dict[str, Any]]:
        """
        Execute SELECT query and return results as dictionaries
        
        Args:
            query: SQL query string
            params: Query parameters (optional)
            
        Returns:
            List of dictionaries (query results)
        """
        with self.get_cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            results: List[Dict[str, Any]] = [dict(row) for row in cur.fetchall()]
            return results
    
    def execute_update(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> int:
        """
        Execute INSERT/UPDATE/DELETE query
        
        Args:
            query: SQL query string
            params: Query parameters (optional)
            
        Returns:
            Number of affected rows
        """
        with self.get_cursor() as cur:
            cur.execute(query, params)
            rowcount: int = cur.rowcount
            return rowcount
    
    # def execute_transaction(self, queries: List[Tuple[str, Optional[Tuple[Any, ...]]]]) -> bool:
    def execute_transaction(self, queries: Sequence[Tuple[str, Optional[Tuple[Any, ...]]]]) -> bool:
        """
        Execute multiple queries in a transaction
        
        Args:
            queries: List of (query, params) tuples
            
        Returns:
            True if transaction succeeded, False otherwise
        """
        conn: psycopg2.extensions.connection = self.get_connection()
        try:
            with conn.cursor() as cur:
                for query, params in queries:
                    cur.execute(query, params)
            conn.commit()
            logger.debug(f"Transaction committed: {len(queries)} queries")
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction failed, rolled back: {e}", exc_info=True)
            return False
        finally:
            self.return_connection(conn)
    
    def close_all(self) -> None:
        """Close all connections and clean up pool"""
        if self.pool:
            try:
                logger.info("Closing all database connections...")
                self.pool.closeall()
                logger.info("All database connections closed")
            except Exception as e:
                logger.error(f"Error closing connection pool: {e}")
            finally:
                self.pool = None


if __name__ == "__main__":
    from .config import ConfigLoader
    
    try:
        config: ConfigLoader = ConfigLoader(
            '../config/base_config.ini',
            '../config/load_compliance_check_driver_loader_config.ini'
        )
        
        db_manager: DatabaseConnectionManager = DatabaseConnectionManager(config)
        
        version_result: List[Tuple[Any, ...]] = db_manager.execute_query("SELECT version()")
        print("✓ PostgreSQL version:", version_result[0][0])
        
        tables_result: List[Dict[str, Any]] = db_manager.execute_query_dict(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
        )
        print(f"✓ Found {len(tables_result)} tables:")
        for row in tables_result:
            print(f"  - {row['table_name']}")
        
        print("\n✓ Database connection manager working correctly")
        
    except DatabaseConnectionError as e:
        print(f"✗ Database error: {e}")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db_manager' in locals():
            db_manager.close_all()