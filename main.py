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
        """Очистка отключенных соединений"""
        disconnected_clients = []
        for client_id, websocket in self.active_connections.items():
            if websocket.client_state.name != "CONNECTED":
                disconnected_clients.append(client_id)
        
        for client_id in disconnected_clients:
            self.disconnect(client_id)
            print(f"🧹 Очищен отключенный клиент: {client_id}")

    async def send_message(self, client_id: str, message: dict):
        print(f"📤 Отправляем сообщение клиенту {client_id}: {message}")
        # Очищаем отключенные соединения перед отправкой
        self.cleanup_disconnected()
        
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                # Проверяем состояние соединения
                if websocket.client_state.name == "CONNECTED":
                    await websocket.send_text(json.dumps(message))
                    print(f"✅ Сообщение отправлено клиенту {client_id}")
                else:
                    print(f"⚠️ WebSocket клиента {client_id} не в состоянии CONNECTED: {websocket.client_state.name}")
                    self.disconnect(client_id)
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"❌ Ошибка отправки сообщения клиенту {client_id}: {e}")
                print(f"📋 Детали ошибки WebSocket:\n{error_details}")
                self.disconnect(client_id)
        else:
            print(f"⚠️ Клиент {client_id} не найден в активных соединениях")
            print(f"📋 Активные соединения: {list(self.active_connections.keys())}")

manager = ConnectionManager()

# Initialize database
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_database()
    print("✅ Database initialized")

# Проверяем конфигурацию при запуске
config_errors = config.validate_config()
if config_errors:
    print("⚠️  Предупреждения конфигурации:")
    for error in config_errors:
        print(f"   - {error}")

@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/feature", response_class=HTMLResponse)
async def feature_form(request: Request):
    return templates.TemplateResponse("feature_form.html", {"request": request})

@app.get("/product", response_class=HTMLResponse)
async def product_form(request: Request):
    return templates.TemplateResponse("product_form.html", {"request": request})

@app.get("/loading", response_class=HTMLResponse)
async def loading_page(request: Request):
    """Loading page for research process"""
    # Try to get research data from session or return empty data
    research_data = {
        "product_description": "",
        "segment": "",
        "research_element": "",
        "product_characteristics": "",
        "benchmarks": "",
        "required_players": "",
        "required_countries": ""
    }
    
    return templates.TemplateResponse("loading.html", {
        "request": request,
        "research_data": research_data
    })

@app.post("/process-feature")
async def process_feature(
    request: Request,
    product_description: str = Form(...),
    segment: str = Form(...),
    research_element: str = Form(...),
    benchmarks: str = Form(""),
    required_players: str = Form(""),
    required_countries: str = Form(""),
    db: Session = Depends(get_db)
):
    # Сохраняем данные для обработки
    research_data = {
        "product_description": product_description,
        "segment": segment,
        "research_element": research_element,
        "benchmarks": benchmarks,
        "required_players": required_players,
        "required_countries": required_countries
    }
    
    return templates.TemplateResponse("loading.html", {
        "request": request,
        "research_data": research_data
    })

@app.post("/process-product")
async def process_product(
    request: Request,
    product_description: str = Form(...),
    segment: str = Form(...),
    product_characteristics: str = Form(...),
    required_players: str = Form(""),
    required_countries: str = Form(""),
    db: Session = Depends(get_db)
):
    # Сохраняем данные для обработки
    research_data = {
        "product_description": product_description,
        "segment": segment,
        "product_characteristics": product_characteristics,
        "required_players": required_players,
        "required_countries": required_countries
    }
    
    return templates.TemplateResponse("loading.html", {
        "request": request,
        "research_data": research_data
    })

