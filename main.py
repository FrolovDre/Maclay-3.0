from fastapi import FastAPI, Request, Form, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
import asyncio
import os
import uuid
from dotenv import load_dotenv
import json
from datetime import datetime
from config import config
from database import init_database, get_db, ResearchReport, UserSession
from services import ReportService, SessionManager
from sqlalchemy.orm import Session
import asyncio
from typing import Dict, List, Any
from research_stages import ResearchProcessor

load_dotenv()


async def call_deepseek(prompt: str, temperature: float = 0.7, max_new_tokens: int = 4096) -> str:
    """Call DeepSeek model via Hugging Face Inference API"""
    api_url = f"{config.HF_API_URL}/models/{config.HF_MODEL}"
    headers = {
        "Authorization": f"Bearer {config.HF_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": temperature,
            "max_new_tokens": max_new_tokens,
            "return_full_text": False,
        },
    }

    async with httpx.AsyncClient(timeout=600.0) as client:
        max_retries = 5
        attempt = 0

        while attempt < max_retries:
            try:
                response = await client.post(api_url, headers=headers, json=payload)
                if response.status_code == 503:
                    await asyncio.sleep(5)
                    continue
                response.raise_for_status()
                result = response.json()
                return extract_generated_text(result)
            except Exception as e:
                attempt += 1
                if attempt >= max_retries:
                    raise e
                await asyncio.sleep(2 ** attempt)


def extract_generated_text(result: Any) -> str:
    """Extract generated text from Hugging Face response"""
    if isinstance(result, list) and result:
        item = result[0]
        if isinstance(item, dict):
            return item.get("generated_text") or item.get("text") or ""
        if isinstance(item, str):
            return item
    if isinstance(result, dict):
        return result.get("generated_text") or result.get("text") or ""
    return ""

app = FastAPI(
    title=config.APP_NAME,
    description=config.APP_DESCRIPTION,
    version=config.APP_VERSION
)

# Подключение статических файлов и шаблонов
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            print(f"🔌 Клиент {client_id} отключен")
    
    def cleanup_disconnected(self):
@@ -237,68 +286,68 @@ async def process_research_background(research_data: Dict[str, Any], research_ty
        
        # Process research without timeout
        result = await processor.process_research(research_data, research_type)
        
        if result["success"]:
            # Save report to database
            report_service = ReportService(db)
            
            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # Create report
            if research_type == "feature":
                title = f"Исследование фичи: {research_data.get('research_element', '')[:50]}..."
                report = report_service.create_report(
                    title=title,
                    content=result["report"],
                    research_type="feature",
                    product_description=research_data.get('product_description', ''),
                    segment=research_data.get('segment', ''),
                    research_element=research_data.get('research_element', ''),
                    benchmarks=research_data.get('benchmarks', ''),
                    required_players=research_data.get('required_players', ''),
                    required_countries=research_data.get('required_countries', ''),
                    session_id=session_id,
                    ai_model=config.HF_MODEL,
                    processing_time=120,  # 2 minutes
                    tokens_used=len(result["report"].split()) * 1.3  # Approximate
                )
            else:  # product research
                title = f"Исследование продукта: {research_data.get('product_characteristics', '')[:50]}..."
                report = report_service.create_report(
                    title=title,
                    content=result["report"],
                    research_type="product",
                    product_description=research_data.get('product_description', ''),
                    segment=research_data.get('segment', ''),
                    research_element=research_data.get('product_characteristics', ''),
                    benchmarks="",
                    required_players=research_data.get('required_players', ''),
                    required_countries=research_data.get('required_countries', ''),
                    session_id=session_id,
                    ai_model=config.HF_MODEL,
                    processing_time=120,
                    tokens_used=len(result["report"].split()) * 1.3
                )
            
            # Send completion message
            await manager.send_message(client_id, {
                "type": "completion",
                "success": True,
                "report_id": report.id,
                "message": "Исследование завершено успешно",
                "timestamp": datetime.now().isoformat()
            })
            
        else:
            # Send error message
            await manager.send_message(client_id, {
                "type": "completion",
                "success": False,
                "error": result.get("error", "Неизвестная ошибка"),
                "message": "Ошибка при выполнении исследования",
                "timestamp": datetime.now().isoformat()
            })
            
    except Exception as e:
        import traceback
@@ -581,169 +630,113 @@ Mapping к нашим целям/метрикам: какие north-star/под
«Списки без анализа применимости».

Проверки перед сдачей (чек-лист)

 10+ кейсов, пронумерованы.

 В каждом кейсе есть: сайт компании, страна, 4–5 предложений о продукте, источники, скриншоты, подписи, перевод при необходимости. 

 Таблица обзора заполнена для всех кейсов.

 Указаны даты публикаций/обновлений.

 Есть секция «Применимость» и «План внедрения».

 Все ссылки открываются.

Тон и стиль

Нейтрально-деловой, кратко, по делу.

Сначала выводы, потом детали.

Ясные формулировки, избегай жаргона.
"""

    try:
        report_content = await call_deepseek(prompt, temperature=0.7, max_new_tokens=4096)

        # Сохраняем отчет в базу данных
        report_service = ReportService(db)
        session_manager = SessionManager(db)

        # Получаем или создаем сессию
        session_id = request.cookies.get("session_id")
        if not session_id:
            session_id = session_manager.create_session(
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent")
            )

        # Создаем отчет
        if research_type == "feature":
            title = f"Исследование: {research_element}"
            report = report_service.create_report(
                title=title,
                content=report_content,
                research_type="feature",
                product_description=product_description,
                segment=segment,
                research_element=research_element,
                benchmarks=benchmarks,
                required_players=required_players,
                required_countries=required_countries,
                session_id=session_id,
                ai_model=config.HF_MODEL,
                processing_time=30,  # Примерное время
                tokens_used=len(report_content.split())  # Примерное количество токенов
            )
        else:  # research_type == "product"
            title = f"Исследование продукта: {product_characteristics[:50]}..."
            report = report_service.create_report(
                title=title,
                content=report_content,
                research_type="product",
                product_description=product_description,
                segment=segment,
                research_element=product_characteristics,  # Используем характеристики продукта
                benchmarks="",  # Не используется для product
                required_players=required_players,
                required_countries=required_countries,
                session_id=session_id,
                ai_model=config.HF_MODEL,
                processing_time=30,  # Примерное время
                tokens_used=len(report_content.split())  # Примерное количество токенов
            )

        return {
            "success": True,
            "report": report_content,
            "report_id": report.id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"API Error: {str(e)}",
            "message": "Ошибка при генерации отчета"
        }

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    print(f"🔌 WebSocket подключение для клиента: {client_id}")
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"📨 Получено сообщение от {client_id}: {data}")
            # Handle incoming messages if needed
    except WebSocketDisconnect:
        print(f"🔌 WebSocket отключение для клиента: {client_id}")
        manager.disconnect(client_id)

@app.get("/status/{client_id}")
async def check_status(client_id: str):
    """Check status of research process"""
    if client_id in manager.active_connections:
        return {
            "status": "active",
            "message": "Исследование в процессе"
        }
    else:
        return {
            "status": "inactive", 
