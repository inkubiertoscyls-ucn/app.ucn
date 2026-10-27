"""
Configuration settings for INKubiertos backend.
Loads from environment variables or Streamlit secrets.
"""
import os
from typing import Optional
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Cargar el archivo .env ubicado en la raíz del proyecto
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)


@dataclass
class Settings:
    """Application settings."""
    supabase_url: str
    supabase_key: str
    supabase_service_role_key: Optional[str] = None
    app_env: str = "development"
    log_level: str = "INFO"
    auth_enabled: bool = False
    session_timeout_minutes: int = 60
    
    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        supabase_url = os.getenv("SUPABASE_URL", "")
        supabase_key = os.getenv("SUPABASE_KEY", "")
        supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY must be set. "
                "Check .env or Streamlit secrets."
            )
        
        return cls(
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            supabase_service_role_key=supabase_service_role_key,
            app_env=os.getenv("APP_ENV", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            auth_enabled=os.getenv("AUTH_ENABLED", "false").lower() == "true",
            session_timeout_minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "60")),
        )
    
    @classmethod
    def from_streamlit_secrets(cls) -> "Settings":
        """Load settings from Streamlit secrets."""
        try:
            import streamlit as st
            supabase_config = st.secrets.get("supabase", {})
            supabase_url = supabase_config.get("url", "") or st.secrets.get("SUPABASE_URL", "")
            supabase_key = supabase_config.get("key", "") or st.secrets.get("SUPABASE_KEY", "")
            supabase_service_role_key = supabase_config.get("service_role_key") or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
            
            if not supabase_url or not supabase_key:
                raise ValueError("Supabase credentials not found in Streamlit secrets")
            
            return cls(
                supabase_url=supabase_url,
                supabase_key=supabase_key,
                supabase_service_role_key=supabase_service_role_key,
                app_env=st.secrets.get("APP_ENV", "development"),
                log_level=st.secrets.get("LOG_LEVEL", "INFO"),
                auth_enabled=st.secrets.get("AUTH_ENABLED", False),
                session_timeout_minutes=int(st.secrets.get("SESSION_TIMEOUT_MINUTES", 60)),
            )
        except Exception as e:
            raise ValueError(f"Failed to load Streamlit secrets: {e}")


def get_settings(use_streamlit: bool = False) -> Settings:
    """
    Get application settings.
    Try Streamlit secrets first if use_streamlit=True, else environment variables.
    """
    if use_streamlit:
        try:
            return Settings.from_streamlit_secrets()
        except Exception:
            # Fallback to environment
            return Settings.from_env()
    return Settings.from_env()
