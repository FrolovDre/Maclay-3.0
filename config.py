"""
Конфигурация приложения AI Research Assistant
"""

import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

class Config:
    """Конфигурация приложения"""
    
    # Hugging Face / DeepSeek API
    HF_API_TOKEN = os.getenv("HF_API_TOKEN", "your-deepseek-api-key-here")
    HF_MODEL = os.getenv("HF_MODEL", "deepseek-ai/DeepSeek-R1")
    HF_API_URL = os.getenv("HF_API_URL", "https://api-inference.huggingface.co")
    
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
        
        if not cls.HF_API_TOKEN or not cls.HF_API_TOKEN.startswith("hf_"):
            errors.append("HF_API_TOKEN не настроен или некорректен. Добавьте токен Hugging Face в .env файл")
        
        if cls.PORT < 1 or cls.PORT > 65535:
            errors.append("Некорректный порт. Должен быть от 1 до 65535")
        
        # Validate local data directory exists
        if not os.path.isdir(cls.DATA_DIR):
            errors.append(f"Каталог с локальными документами не найден: {cls.DATA_DIR}")
        
        return errors

# Создаем экземпляр конфигурации
config = Config()
