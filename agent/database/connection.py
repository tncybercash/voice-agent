"""
Async PostgreSQL connection pool for high-concurrency voice agent sessions.
Optimized for 20+ concurrent users with connection pooling and retry logic.
"""
import os
import logging
import asyncio
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import asyncpg
from asyncpg import Pool, Connection
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

logger = logging.getLogger("database")

# Singleton pool instance (per-process)
_pool: Optional[Pool] = None
_pool_lock: Optional[asyncio.Lock] = None
_pool_pid: Optional[int] = None  # Track which process owns the pool


class DatabasePool:
    """
    Async PostgreSQL connection pool manager.
    Optimized for concurrent voice agent sessions.
    """
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        database: str = None,
        user: str = None,
        password: str = None,
        min_connections: int = None,
        max_connections: int = None,
    ):
        # Read from environment variables (no hardcoded defaults for security)
        self.host = host or os.getenv("POSTGRES_HOST")
        self.port = port or int(os.getenv("POSTGRES_PORT", "5432"))
        self.database = database or os.getenv("POSTGRES_DB")
        self.user = user or os.getenv("POSTGRES_USER")
        self.password = password or os.getenv("POSTGRES_PASSWORD")
        self.min_connections = min_connections or int(os.getenv("POSTGRES_MIN_CONN", "5"))
        self.max_connections = max_connections or int(os.getenv("POSTGRES_MAX_CONN", "30"))
        
        # Validate required fields
        if not all([self.host, self.database, self.user, self.password]):
            raise ValueError("Missing required database configuration. Check POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD in .env")
        
        self._pool: Optional[Pool] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the connection pool"""
        if self._initialized:
            return
        
        try:
            # Use explicit parameters instead of DSN for Windows compatibility
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=self.min_connections,
                max_size=self.max_connections,
                max_inactive_connection_lifetime=300,  # 5 min idle timeout
                command_timeout=60,
                statement_cache_size=100,  # Cache prepared statements
            )
            self._initialized = True
            logger.info(f"Database pool initialized with {self.min_connections}-{self.max_connections} connections to {self.host}:{self.port}/{self.database}")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    async def close(self) -> None:
        """Close all connections in the pool"""
        if self._pool:
            await self._pool.close()
            self._initialized = False
            logger.info("Database pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool"""
        if not self._initialized:
            await self.initialize()
        
        async with self._pool.acquire() as conn:
            yield conn
    
    async def execute(self, query: str, *args) -> str:
        """Execute a query without returning results"""
        async with self.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """Execute a query and return all results"""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Execute a query and return a single row"""
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args) -> Any:
        """Execute a query and return a single value"""
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)
    
    @asynccontextmanager
    async def transaction(self):
        """Start a transaction"""
        async with self.acquire() as conn:
            async with conn.transaction():
                yield conn


async def get_db_pool() -> DatabasePool:
    """
    Get or create the global database pool singleton.
    Creates a new pool per-process to avoid event loop conflicts.
    """
    global _pool, _pool_lock, _pool_pid
    import os
    
    current_pid = os.getpid()
    
    # Create lock if needed (per event loop)
    if _pool_lock is None:
        _pool_lock = asyncio.Lock()
    
    async with _pool_lock:
        # If pool exists but was created in a different process, close it
        if _pool is not None and _pool_pid != current_pid:
            logger.warning(f"Detected new process (pid {current_pid}), closing old pool from pid {_pool_pid}")
            try:
                await _pool.close()
            except Exception as e:
                logger.warning(f"Error closing old pool: {e}")
            _pool = None
            _pool_pid = None
        
        # Create new pool if needed
        if _pool is None:
            logger.info(f"Creating new database pool for process {current_pid}")
            _pool = DatabasePool()
            await _pool.initialize()
            _pool_pid = current_pid
        
        return _pool


async def close_db_pool() -> None:
    """Close the global database pool"""
    global _pool
    
    async with _pool_lock:
        if _pool:
            await _pool.close()
            _pool = None
