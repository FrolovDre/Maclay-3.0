"""
Services for managing research reports and database operations
"""

from sqlalchemy.orm import Session
from database import ResearchReport, UserSession, get_db
from datetime import datetime
from typing import Optional, List
import uuid
import re

class ReportService:
    """Service for managing research reports"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def clean_report_content(self, content: str) -> str:
        """Clean report content by removing standalone single asterisks"""
        if not content:
            return content
        
        # Remove standalone single asterisks (not part of bold formatting)
        # This regex looks for single asterisks that are not part of **bold** or *italic* formatting
        cleaned_content = re.sub(r'(?<!\*)\*(?!\*)(?![^*]*\*)', '', content)
        
        # Remove asterisks after colons (like "Оценка сложности:* Средняя")
        cleaned_content = re.sub(r':\*\s*', ': ', cleaned_content)
        
        # Remove single asterisks after colon and space (like "Текст: *")
        cleaned_content = re.sub(r':\s*\*', ':', cleaned_content)
        
        # Remove multiple consecutive commas
        cleaned_content = re.sub(r',\s*,+', ',', cleaned_content)
        
        # Remove commas between links (like "link1, , link2")
        cleaned_content = re.sub(r',\s*,\s*', ', ', cleaned_content)
        
        # Remove trailing commas before links
        cleaned_content = re.sub(r',\s*\[', ' [', cleaned_content)
        
        # Remove leading commas after links
        cleaned_content = re.sub(r'\]\s*,', ']', cleaned_content)
        
        # Remove trailing commas at the end of lines or before empty space
        cleaned_content = re.sub(r',\s*$', '', cleaned_content, flags=re.MULTILINE)
        
        # Remove commas followed by only whitespace and nothing else
        cleaned_content = re.sub(r',\s*$', '', cleaned_content, flags=re.MULTILINE)
        
        # Remove commas before empty content (like "text, ")
        cleaned_content = re.sub(r',\s*$', '', cleaned_content, flags=re.MULTILINE)
        
        return cleaned_content
    
    def create_report(
        self,
        title: str,
        content: str,
        research_type: str,
        product_description: str = None,
        segment: str = None,
        research_element: str = None,
        benchmarks: str = None,
        required_players: str = None,
        required_countries: str = None,
        session_id: str = None,
        ai_model: str = "mistral",
        processing_time: int = None,
        tokens_used: int = None
    ) -> ResearchReport:
        """Create a new research report"""
        
        # Create or get user session
        if session_id:
            user_session = self.get_or_create_session(session_id)
        else:
            user_session = None
        
        # Clean the content before saving
        cleaned_content = self.clean_report_content(content)
        
        report = ResearchReport(
            title=title,
            content=cleaned_content,
            research_type=research_type,
            product_description=product_description,
            segment=segment,
            research_element=research_element,
            benchmarks=benchmarks,
            required_players=required_players,
            required_countries=required_countries,
            session_id=user_session.id if user_session else None,
            ai_model=ai_model,
            processing_time=processing_time,
            tokens_used=tokens_used
        )
        
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        
        return report
    
    def get_report(self, report_id: int) -> Optional[ResearchReport]:
        """Get a report by ID"""
        return self.db.query(ResearchReport).filter(
            ResearchReport.id == report_id,
            ResearchReport.is_active == True
        ).first()
    
    def get_reports_by_session(self, session_id: str) -> List[ResearchReport]:
        """Get all reports for a session"""
        user_session = self.get_session(session_id)
        if not user_session:
            return []
        
        return self.db.query(ResearchReport).filter(
            ResearchReport.session_id == user_session.id,
            ResearchReport.is_active == True
        ).order_by(ResearchReport.created_at.desc()).all()
    
    def get_recent_reports(self, limit: int = 10) -> List[ResearchReport]:
        """Get recent reports"""
        return self.db.query(ResearchReport).filter(
            ResearchReport.is_active == True
        ).order_by(ResearchReport.created_at.desc()).limit(limit).all()
    
    def search_reports(self, query: str) -> List[ResearchReport]:
        """Search reports by title or content"""
        return self.db.query(ResearchReport).filter(
            ResearchReport.is_active == True,
            (ResearchReport.title.contains(query) | 
             ResearchReport.content.contains(query))
        ).order_by(ResearchReport.created_at.desc()).all()
    
    def delete_report(self, report_id: int) -> bool:
        """Soft delete a report"""
        report = self.get_report(report_id)
        if report:
            report.is_active = False
            self.db.commit()
            return True
        return False
    
    def get_or_create_session(self, session_id: str, ip_address: str = None, user_agent: str = None) -> UserSession:
        """Get or create a user session"""
        session = self.db.query(UserSession).filter(
            UserSession.session_id == session_id
        ).first()
        
        if not session:
            session = UserSession(
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
        else:
            # Update last activity
            session.last_activity = datetime.utcnow()
            self.db.commit()
        
        return session
    
    def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get a session by ID"""
        return self.db.query(UserSession).filter(
            UserSession.session_id == session_id
        ).first()
    
    def get_report_stats(self) -> dict:
        """Get statistics about reports"""
        total_reports = self.db.query(ResearchReport).filter(
            ResearchReport.is_active == True
        ).count()
        
        reports_by_type = self.db.query(
            ResearchReport.research_type,
            self.db.func.count(ResearchReport.id)
        ).filter(
            ResearchReport.is_active == True
        ).group_by(ResearchReport.research_type).all()
        
        return {
            "total_reports": total_reports,
            "reports_by_type": dict(reports_by_type),
            "recent_reports_count": self.get_recent_reports(5)
        }

class SessionManager:
    """Manager for user sessions"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_session(self, ip_address: str = None, user_agent: str = None) -> str:
        """Create a new session"""
        session_id = str(uuid.uuid4())
        
        session = UserSession(
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get session by ID"""
        return self.db.query(UserSession).filter(
            UserSession.session_id == session_id
        ).first()
    
    def update_session_activity(self, session_id: str):
        """Update session last activity"""
        session = self.get_session(session_id)
        if session:
            session.last_activity = datetime.utcnow()
            self.db.commit()
