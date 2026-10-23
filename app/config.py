import os
from pydantic import BaseModel

class Settings(BaseModel):
    PROJECT_NAME: str = "Online Retail Machine Learning Backend"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # MySQL Database Config
    DB_HOST: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    DB_PORT: int = int(os.getenv("MYSQL_PORT", 3306))
    DB_USER: str = os.getenv("MYSQL_USER", "root")
    DB_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "123456")
    DB_NAME: str = os.getenv("MYSQL_DATABASE", "online_retail_db")
    
    # Server Config
    HOST: str = os.getenv("SERVER_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("SERVER_PORT", 8000))

settings = Settings()