@app.post("/generate-report")
async def generate_report(request: Request, db: Session = Depends(get_db)):
    """Generate report using improved multi-stage process"""
    try:
        # Get data from request
        data = await request.json()
        
        # Extract research data
        product_description = data.get('product_description', '')
        segment = data.get('segment', '')
        research_element = data.get('research_element', '')
        product_characteristics = data.get('product_characteristics', '')
        benchmarks = data.get('benchmarks', '')
        required_players = data.get('required_players', '')
        required_countries = data.get('required_countries', '')
        
        # Determine research type
        research_type = "feature" if research_element else "product"
        
        # Create research data dict
        research_data = {
            "product_description": product_description,
            "segment": segment,
            "research_element": research_element,
            "product_characteristics": product_characteristics,
            "benchmarks": benchmarks,
            "required_players": required_players,
            "required_countries": required_countries
        }
        
        # Get client ID from request or generate new one
        client_id = data.get('client_id', str(uuid.uuid4()))
        
        print(f"🔗 Используем client_id: {client_id}")
        
        # Start research processing in background
        asyncio.create_task(process_research_background(research_data, research_type, client_id, db))
        
        return {
            "success": True,
            "client_id": client_id,
            "message": "Исследование запущено"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Ошибка при запуске исследования"
        }

async def process_research_background(research_data: Dict[str, Any], research_type: str, client_id: str, db: Session):
    """Process research in background with real-time updates"""
    try:
        print(f"🚀 Запускаем фоновое исследование для клиента {client_id}")
        
        # Initialize research processor
        processor = ResearchProcessor(config, manager, client_id)
        
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
                    ai_model=config.GEMINI_MODEL,
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
                    ai_model=config.GEMINI_MODEL,
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
        error_details = traceback.format_exc()
        print(f"❌ Критическая ошибка в фоновом исследовании: {str(e)}")
        print(f"📋 Детали критической ошибки:\n{error_details}")
        
        # Send error message
        await manager.send_message(client_id, {
            "type": "completion",
            "success": False,
            "error": str(e),
            "error_details": error_details,
            "message": "Критическая ошибка при выполнении исследования",
            "timestamp": datetime.now().isoformat()
        })

