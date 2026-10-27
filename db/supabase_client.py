"""
Supabase client for INKubiertos backend.
Singleton pattern with error handling. No credentials logged.
"""
import logging
from typing import Optional
from supabase import create_client, Client

from config.settings import get_settings
from core.exceptions import SupabaseConnectionError

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Singleton Supabase client wrapper."""
    _instance: Optional["SupabaseClient"] = None
    _client: Optional[Client] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Supabase client from settings."""
        try:
            settings = get_settings(use_streamlit=False)
            self._client = create_client(settings.supabase_url, settings.supabase_key)
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {type(e).__name__}")
            raise SupabaseConnectionError(
                "Error al conectar con Supabase. Verifique configuración."
            ) from e
    
    @property
    def client(self) -> Client:
        """Get Supabase client instance."""
        if self._client is None:
            self._initialize_client()
        return self._client
    
    def table(self, table_name: str):
        """Get table reference."""
        return self.client.table(table_name)
    
    def rpc(self, function_name: str, params: dict = None):
        """Call RPC function."""
        if params is None:
            params = {}
        return self.client.rpc(function_name, params)
    
    def health_check(self) -> bool:
        """Check connection health."""
        try:
            # Try a simple query
            self.client.table("dim_area").select("*").limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"Health check failed: {type(e).__name__}")
            return False


def get_supabase_client() -> Client:
    """Get Supabase client instance."""
    return SupabaseClient().client
