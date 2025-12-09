"""
Database models and configuration for Maclay Research Assistant
"""

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/maclay_research.db")

# Create engine
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class ResearchReport(Base):
    """Model for storing research reports"""
    __tablename__ = "research_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    research_type = Column(String(50), nullable=False)  # 'feature', 'product', 'gap'
    
    # Research parameters
    product_description = Column(Text)
    segment = Column(String(50))  # 'ЮЛ' or 'ФЛ'
    research_element = Column(Text)
    benchmarks = Column(Text)
    required_players = Column(Text)
    required_countries = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # AI response metadata
    ai_model = Column(String(100), default="mistral")
    processing_time = Column(Integer)  # seconds
    tokens_used = Column(Integer)
    
    def __repr__(self):
        return f"<ResearchReport(id={self.id}, title='{self.title}', type='{self.research_type}')>"

class UserSession(Base):
    """Model for storing user sessions"""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    reports = relationship("ResearchReport", back_populates="session")
    
    def __repr__(self):
        return f"<UserSession(id={self.id}, session_id='{self.session_id}')>"

# Add relationship to ResearchReport
ResearchReport.session_id = Column(Integer, ForeignKey("user_sessions.id"))
ResearchReport.session = relationship("UserSession", back_populates="reports")

def create_tables():
    """Create all tables in the database"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """Initialize database with tables"""
    import os
    
    try:
        # Create data directory if it doesn't exist
        data_dir = os.path.dirname(DATABASE_URL.replace("sqlite:///", ""))
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            print(f"✅ Created data directory: {data_dir}")
        
        # Create database file if it doesn't exist
        db_path = DATABASE_URL.replace("sqlite:///", "")
        if not os.path.exists(db_path):
            print(f"✅ Creating new database: {db_path}")
        
        # Create tables
        create_tables()
        print("✅ Database tables created successfully")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        raise

if __name__ == "__main__":
    init_database()