@app.post("/generate-report-old")
async def generate_report_old(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    
    # Извлекаем данные из запроса
    product_description = data.get('product_description', '')
    segment = data.get('segment', '')
    research_element = data.get('research_element', '')
    benchmarks = data.get('benchmarks', '')
    required_players = data.get('required_players', '')
    required_countries = data.get('required_countries', '')
    
    # Новые поля для исследования продукта
    product_characteristics = data.get('product_characteristics', '')
    
    # Определяем тип исследования
    research_type = "feature" if research_element else "product"
    
    # Создаем промпт для Mistral в зависимости от типа исследования
    if research_type == "feature":
        prompt = f"""
Роль

Ты — старший аналитик по финтеху/банкам/супераппам. Работаешь как исследователь рынка + UX-разведчик: быстро находишь и верифицируешь продуктовые фичи у международных игроков и формируешь пригодные к внедрению инсайты для Product Manager.

Цель

Собрать и проверить лучшие практики/фичи по заданному элементу продукта.

Показать применимость к нашему контексту (value, риски, усилия внедрения).

Дать минимум 10 подтверждённых кейсов с источниками и скриншотами.

Входные параметры (подставь из запроса)
- Описание продукта и бизнес-контекста: {product_description}
- Сегмент: {segment}
- Что исследуем (элемент продукта): {research_element}
- Известные бенчмарки (если есть): {benchmarks}
- Обязательные игроки к рассмотрению (если есть): {required_players}
- Обязательные страны к рассмотрению (если есть): {required_countries}

Обязательные источники и приоритет
- Официальные сайты/документы компаний (прайсы, релизы, справки, help-центры).
- Отчёты консалтинга/исследовательских агентств (в т.ч. UX/UI).
- Карточки приложений в App Store / Google Play (описания, скриншоты, отзывы).
- Профильные медиа/новости, тех-блоги компаний.
- Другие релевантные источники.

КРИТИЧЕСКИ ВАЖНО ДЛЯ ССЫЛОК:
- Используй ТОЛЬКО проверенные и доступные ссылки
- Проверяй актуальность каждой ссылки перед включением
- Предпочитай официальные источники (сайты компаний, документация)
- Избегай ссылок на временные или устаревшие страницы
- Если ссылка недоступна или сомнительна - НЕ включай её
- Лучше меньше ссылок, но все должны быть рабочими
- На каждый факт давай ссылку. Если данные спорные — пометь «(требует верификации)».

Метод

Сначала коротко сформулируй гипотезы пользы фичи для нашего контекста.

Делай целенаправленные запросы по странам/игрокам/кейвордам.

Для каждой фичи: фиксируй первоисточник, дату публикации/обновления и географию доступности.

Проверяй актуальность (дата релиза/последнего апдейта, наличие в текущей версии приложения).

Формат итоговой выдачи
1) Краткое резюме (до 10 пунктов)

Что нашли, почему важно, краткий список «quick wins», риски и зависимости.

2) 10+ кейсов (по шаблону, строго пронумеруй)

Компания: Название — ссылка на сайт.

Краткое описание (1 предложение): ...

Страна регистрации: ...

Подробное описание фичи (4–5 предложений):
— Как работает / где в пользовательском пути.
— Для кого / какие триггеры.
— Метрики/результаты (если есть, со ссылкой).

Ссылки на источники: полный список, каждая ссылка отдельным пунктом.

Скриншоты фичи: вставь изображения; подпиши, что на них (экран/шаг/состояние).

Перевод скриншотов (если не RU/EN): полный, с разбивкой по блокам.

4) Применимость к нашему продукту

Mapping к нашим целям/метрикам: какие north-star/подметрики заденет.

Локализация и регуляторика: AML/KYC, платежные лицензии, персональные данные, санкционные и иные ограничения.

Технические зависимости: данные/интеграции, изменения в бэке/клиенте, аналитика.

Риски и способы их снижения.
Требования к качеству
Минимум 10 кейсов, лучше 12–15, но без «воды».

Все факты — с активными ссылками на первоисточники.

Даты релизов/обновлений указывать в каждом кейсе.

ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ К ССЫЛКАМ:
- Каждая ссылка должна быть проверена на доступность
- Предпочитай официальные источники (сайты компаний, документация)
- Избегай ссылок на временные страницы, блоги с неопределенным статусом
- Если ссылка сомнительна - лучше не включать её вообще
- Лучше меньше ссылок, но все должны быть рабочими и релевантными
- Проверяй актуальность ссылок

Не использовать непроверяемые источники; если используешь обзоры/агрегаторы — обязательно находи первоисточник.

Отмечай гео-ограничения фич (доступность по странам/рынкам).

Если чего-то не нашлось, так и напиши «не найдено/редко встречается», предложи обходные пути поиска.

Что исключить

Голые мнения без подтверждений.

Копирование маркетинговых лозунгов без верификации в продукте.

Скриншоты без подписи и контекста.

«Списки без анализа применимости».

Проверки перед сдачей (чек-лист)

 10+ кейсов, пронумерованы.

 В каждом кейсе есть: сайт компании, страна, 4–5 предложений о фиче, источники, скриншоты, подписи, перевод при необходимости.

 Таблица обзора заполнена для всех кейсов.

 Указаны даты публикаций/обновлений.

 Есть секция «Применимость» и «План внедрения».

 Все ссылки открываются.

Тон и стиль

Нейтрально-деловой, кратко, по делу.

Сначала выводы, потом детали.

Ясные формулировки, избегай жаргона.
"""
    else:  # research_type == "product"
        prompt = f"""
Роль

Ты — старший аналитик по финтеху/банкам/супераппам. Работаешь как исследователь рынка + UX-разведчик: быстро находишь новые продукты международных игроков и формируешь пригодные к внедрению инсайты для Product Manager. 

Цель

Собрать и проверить наиболее подходящие продукты по описанию Product Manager. 

Показать применимость к нашему контексту (value, риски, усилия внедрения).

Дать минимум 10 подтверждённых кейсов с источниками и скриншотами.

Входные параметры (подставь из запроса)
- Описание бизнес-контекста: {product_description}
- Сегмент: {segment}
- Характеристики продукта, который требуется найти: {product_characteristics}
- Обязательные игроки к рассмотрению (если есть): {required_players}
- Обязательные страны к рассмотрению (если есть): {required_countries}

Обязательные источники и приоритет
- Официальные сайты/документы компаний (прайсы, релизы, справки, help-центры).
- Отчёты консалтинга/исследовательских агентств (в т.ч. UX/UI).
- Карточки приложений в App Store / Google Play (описания, скриншоты, отзывы).
- Профильные медиа/новости, тех-блоги компаний.
- Другие релевантные источники.

КРИТИЧЕСКИ ВАЖНО ДЛЯ ССЫЛОК:
- Используй ТОЛЬКО проверенные и доступные ссылки
- Проверяй актуальность каждой ссылки перед включением
- Предпочитай официальные источники (сайты компаний, документация)
- Избегай ссылок на временные или устаревшие страницы
- Если ссылка недоступна или сомнительна - НЕ включай её
- Лучше меньше ссылок, но все должны быть рабочими
- На каждый факт давай ссылку. Если данные спорные — пометь «(требует верификации)».

Метод

Сначала коротко сформулируй гипотезы пользы продукта для бизнеса. 

Делай целенаправленные запросы по странам/игрокам/кейвордам.

Для каждого продукта: фиксируй первоисточник, дату публикации/обновления и географию доступности. 

Проверяй актуальность (дата релиза/последнего апдейта, наличие в текущей версии приложения).

Формат итоговой выдачи
1) Краткое резюме (до 10 пунктов)

Что нашли, почему важно, краткий список «quick wins», риски и зависимости.

2) 10+ кейсов (по шаблону, строго пронумеруй)

Компания: Название — ссылка на сайт.

Краткое описание (1 предложение): ...

Страна регистрации: ...

Подробное описание продукта (4–5 предложений): 
— Как работает / как устроен UX/UI 
— Для кого / какие триггеры.
— Метрики/результаты (если есть, со ссылкой).

Ссылки на источники: полный список, каждая ссылка отдельным пунктом.

Скриншоты продукта: вставь изображения; подпиши, что на них (экран/шаг/состояние). 

Перевод скриншотов (если не RU/EN): полный, с разбивкой по блокам.

4) Применимость к нашему бизнесу

Mapping к нашим целям/метрикам: какие north-star/подметрики заденет.

Локализация и регуляторика: AML/KYC, платежные лицензии, персональные данные, санкционные и иные ограничения.

Технические зависимости: данные/интеграции, изменения в бэке/клиенте, аналитика.

Риски и способы их снижения.
Требования к качеству
Минимум 10 кейсов, лучше 12–15, но без «воды».

Все факты — с активными ссылками на первоисточники.

Даты релизов/обновлений указывать в каждом кейсе.

ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ К ССЫЛКАМ:
- Каждая ссылка должна быть проверена на доступность
- Предпочитай официальные источники (сайты компаний, документация)
- Избегай ссылок на временные страницы, блоги с неопределенным статусом
- Если ссылка сомнительна - лучше не включать её вообще
- Лучше меньше ссылок, но все должны быть рабочими и релевантными
- Проверяй актуальность ссылок (не старше 2 лет для большинства источников)

Не использовать непроверяемые источники; если используешь обзоры/агрегаторы — обязательно находи первоисточник.

Отмечай гео-ограничения продуктов (доступность по странам/рынкам). 

Если чего-то не нашлось, так и напиши «не найдено/редко встречается», предложи обходные пути поиска.

Что исключить

Голые мнения без подтверждений.

Копирование маркетинговых лозунгов без верификации в продукте.

Скриншоты без подписи и контекста.

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

    # Отправляем запрос к Gemini API
    async with httpx.AsyncClient(timeout=600.0) as client:  # 10 minutes for HTTP requests
        # Retry logic for 503 errors (model overloaded)
        max_retries = 5
        attempt = 0
        
        while attempt < max_retries:
            try:
                response = await client.post(
                    config.GEMINI_API_URL,
                    headers={
                        "Content-Type": "application/json"
                    },
                    params={
                        "key": config.GEMINI_API_KEY
                    },
                    json={
                        "contents": [
                            {
                                "parts": [
                                    {
                                        "text": prompt
                                    }
                                ]
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.7,
                            "topP": 0.8,
                            "topK": 40
                        }
                    }
                )
                
                # Check for 503 error (model overloaded)
                if response.status_code == 503:
                    error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                    error_message = error_data.get('error', {}).get('message', 'Model overloaded')
                    
                    print(f"⚠️ Модель перегружена (503), повторяем через 5 секунд... (попытка не засчитывается)")
                    await asyncio.sleep(5)  # Wait 5 seconds before retry
                    # НЕ увеличиваем attempt для 503 ошибки - не тратим попытки
                    continue
                
                # If not 503, break out of retry loop
                break
                
            except Exception as e:
                attempt += 1
                print(f"❌ Ошибка на попытке {attempt}: {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise e
        
        if response.status_code == 200:
            result = response.json()
            report_content = result["candidates"][0]["content"]["parts"][0]["text"]
            
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
                    ai_model=config.GEMINI_MODEL,
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
                    ai_model=config.GEMINI_MODEL,
                    processing_time=30,  # Примерное время
                    tokens_used=len(report_content.split())  # Примерное количество токенов
                )
            
            return {
                "success": True,
                "report": report_content,
                "report_id": report.id,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": f"API Error: {response.status_code}",
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
            "message": "Соединение потеряно"
        }

@app.get("/results", response_class=HTMLResponse)
async def results_page(request: Request, report_id: int = None, db: Session = Depends(get_db)):
    report_content = ""
    report_title = "Отчет не найден"
    
    if report_id:
        # Загружаем отчет из базы данных
        report_service = ReportService(db)
        report = report_service.get_report(report_id)
        if report:
            report_content = report.content
            report_title = report.title
        else:
            report_content = "Отчет с указанным ID не найден."
    else:
        # Получаем report из query параметра (для обратной совместимости)
        report = request.query_params.get("report", "")
        report_content = report
        report_title = "Результат исследования"
    
    return templates.TemplateResponse("results.html", {
        "request": request,
        "report": report_content,
        "report_id": report_id,
        "report_title": report_title
    })

@app.get("/reports")
async def get_reports(request: Request, db: Session = Depends(get_db)):
    """Получить список отчетов"""
    report_service = ReportService(db)
    session_id = request.cookies.get("session_id")
    
    if session_id:
        reports = report_service.get_reports_by_session(session_id)
    else:
        reports = report_service.get_recent_reports(10)
    
    return {
        "reports": [
            {
                "id": report.id,
                "title": report.title,
                "research_type": report.research_type,
                "created_at": report.created_at.isoformat(),
                "research_element": report.research_element
            }
            for report in reports
        ]
    }

@app.get("/reports/{report_id}")
async def get_report(report_id: int, db: Session = Depends(get_db)):
    """Получить конкретный отчет"""
    report_service = ReportService(db)
    report = report_service.get_report(report_id)
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return {
        "id": report.id,
        "title": report.title,
        "content": report.content,
        "research_type": report.research_type,
        "created_at": report.created_at.isoformat(),
        "research_element": report.research_element,
        "segment": report.segment,
        "benchmarks": report.benchmarks,
        "required_players": report.required_players,
        "required_countries": report.required_countries
    }

@app.delete("/reports/{report_id}")
async def delete_report(report_id: int, db: Session = Depends(get_db)):
    """Удалить отчет"""
    report_service = ReportService(db)
    success = report_service.delete_report(report_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return {"message": "Report deleted successfully"}

@app.get("/data/{filename}")
async def download_pdf(filename: str):
    """Открыть PDF файл из папки data в браузере"""
    import os
    from pathlib import Path
    
    # Безопасность: проверяем, что файл существует и это PDF
    if not filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    file_path = Path(config.DATA_DIR) / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Проверяем, что файл находится в разрешенной директории
    if not file_path.resolve().is_relative_to(Path(config.DATA_DIR).resolve()):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type='application/pdf',
        headers={'Content-Disposition': 'inline'}  # Открывать в браузере, а не скачивать
    )

@app.post("/export-pdf")
async def export_pdf(request: Request):
    data = await request.json()
    report_content = data.get("report", "")
    
    # Здесь можно добавить логику экспорта в PDF
    # Пока возвращаем JSON с содержимым
    return {
        "success": True,
        "message": "PDF экспорт будет реализован",
        "content": report_content
    }
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="127.0.0.1",  # за Nginx лучше слушать только loopback
        port=8000,
        proxy_headers=True,
        forwarded_allow_ips="*",
        ws="websockets",
        ws_ping_interval=20,
        ws_ping_timeout=20,
        # ВАЖНО: пока держите один воркер (через run это всегда 1)
    )