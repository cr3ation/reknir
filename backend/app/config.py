from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Database
    database_url: str = "postgresql://reknir:reknir@localhost:5432/reknir"

    # CORS (can be comma-separated string or JSON array)
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Application
    app_name: str = "Reknir - Swedish Bookkeeping"
    debug: bool = True

    # Backup
    backup_dir: str = "/backups"

    # Authentication
    secret_key: str = "your-secret-key-change-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins as list"""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",")]
        return self.cors_origins


settings = Settings()
