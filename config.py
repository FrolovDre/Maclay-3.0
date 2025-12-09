"""
Конфигурация приложения AI Research Assistant
"""

import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

class Config:
    """Конфигурация приложения"""
    
    # Google Gemini API
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your-gemini-api-key-here")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_API_URL = "https://generativelanguage.googleapis.com"
    
    # Server Configuration
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    BASE_URL = os.getenv("BASE_URL", "https://maclay.pro")
    
    # App Configuration
    APP_NAME = "AI Research Assistant"
    APP_VERSION = "1.0.0"
    APP_DESCRIPTION = "Современное приложение для продуктового исследования с ИИ"
    
    # File Upload Configuration
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.doc', '.docx'}
    
    # Report Configuration
    MAX_REPORT_LENGTH = 50000  # Максимальная длина отчета
    
    # Local Data Directory
    DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
    
    @classmethod
    def validate_config(cls):
        """Проверяет корректность конфигурации"""
        errors = []
        
        if not cls.GEMINI_API_KEY or cls.GEMINI_API_KEY == "your-gemini-api-key-here":
            errors.append("GEMINI_API_KEY не настроен. Добавьте ключ в .env файл")
        
        if cls.PORT < 1 or cls.PORT > 65535:
            errors.append("Некорректный порт. Должен быть от 1 до 65535")
        
        # Validate local data directory exists
        if not os.path.isdir(cls.DATA_DIR):
            errors.append(f"Каталог с локальными документами не найден: {cls.DATA_DIR}")
        
        return errors

# Создаем экземпляр конфигурации
config = Config()
