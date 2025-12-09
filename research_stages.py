"""
Research stages and prompts for AI Research Assistant
"""

import asyncio
import httpx
from typing import Dict, List, Any
import os
import json
import re
import pdfplumber
import json
from datetime import datetime

class ResearchStage:
    """Base class for research stages"""
    
    def __init__(self, name: str, description: str, icon: str):
        self.name = name
        self.description = description
        self.icon = icon
        self.status = "pending"  # pending, active, completed, error
        self.progress = 0
        self.result = None
        self.error = None

class ResearchProcessor:
    """Main processor for research stages"""
    
    def __init__(self, config, manager, client_id: str):
        self.config = config
        self.manager = manager
        self.client_id = client_id
        self.stages = []
        self.current_stage = 0
        
    async def send_update(self, stage_name: str, status: str, progress: int, message: str = ""):
        """Send update to client via WebSocket"""
        await self.manager.send_message(self.client_id, {
            "type": "stage_update",
            "stage": stage_name,
            "status": status,
            "progress": progress,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
    
    async def _execute_with_retry(self, func, *args, stage_name: str, stage_description: str, max_retries: int = 3):
        """Execute function with retry mechanism"""
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                print(f"🔄 Попытка {attempt + 1}/{max_retries} для {stage_description}")
                
                if attempt > 0:
                    await self.send_update(stage_name, "active", 0, f"Повторная попытка {attempt + 1}/{max_retries}...")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff: 2, 4, 8 seconds
                
                result = await func(*args)
                print(f"✅ {stage_description} успешно выполнено с попытки {attempt + 1}")
                return result
                
            except (httpx.TimeoutException, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                last_exception = e
                print(f"⏰ Таймаут на попытке {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    await self.send_update(stage_name, "active", 0, f"Таймаут, повторяем через {2 ** (attempt + 1)} сек...")
                else:
                    await self.send_update(stage_name, "error", 0, f"Таймаут после {max_retries} попыток")
                    
            except Exception as e:
                last_exception = e
                print(f"❌ Ошибка на попытке {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    await self.send_update(stage_name, "active", 0, f"Ошибка, повторяем через {2 ** (attempt + 1)} сек...")
                else:
                    await self.send_update(stage_name, "error", 0, f"Ошибка после {max_retries} попыток")
        
        # If all retries failed, raise the last exception
        raise last_exception
    
    def clean_report_content(self, content: str) -> str:
        """Clean report content by removing standalone single asterisks"""
        if not content:
            return content
        
        import re
        
        # Remove single asterisks at the beginning of lines (improved)
        cleaned_content = re.sub(r'^\*\s+', '', content, flags=re.MULTILINE)
        cleaned_content = re.sub(r'^\*\s*$', '', cleaned_content, flags=re.MULTILINE)
        
        # Remove standalone single asterisks (not part of bold formatting)
        # This regex looks for single asterisks that are not part of **bold** or *italic* formatting
        cleaned_content = re.sub(r'(?<!\*)\*(?!\*)(?![^*]*\*)', '', cleaned_content)
        
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
    
    def get_available_pdf_files(self) -> List[str]:
        """Get list of available PDF files in data directory"""
        try:
            pdf_files = []
            for name in os.listdir(self.config.DATA_DIR):
                if name.lower().endswith(".pdf"):
                    pdf_files.append(name)
            return pdf_files
        except Exception as e:
            print(f"⚠️ Ошибка получения списка PDF файлов: {e}")
            return []
    
    async def process_research(self, research_data: Dict[str, Any], research_type: str) -> Dict[str, Any]:
        """Process research through all stages"""
        try:
            print(f"🚀 Начинаем исследование типа: {research_type}")
            print(f"📊 Данные исследования: {research_data}")
            
            # Stage 1: Data Collection
            print("📡 Этап 1: Сбор данных")
            await self.send_update("data_collection", "active", 0, "Собираем данные о рынке...")
            market_data = await self.collect_market_data(research_data, research_type)
            print(f"✅ Данные собраны: {len(market_data.get('companies', []))} компаний")
            
            # Stage 1.5: Local Documents Insights
            print("📚 Этап 1.5: Локальные документы (PDF)")
            await self.send_update("local_documents", "active", 0, "Ищем инсайты в локальных PDF...")
            local_insights = await self.collect_local_documents_insights(research_data, research_type)
            market_data["local_insights"] = local_insights or {"insights": [], "files": []}
            print(f"✅ Локальные инсайты: {len(market_data['local_insights'].get('insights', []))} фактов из {len(market_data['local_insights'].get('files', []))} файлов")
            
            # Stage 2: Case Analysis
            print("🔍 Этап 2: Анализ кейсов")
            await self.send_update("case_analysis", "active", 0, "Анализируем кейсы...")
            cases = await self.analyze_cases(market_data, research_data, research_type)
            print(f"✅ Кейсы проанализированы: {len(cases)} кейсов")
            
            # Stage 3: Report Generation
            print("📝 Этап 3: Генерация отчета")
            await self.send_update("report_generation", "active", 0, "Генерируем отчет...")
            report = await self.generate_report(cases, research_data, research_type)
            print(f"✅ Отчет готов: {len(report)} символов")
            
            # Stage 4: Link Verification (Final)
            print("🔗 Этап 4: Финальная проверка ссылок")
            await self.send_update("link_verification", "active", 0, "Проверяем все ссылки в отчете...")
            final_report = await self.verify_report_links(report)
            print(f"✅ Все ссылки проверены: {len(final_report)} символов")
            
            return {
                "success": True,
                "report": final_report,
                "stages_completed": 5
            }
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ Ошибка в процессе исследования: {str(e)}")
            print(f"📋 Детали ошибки:\n{error_details}")
            await self.send_update("error", "error", 0, f"Ошибка: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_details": error_details
            }
    
    async def collect_market_data(self, research_data: Dict[str, Any], research_type: str) -> Dict[str, Any]:
        """Stage 1: Collect market data with retry mechanism"""
        return await self._execute_with_retry(
            self._collect_market_data_internal,
            research_data,
            research_type,
            stage_name="data_collection",
            stage_description="сбора данных"
        )
    
    async def _collect_market_data_internal(self, research_data: Dict[str, Any], research_type: str) -> Dict[str, Any]:
        """Internal method for data collection"""
        await self.send_update("data_collection", "active", 10, "Подготавливаем запрос...")
        
        prompt = self.get_data_collection_prompt(research_data, research_type)
        print(f"📝 Промпт для сбора данных: {len(prompt)} символов")
        
        await self.send_update("data_collection", "active", 30, "Отправляем запрос к ИИ...")
        
        async with httpx.AsyncClient(timeout=270.0) as client:
            await self.send_update("data_collection", "active", 40, "Выполняем HTTP запрос...")
            api_url = f"{self.config.GEMINI_API_URL}/v1beta/models/{self.config.GEMINI_MODEL}:generateContent"
            print(f"🌐 Отправляем запрос к {api_url}")
            
            # Retry logic for 503 errors (model overloaded)
            max_retries = 5
            attempt = 0
            
            while attempt < max_retries:
                try:
                    response = await client.post(
                        api_url,
                        headers={
                            "Content-Type": "application/json",
                            "x-goog-api-key": self.config.GEMINI_API_KEY
                        },
                        json={
                            "contents": [{
                                "parts": [{"text": prompt}]
                            }],
                            "generationConfig": {
                                "temperature": 0.7
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
            
            print(f"📡 Получен ответ: {response.status_code}")
            await self.send_update("data_collection", "active", 70, "Обрабатываем ответ...")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Ответ успешно получен: {len(str(result))} символов")
                await self.send_update("data_collection", "active", 90, "Структурируем данные...")
                
                # Parse the response to extract structured data
                market_data = self.parse_market_data(result, research_type)
                
                await self.send_update("data_collection", "completed", 100, f"Найдено {len(market_data.get('companies', []))} компаний")
                
                return market_data
            else:
                error_msg = f"API Error: {response.status_code} - {response.text}"
                print(f"❌ {error_msg}")
                await self.send_update("data_collection", "error", 0, error_msg)
                raise Exception(error_msg)

    async def collect_local_documents_insights(self, research_data: Dict[str, Any], research_type: str) -> Dict[str, Any]:
        """Stage 1.5: Extract and summarize insights from local PDFs with retry"""
        return await self._execute_with_retry(
            self._collect_local_documents_insights_internal,
            research_data,
            research_type,
            stage_name="local_documents",
            stage_description="обработки локальных PDF"
        )

    def _read_pdf_text(self, file_path: str, max_chars: int = None) -> str:
        """Extract text from a PDF file - full text extraction"""
        text_parts: List[str] = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    if page_text:
                        text_parts.append(page_text)
                    # Remove character limit - extract full text
                    # if max_chars and sum(len(p) for p in text_parts) >= max_chars:
                    #     break
        except Exception as e:
            print(f"⚠️ Ошибка чтения PDF {file_path}: {e}")
        text = "\n".join(text_parts)
        # Normalize excessive whitespace
        text = re.sub(r"\s+", " ", text)
        # Return full text without character limit
        return text

    async def _collect_local_documents_insights_internal(self, research_data: Dict[str, Any], research_type: str) -> Dict[str, Any]:
        await self.send_update("local_documents", "active", 5, "Сканируем каталог с PDF...")
        data_dir = self.config.DATA_DIR
        pdf_files = []
        try:
            for name in os.listdir(data_dir):
                if name.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(data_dir, name))
        except Exception as e:
            await self.send_update("local_documents", "error", 0, f"Ошибка доступа к каталогу: {e}")
            return {"insights": [], "files": []}

        if not pdf_files:
            await self.send_update("local_documents", "completed", 100, "PDF не найдены")
            return {"insights": [], "files": []}

        await self.send_update("local_documents", "active", 10, f"Найдено документов: {len(pdf_files)}. Извлекаем текст...")
        files_payload: List[Dict[str, Any]] = []
        total_chars = 0
        
        # Process each PDF file with progress updates
        for i, f in enumerate(pdf_files):
            progress = int((i / len(pdf_files)) * 40) + 10  # 10-50%
            await self.send_update("local_documents", "active", progress, 
                                 f"Обрабатываем документ {i+1}/{len(pdf_files)}")
            
            print(f"📄 Обрабатываем PDF {i+1}/{len(pdf_files)}: {os.path.basename(f)}")
            
            text = self._read_pdf_text(f)  # Extract full text without character limit
            total_chars += len(text)
            files_payload.append({
                "file": os.path.basename(f),
                "excerpt": text
            })
            
            print(f"📊 PDF {i+1}: извлечено {len(text)} символов")
            
            # Small delay to show progress
            await asyncio.sleep(0.2)
        
        await self.send_update("local_documents", "active", 55, f"Текст извлечен из {len(files_payload)} документов")

        prompt = self.get_local_documents_prompt(files_payload, research_data, research_type)
        await self.send_update("local_documents", "active", 65, "Анализируем содержимое документов...")

        async with httpx.AsyncClient(timeout=120.0) as client:
            await self.send_update("local_documents", "active", 70, "Отправляем запрос к ИИ...")
            
            # Retry logic for 503 errors (model overloaded)
            max_retries = 5
            attempt = 0
            
            while attempt < max_retries:
                try:
                    response = await client.post(
                        f"{self.config.GEMINI_API_URL}/v1beta/models/{self.config.GEMINI_MODEL}:generateContent",
                        headers={
                            "Content-Type": "application/json",
                            "x-goog-api-key": self.config.GEMINI_API_KEY
                        },
                        json={
                            "contents": [{
                                "parts": [{"text": prompt}]
                            }],
                            "generationConfig": {
                                "temperature": 0.2
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

        if response.status_code != 200:
            await self.send_update("local_documents", "error", 0, f"API Error: {response.status_code}")
            return {"insights": [], "files": [f["file"] for f in files_payload]}

        await self.send_update("local_documents", "active", 85, "Обрабатываем ответ ИИ...")
        result = response.json()
        content = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        
        await self.send_update("local_documents", "active", 90, "Извлекаем структурированные инсайты...")
        insights = self.parse_local_insights(content)
        
        # Count insights by source file
        insights_by_file = {}
        for insight in insights:
            source_file = insight.get("source_file", "unknown.pdf")
            if source_file not in insights_by_file:
                insights_by_file[source_file] = 0
            insights_by_file[source_file] += 1
        
        # Create summary message without specific file names
        summary = f"Найдено {len(insights)} инсайтов из {len(files_payload)} документов"
        
        await self.send_update("local_documents", "completed", 100, summary)
        
        print(f"📈 ИТОГИ ОБРАБОТКИ PDF:")
        print(f"   Всего файлов: {len(files_payload)}")
        print(f"   Всего символов: {total_chars}")
        print(f"   Найдено инсайтов: {len(insights)}")
        for file, count in insights_by_file.items():
            print(f"   {file}: {count} инсайтов")
        
        return {"insights": insights, "files": [f["file"] for f in files_payload]}
    
    async def analyze_cases(self, market_data: Dict[str, Any], research_data: Dict[str, Any], research_type: str) -> List[Dict[str, Any]]:
        """Stage 2: Analyze cases with retry mechanism"""
        return await self._execute_with_retry(
            self._analyze_cases_internal,
            market_data,
            research_data,
            research_type,
            stage_name="case_analysis",
            stage_description="анализа кейсов"
        )
    
    async def _analyze_cases_internal(self, market_data: Dict[str, Any], research_data: Dict[str, Any], research_type: str) -> List[Dict[str, Any]]:
        """Internal method for case analysis"""
        await self.send_update("case_analysis", "active", 10, "Подготавливаем анализ кейсов...")
        
        prompt = self.get_case_analysis_prompt(market_data, research_data, research_type)
        
        await self.send_update("case_analysis", "active", 30, "Отправляем запрос на анализ...")
        
        async with httpx.AsyncClient(timeout=270.0) as client:
            # Retry logic for 503 errors (model overloaded)
            max_retries = 5
            attempt = 0
            
            while attempt < max_retries:
                try:
                    response = await client.post(
                        f"{self.config.GEMINI_API_URL}/v1beta/models/{self.config.GEMINI_MODEL}:generateContent",
                        headers={
                            "Content-Type": "application/json",
                            "x-goog-api-key": self.config.GEMINI_API_KEY
                        },
                        json={
                            "contents": [{
                                "parts": [{"text": prompt}]
                            }],
                            "generationConfig": {
                                "temperature": 0.5
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
            
            await self.send_update("case_analysis", "active", 70, "Обрабатываем результаты анализа...")
            
            if response.status_code == 200:
                result = response.json()
                await self.send_update("case_analysis", "active", 90, "Структурируем кейсы...")
                
                cases = self.parse_cases(result)
                await self.send_update("case_analysis", "completed", 100, f"Проанализировано {len(cases)} кейсов")
                
                return cases
            else:
                raise Exception(f"API Error: {response.status_code}")
    
    
    
    
    async def generate_report(self, cases: List[Dict[str, Any]], research_data: Dict[str, Any], research_type: str) -> str:
        """Stage 4: Generate final report with retry mechanism"""
        return await self._execute_with_retry(
            self._generate_report_internal,
            cases,
            research_data,
            research_type,
            stage_name="report_generation",
            stage_description="генерации отчета"
        )
    
    async def _generate_report_internal(self, cases: List[Dict[str, Any]], research_data: Dict[str, Any], research_type: str) -> str:
        """Internal method for report generation"""
        await self.send_update("report_generation", "active", 10, "Подготавливаем данные для отчета...")
        
        prompt = self.get_report_generation_prompt(cases, research_data, research_type)
        
        await self.send_update("report_generation", "active", 30, "Отправляем запрос на генерацию отчета...")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Retry logic for 503 errors (model overloaded)
            max_retries = 5
            attempt = 0
            
            while attempt < max_retries:
                try:
                    response = await client.post(
                        f"{self.config.GEMINI_API_URL}/v1beta/models/{self.config.GEMINI_MODEL}:generateContent",
                        headers={
                            "Content-Type": "application/json",
                            "x-goog-api-key": self.config.GEMINI_API_KEY
                        },
                        json={
                            "contents": [{
                                "parts": [{"text": prompt}]
                            }],
                            "generationConfig": {
                                "temperature": 0.3
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
            
            await self.send_update("report_generation", "active", 70, "Обрабатываем ответ...")
            
            if response.status_code == 200:
                result = response.json()
                await self.send_update("report_generation", "active", 90, "Форматируем отчет...")
                
                report_content = self.extract_report_content(result)
                
                # Enhance report with additional links
                await self.send_update("report_generation", "active", 95, "Добавляем дополнительные ссылки...")
                enhanced_report = await self.enhance_report_with_links(report_content, cases, research_data, research_type)
                
                # Clean the report content before final processing
                final_report = self.clean_report_content(enhanced_report)
                
                # Final report length check
                print(f"📊 ФИНАЛЬНЫЙ ОТЧЕТ:")
                print(f"   Длина отчета: {len(final_report)} символов")
                print(f"   Количество абзацев: {final_report.count(chr(10)) + 1}")
                print(f"   Количество ссылок: {final_report.count('[')}")
                
                await self.send_update("report_generation", "completed", 100, f"Отчет готов! ({len(final_report)} символов)")
                
                return final_report
            else:
                raise Exception(f"API Error: {response.status_code}")
    
    def get_data_collection_prompt(self, research_data: Dict[str, Any], research_type: str) -> str:
        """Get prompt for data collection stage"""
        if research_type == "feature":
            return f"""
Ты — эксперт по поиску и сбору данных о финтех-продуктах.

ЦЕЛЬ: Найти и собрать МАКСИМАЛЬНО ПОДРОБНУЮ информацию о компаниях, которые используют фичу "{research_data.get('research_element', '')}".

ПАРАМЕТРЫ ИССЛЕДОВАНИЯ:
- Продукт: {research_data.get('product_description', '')}
- Сегмент: {research_data.get('segment', '')}
- Элемент: {research_data.get('research_element', '')}
- Бенчмарки: {research_data.get('benchmarks', '')}
- Обязательные игроки: {research_data.get('required_players', '')}
- Обязательные страны: {research_data.get('required_countries', '')}

КРИТИЧЕСКИ ВАЖНО - ПОИСК ССЫЛОК:
1. Найди МИНИМУМ 15-20 компаний
2. Для КАЖДОЙ компании найди МИНИМУМ 8-10 ОФИЦИАЛЬНЫХ ССЫЛОК:
   - Официальный сайт компании
   - Социальные сети (LinkedIn, Twitter, Facebook)
   - Продуктовые страницы и функции
   - Кейсы использования и отзывы
   - Пресс-релизы и новости
   - Информация о финансировании
   - Партнерства и интеграции
   - Достижения и награды
   - Блоги и техническая документация
   - Отзывы клиентов и рейтинги

3. Если ссылок мало - ищи ГЛУБЖЕ:
   - Проверяй LinkedIn, Crunchbase, TechCrunch, Product Hunt
   - Ищи в отраслевых изданиях, блогах, форумах
   - Проверяй актуальность всех ссылок
   - Если не находишь ссылки - ищи альтернативные источники

ВАЖНО:
- НЕ генерируй изображения
- НЕ создавай скриншоты
- Фокусируйся на МАКСИМАЛЬНОМ количестве ссылок
- Используй только проверенные источники
- Группируй по странам/регионам
- Каждая компания должна быть в формате:
  Компания: [название]
  Сайт: [официальный сайт]
  Соцсети: [ссылки на соцсети]
  Продукты: [ссылки на продукты]
  Кейсы: [ссылки на кейсы]
  Новости: [ссылки на новости]
  Финансирование: [ссылки на финансирование]
  Партнерства: [ссылки на партнерства]
  Достижения: [ссылки на достижения]
  Блоги: [ссылки на блоги]
  Отзывы: [ссылки на отзывы]
  Страна: [страна]
  Описание: [краткое описание фичи]

ФОРМАТ ОТВЕТА:
Структурированный список компаний с МАКСИМАЛЬНЫМ количеством ссылок.
"""
        else:  # product research
            return f"""
Ты — эксперт по поиску и сбору данных о финтех-продуктах.

ЦЕЛЬ: Найти и собрать МАКСИМАЛЬНО ПОДРОБНУЮ информацию о продуктах с характеристиками "{research_data.get('product_characteristics', '')}".

ПАРАМЕТРЫ ИССЛЕДОВАНИЯ:
- Продукт: {research_data.get('product_description', '')}
- Сегмент: {research_data.get('segment', '')}
- Характеристики: {research_data.get('product_characteristics', '')}
- Обязательные игроки: {research_data.get('required_players', '')}
- Обязательные страны: {research_data.get('required_countries', '')}

КРИТИЧЕСКИ ВАЖНО - ПОИСК ССЫЛОК:
1. Найди МИНИМУМ 15-20 продуктов
2. Для КАЖДОГО продукта найди МИНИМУМ 8-10 ОФИЦИАЛЬНЫХ ССЫЛОК:
   - Официальный сайт продукта
   - Социальные сети компании (LinkedIn, Twitter, Facebook)
   - Продуктовые страницы и функции
   - Кейсы использования и отзывы
   - Пресс-релизы и новости
   - Информация о финансировании
   - Партнерства и интеграции
   - Достижения и награды
   - Блоги и техническая документация
   - Отзывы клиентов и рейтинги

3. Если ссылок мало - ищи ГЛУБЖЕ:
   - Проверяй LinkedIn, Crunchbase, TechCrunch, Product Hunt
   - Ищи в отраслевых изданиях, блогах, форумах
   - Проверяй актуальность всех ссылок
   - Если не находишь ссылки - ищи альтернативные источники

ВАЖНО:
- НЕ генерируй изображения
- НЕ создавай скриншоты
- Фокусируйся на МАКСИМАЛЬНОМ количестве ссылок
- Используй только проверенные источники
- Группируй по странам/регионам
- Каждый продукт должен быть в формате:
  Продукт: [название]
  Компания: [название компании]
  Сайт: [официальный сайт]
  Соцсети: [ссылки на соцсети]
  Продукты: [ссылки на продукты]
  Кейсы: [ссылки на кейсы]
  Новости: [ссылки на новости]
  Финансирование: [ссылки на финансирование]
  Партнерства: [ссылки на партнерства]
  Достижения: [ссылки на достижения]
  Блоги: [ссылки на блоги]
  Отзывы: [ссылки на отзывы]
  Страна: [страна]
  Характеристики: [ключевые характеристики]

ФОРМАТ ОТВЕТА:
Структурированный список продуктов с МАКСИМАЛЬНЫМ количеством ссылок.
"""
    
    def get_local_documents_prompt(self, files_payload: List[Dict[str, Any]], research_data: Dict[str, Any], research_type: str) -> str:
        """Prompt for summarizing local PDF documents into structured insights (JSON)."""
        context = {
            "research_type": research_type,
            "product_description": research_data.get('product_description', ''),
            "segment": research_data.get('segment', ''),
        }
        if research_type == "feature":
            context["focus"] = research_data.get('research_element', '')
        else:
            context["focus"] = research_data.get('product_characteristics', '')

        # Get list of actual PDF files that exist
        actual_files = []
        try:
            for name in os.listdir(self.config.DATA_DIR):
                if name.lower().endswith(".pdf"):
                    actual_files.append(name)
        except Exception:
            actual_files = []

        return (
            "Ты — аналитик. Проанализируй локальные PDF-документы и извлеки ТОЛЬКО релевантные факты по исследованию.\n"
            "Верни результат в строго валидном JSON-массиве объектов без пояснений. Схема объекта:\n"
            "{\"source_file\": str, \"section\": str, \"fact\": str, \"metrics\": str|null, \"date\": str|null, \"links\": [str]}\n"
            "Правила: коротко, по делу; добавляй ссылки если явно указаны в тексте; игнорируй нерелевантное.\n"
            f"ВАЖНО: Используй ТОЛЬКО эти существующие PDF файлы: {', '.join(actual_files)}\n"
            f"НЕ создавай ссылки на несуществующие файлы!\n\n"
            f"КОНТЕКСТ ИССЛЕДОВАНИЯ: {json.dumps(context, ensure_ascii=False)}\n\n"
            f"ИСТОЧНИКИ: {json.dumps(files_payload[:3], ensure_ascii=False) if len(files_payload)>3 else json.dumps(files_payload, ensure_ascii=False)}\n\n"
            "Верни только JSON без маркировок."
        )

    def get_case_analysis_prompt(self, market_data: Dict[str, Any], research_data: Dict[str, Any], research_type: str) -> str:
        """Get prompt for case analysis stage"""
        if research_type == "feature":
            return f"""
Ты — старший аналитик по финтеху. Проанализируй собранные данные и создай детальные кейсы.

ВХОДНЫЕ ДАННЫЕ:
{json.dumps(market_data, ensure_ascii=False, indent=2)}

ПАРАМЕТРЫ ИССЛЕДОВАНИЯ:
- Продукт: {research_data.get('product_description', '')}
- Сегмент: {research_data.get('segment', '')}
- Элемент: {research_data.get('research_element', '')}

ЛОКАЛЬНЫЕ ИНСАЙТЫ ИЗ PDF:
{json.dumps(market_data.get('local_insights', {}), ensure_ascii=False, indent=2)}

КРИТИЧЕСКИ ВАЖНО - МАКСИМАЛЬНОЕ КОЛИЧЕСТВО ССЫЛОК:
1. Для КАЖДОГО кейса найди МИНИМУМ 5-7 ПОДТВЕРЖДАЮЩИХ ССЫЛОК
2. Если ссылок мало - ищи ГЛУБЖЕ в исходных данных
3. Проверяй все найденные ссылки на актуальность
4. Добавляй ссылки на:
   - Официальные страницы продуктов
   - Техническую документацию
   - Кейсы использования
   - Отзывы клиентов
   - Пресс-релизы и новости
   - Партнерские интеграции
   - Достижения и награды

ЗАДАЧА:
Создай 10-12 детальных кейсов по шаблону:

**Кейс [номер]: [Название компании]**

**Краткое описание:** [1-2 предложения]

**Страна:** [страна регистрации]

**Подробное описание фичи:**
- Как работает фича
- Где в пользовательском пути
- Для кого предназначена
- Какие триггеры
- Метрики/результаты (если есть)

**Источники (МИНИМУМ 5-7 ссылок):**
- [официальная ссылка 1]
- [продуктовая ссылка 2]
- [кейс использования 3]
- [техническая документация 4]
- [отзыв клиента 5]
- [новость/пресс-релиз 6]
- [партнерство/интеграция 7]


ВАЖНО:
- НЕ генерируй изображения
- НЕ создавай скриншоты
- Каждый кейс должен быть уникальным
- Все ссылки должны быть рабочими
- Указывай конкретные даты
- Фокусируйся на применимости к нашему контексту
- Используй только текстовое описание
"""
        else:  # product research
            return f"""
Ты — старший аналитик по финтеху. Проанализируй собранные данные и создай детальные кейсы продуктов.

ВХОДНЫЕ ДАННЫЕ:
{json.dumps(market_data, ensure_ascii=False, indent=2)}

ПАРАМЕТРЫ ИССЛЕДОВАНИЯ:
- Продукт: {research_data.get('product_description', '')}
- Сегмент: {research_data.get('segment', '')}
- Характеристики: {research_data.get('product_characteristics', '')}

ЛОКАЛЬНЫЕ ИНСАЙТЫ ИЗ PDF:
{json.dumps(market_data.get('local_insights', {}), ensure_ascii=False, indent=2)}

КРИТИЧЕСКИ ВАЖНО - МАКСИМАЛЬНОЕ КОЛИЧЕСТВО ССЫЛОК:
1. Для КАЖДОГО кейса найди МИНИМУМ 5-7 ПОДТВЕРЖДАЮЩИХ ССЫЛОК
2. Если ссылок мало - ищи ГЛУБЖЕ в исходных данных
3. Проверяй все найденные ссылки на актуальность
4. Добавляй ссылки на:
   - Официальные страницы продуктов
   - Техническую документацию
   - Кейсы использования
   - Отзывы клиентов
   - Пресс-релизы и новости
   - Партнерские интеграции
   - Достижения и награды

ЗАДАЧА:
Создай 10-12 детальных кейсов продуктов по шаблону:

**Кейс [номер]: [Название продукта]**

**Компания:** [название компании]

**Краткое описание:** [1-2 предложения о продукте]

**Страна:** [страна регистрации]

**Ключевые характеристики:**
- [характеристика 1]
- [характеристика 2]
- [характеристика 3]

**Подробное описание продукта:**
- Как работает продукт
- Где в пользовательском пути
- Для кого предназначен
- Какие триггеры
- Метрики/результаты (если есть)

**Источники (МИНИМУМ 5-7 ссылок):**
- [официальная ссылка 1]
- [продуктовая ссылка 2]
- [кейс использования 3]
- [техническая документация 4]
- [отзыв клиента 5]
- [новость/пресс-релиз 6]
- [партнерство/интеграция 7]

ВАЖНО:
- НЕ генерируй изображения
- НЕ создавай скриншоты
- Каждый кейс должен быть уникальным
- Все ссылки должны быть рабочими
- Указывай конкретные даты
- Фокусируйся на применимости к нашему контексту
- Используй только текстовое описание
"""
    
    def get_report_generation_prompt(self, cases: List[Dict[str, Any]], research_data: Dict[str, Any], research_type: str) -> str:
        """Get prompt for final report generation"""
        # Get list of available PDF files
        available_files = self.get_available_pdf_files()
        files_list = ", ".join(available_files) if available_files else "нет доступных файлов"
        
        if research_type == "feature":
            return f"""
Ты — старший аналитик по финтеху. Создай финальный отчет на основе проанализированных кейсов.

ПРОАНАЛИЗИРОВАННЫЕ КЕЙСЫ:
{json.dumps(cases, ensure_ascii=False, indent=2)}

ПАРАМЕТРЫ ИССЛЕДОВАНИЯ:
- Продукт: {research_data.get('product_description', '')}
- Сегмент: {research_data.get('segment', '')}
- Элемент: {research_data.get('research_element', '')}

ВАЖНО: Используй также локальные инсайты из PDF-документов для обогащения отчета дополнительными фактами и трендами.

ДОСТУПНЫЕ PDF ФАЙЛЫ: {files_list}

КРИТИЧЕСКИ ВАЖНО - ССЫЛКИ НА ЛОКАЛЬНЫЕ ФАКТЫ:
1. Если упоминаются факты из локальных PDF - добавляй ссылки на них в формате:
   - [Название факта]({self.config.BASE_URL}/data/имя_файла.pdf)
2. Ссылки должны быть релевантными и вести на соответствующие PDF-документы
3. ВАЖНО: Используй ТОЛЬКО существующие PDF файлы из папки data/
4. НЕ создавай ссылки на несуществующие файлы!

СОЗДАЙ ОТЧЕТ В СЛЕДУЮЩЕМ ФОРМАТЕ:

# Отчет по исследованию фичи: {research_data.get('research_element', '')}

## Краткое резюме
[Краткое резюме на 5-7 пунктов]

## Анализ кейсов
[Детальное описание каждого кейса с таблицей]

### Таблица сравнения кейсов
| № | Компания | Страна | Описание фичи | Источники |
|---|----------|--------|---------------|-----------|-----------------|
| 1 | [название] | [страна] | [описание] | [ссылки] |
| 2 | [название] | [страна] | [описание] | [ссылки] |
| ... | ... | ... | ... | ... |

## Применимость к нашему продукту
[Анализ применимости с конкретными рекомендациями]

## План внедрения
[Пошаговый план внедрения с оценкой сложности]

## Риски и ограничения
[Потенциальные риски и способы их минимизации]

КРИТИЧЕСКИ ВАЖНО - МАКСИМАЛЬНОЕ КОЛИЧЕСТВО ССЫЛОК:
1. В КАЖДОЙ таблице должно быть МИНИМУМ 3-5 ссылок на компанию
2. Все ссылки должны быть ПРОВЕРЕННЫМИ и АКТУАЛЬНЫМИ
3. Если ссылок мало - ищи ГЛУБЖЕ в исходных данных
4. Добавляй ссылки на:
   - Официальные сайты компаний
   - Продуктовые страницы
   - Кейсы использования
   - Техническую документацию
   - Отзывы клиентов
   - Пресс-релизы и новости
   - Партнерские интеграции

ВАЖНО:
- НЕ генерируй изображения
- НЕ создавай скриншоты
- Используй только таблицы для структурирования данных
- Все ссылки должны быть проверенными и актуальными
- Фокусируйся на практической применимости
- Используй маркдаун форматирование
- Только текстовый контент
- МАКСИМАЛЬНОЕ количество ссылок в каждой таблице
"""
        else:  # product research
            return f"""
Ты — старший аналитик по финтеху. Создай финальный отчет на основе проанализированных продуктов.

ПРОАНАЛИЗИРОВАННЫЕ ПРОДУКТЫ:
{json.dumps(cases, ensure_ascii=False, indent=2)}

ПАРАМЕТРЫ ИССЛЕДОВАНИЯ:
- Продукт: {research_data.get('product_description', '')}
- Сегмент: {research_data.get('segment', '')}
- Характеристики: {research_data.get('product_characteristics', '')}

ВАЖНО: Используй также локальные инсайты из PDF-документов для обогащения отчета дополнительными фактами и трендами.

ДОСТУПНЫЕ PDF ФАЙЛЫ: {files_list}

КРИТИЧЕСКИ ВАЖНО - ССЫЛКИ НА ЛОКАЛЬНЫЕ ФАКТЫ:
1. Если упоминаются факты из локальных PDF - добавляй ссылки на них в формате:
   - [Название факта]({self.config.BASE_URL}/data/имя_файла.pdf)
2. Ссылки должны быть релевантными и вести на соответствующие PDF-документы
3. ВАЖНО: Используй ТОЛЬКО существующие PDF файлы из папки data/
4. НЕ создавай ссылки на несуществующие файлы!

СОЗДАЙ ОТЧЕТ В СЛЕДУЮЩЕМ ФОРМАТЕ:

# Отчет по исследованию продукта: {research_data.get('product_characteristics', '')}

## Краткое резюме
[Краткое резюме на 5-7 пунктов]

## Анализ продуктов
[Детальное описание каждого продукта с таблицей]

### Таблица сравнения продуктов
| № | Продукт | Компания | Страна | Характеристики | Источники |
|---|---------|----------|--------|----------------|-----------|-----------------|
| 1 | [название] | [компания] | [страна] | [характеристики] | [ссылки] |
| 2 | [название] | [компания] | [страна] | [характеристики] | [ссылки] |
| ... | ... | ... | ... | ... | ... |

## Применимость к нашему продукту
[Анализ применимости с конкретными рекомендациями]

## План внедрения
[Пошаговый план внедрения с оценкой сложности]

## Риски и ограничения
[Потенциальные риски и способы их минимизации]

КРИТИЧЕСКИ ВАЖНО - МАКСИМАЛЬНОЕ КОЛИЧЕСТВО ССЫЛОК:
1. В КАЖДОЙ таблице должно быть МИНИМУМ 3-5 ссылок на продукт
2. Все ссылки должны быть ПРОВЕРЕННЫМИ и АКТУАЛЬНЫМИ
3. Если ссылок мало - ищи ГЛУБЖЕ в исходных данных
4. Добавляй ссылки на:
   - Официальные сайты продуктов
   - Продуктовые страницы
   - Кейсы использования
   - Техническую документацию
   - Отзывы клиентов
   - Пресс-релизы и новости
   - Партнерские интеграции

ВАЖНО:
- НЕ генерируй изображения
- НЕ создавай скриншоты
- Используй только таблицы для структурирования данных
- Все ссылки должны быть проверенными и актуальными
- Фокусируйся на практической применимости
- Используй маркдаун форматирование
- Только текстовый контент
- МАКСИМАЛЬНОЕ количество ссылок в каждой таблице
"""

    def parse_local_insights(self, content: str) -> List[Dict[str, Any]]:
        """Parse JSON array of insights from model response; fallback to simple parsing"""
        content_str = content.strip()
        # Attempt to locate JSON array in the text
        match = re.search(r"\[.*\]", content_str, re.DOTALL)
        json_str = match.group(0) if match else content_str
        try:
            data = json.loads(json_str)
            if isinstance(data, list):
                # Normalize objects
                norm = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    source_file = item.get("source_file") or item.get("source") or "unknown.pdf"
                    
                    # Check if file actually exists before creating link
                    file_path = os.path.join(self.config.DATA_DIR, source_file)
                    if os.path.exists(file_path):
                        download_link = f"{self.config.BASE_URL}/data/{source_file}"
                    else:
                        # Don't create link for non-existent files
                        download_link = None
                        print(f"⚠️ PDF файл не найден: {source_file}")
                    
                    norm.append({
                        "source_file": source_file,
                        "download_link": download_link,
                        "section": item.get("section") or "",
                        "fact": item.get("fact") or "",
                        "metrics": item.get("metrics") or None,
                        "date": item.get("date") or None,
                        "links": item.get("links") or []
                    })
                return norm
        except Exception:
            pass
        # Fallback: extract lines starting with '-' or '*'
        insights: List[Dict[str, Any]] = []
        for line in content_str.split('\n'):
            line = line.strip(" -•*")
            if not line:
                continue
            insights.append({
                "source_file": "unknown.pdf",
                "download_link": None,  # Don't create link for unknown files
                "section": "",
                "fact": line,
                "metrics": None,
                "date": None,
                "links": []
            })
        return insights
    
    def parse_market_data(self, api_response: Dict[str, Any], research_type: str) -> Dict[str, Any]:
        """Parse market data from API response"""
        try:
            if "candidates" in api_response and len(api_response["candidates"]) > 0:
                content = api_response["candidates"][0]["content"]["parts"][0]["text"]
                
                # Parse the content to extract structured data
                companies = self.extract_companies_from_text(content)
                
                return {
                    "raw_content": content,
                    "companies": companies,
                    "research_type": research_type,
                    "timestamp": datetime.now().isoformat(),
                    "total_found": len(companies)
                }
            else:
                return {
                    "raw_content": "No data found",
                    "companies": [],
                    "research_type": research_type,
                    "timestamp": datetime.now().isoformat(),
                    "total_found": 0
                }
        except Exception as e:
            return {
                "raw_content": f"Error parsing data: {str(e)}",
                "companies": [],
                "research_type": research_type,
                "timestamp": datetime.now().isoformat(),
                "total_found": 0
            }
    
    def extract_companies_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract company/product information from text"""
        companies = []
        lines = text.split('\n')
        
        current_company = {}
        for line in lines:
            line = line.strip()
            if not line:
                if current_company:
                    companies.append(current_company)
                    current_company = {}
                continue
                
            # Look for company/product patterns - support both
            if any(keyword in line.lower() for keyword in ['компания:', 'company:', 'название:', 'name:', 'продукт:', 'product:']):
                if current_company:
                    companies.append(current_company)
                current_company = {"name": line.split(':', 1)[1].strip() if ':' in line else line}
            elif any(keyword in line.lower() for keyword in ['сайт:', 'website:', 'url:']):
                if current_company:
                    current_company["website"] = line.split(':', 1)[1].strip() if ':' in line else line
            elif any(keyword in line.lower() for keyword in ['страна:', 'country:']):
                if current_company:
                    current_company["country"] = line.split(':', 1)[1].strip() if ':' in line else line
            elif any(keyword in line.lower() for keyword in ['характеристики:', 'characteristics:']):
                if current_company:
                    current_company["characteristics"] = line.split(':', 1)[1].strip() if ':' in line else line
            elif line.startswith('http'):
                if current_company:
                    if "links" not in current_company:
                        current_company["links"] = []
                    current_company["links"].append(line)
        
        if current_company:
            companies.append(current_company)
            
        return companies
    
    def parse_cases(self, api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse cases from API response"""
        try:
            if "candidates" in api_response and len(api_response["candidates"]) > 0:
                content = api_response["candidates"][0]["content"]["parts"][0]["text"]
                
                # Parse the content to extract case information
                cases = self.extract_cases_from_text(content)
                
                return cases
            else:
                return []
        except Exception as e:
            return []
    
    def extract_cases_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract case information from text"""
        cases = []
        lines = text.split('\n')
        
        current_case = {}
        case_number = 1
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for case patterns - support both feature and product cases
            if (line.startswith(f'**Кейс {case_number}') or 
                line.startswith(f'Кейс {case_number}') or
                line.startswith(f'**Продукт {case_number}') or
                line.startswith(f'Продукт {case_number}')):
                if current_case:
                    cases.append(current_case)
                current_case = {
                    "number": case_number,
                    "title": line.replace('**', '').replace('*', '').strip()
                }
                case_number += 1
            elif (line.startswith('**Компания:') or line.startswith('Компания:') or
                  line.startswith('**Продукт:') or line.startswith('Продукт:')):
                if current_case:
                    current_case["company"] = line.split(':', 1)[1].strip() if ':' in line else line
            elif line.startswith('**Страна:') or line.startswith('Страна:'):
                if current_case:
                    current_case["country"] = line.split(':', 1)[1].strip() if ':' in line else line
            elif (line.startswith('**Источники:') or line.startswith('Источники:') or
                  line.startswith('**Ссылки:') or line.startswith('Ссылки:')):
                if current_case:
                    current_case["sources"] = []
            elif line.startswith('http'):
                if current_case:
                    if "sources" not in current_case:
                        current_case["sources"] = []
                    current_case["sources"].append(line)
            elif current_case and line and not line.startswith('**'):
                # This is likely description content
                if "description" not in current_case:
                    current_case["description"] = line
                else:
                    current_case["description"] += " " + line
        
        if current_case:
            cases.append(current_case)
            
        return cases
    
    def add_verification_summary(self, report_content: str, cases: List[Dict[str, Any]]) -> str:
        """Add verification summary to the report"""
        total_links = 0
        working_links = 0
        broken_links = 0
        
        for case in cases:
            if "verified_links" in case:
                total_links += len(case["verified_links"])
                working_links += len([link for link in case["verified_links"] if link.get("status") == "working"])
            if "broken_links" in case:
                broken_links += len(case["broken_links"])
        
        percentage = (working_links/total_links*100) if total_links > 0 else 0
        
        verification_summary = f"""

## Сводка проверки ссылок

- **Всего ссылок проверено:** {total_links}
- **Рабочих ссылок:** {working_links}
- **Нерабочих ссылок:** {broken_links}
- **Процент рабочих ссылок:** {percentage:.1f}%

*Все ссылки были проверены на доступность и актуальность.*
"""
        
        return report_content + verification_summary
    
    def extract_report_content(self, api_response: Dict[str, Any]) -> str:
        """Extract report content from API response"""
        try:
            if "candidates" in api_response and len(api_response["candidates"]) > 0:
                content = api_response["candidates"][0]["content"]["parts"][0]["text"]
                return content
            else:
                return "Ошибка при генерации отчета"
        except Exception as e:
            return f"Ошибка при обработке ответа: {str(e)}"
    
    async def enhance_report_with_links(self, report_content: str, cases: List[Dict[str, Any]], research_data: Dict[str, Any], research_type: str) -> str:
        """Enhance report with additional links from verified sources"""
        try:
            # Extract all verified links from cases
            all_verified_links = []
            for case in cases:
                if "verified_links" in case:
                    for link in case["verified_links"]:
                        if link.get("status") == "working":
                            all_verified_links.append({
                                "url": link.get("url"),
                                "company": case.get("title", case.get("company", "Unknown")),
                                "context": case.get("description", "")
                            })
            
            if not all_verified_links:
                return report_content
            
            # Create prompt for link enhancement
            # Use full report content, but limit to reasonable size for API
            max_content_length = 15000  # Increased from 3000
            report_preview = report_content[:max_content_length]
            if len(report_content) > max_content_length:
                report_preview += "\n\n[... остальная часть отчета ...]"
            
            prompt = f"""
Ты — эксперт по добавлению ссылок в отчеты. Улучши отчет, добавив релевантные ссылки из проверенных источников.

ОТЧЕТ ДЛЯ УЛУЧШЕНИЯ:
{report_preview}

ПРОВЕРЕННЫЕ ССЫЛКИ:
{json.dumps(all_verified_links[:20], ensure_ascii=False, indent=2)}

ЗАДАЧА:
1. Найди в отчете упоминания компаний, продуктов или фактов
2. Добавь к ним релевантные ссылки из списка проверенных источников
3. Используй формат: [текст](ссылка)
4. НЕ изменяй структуру отчета, только добавляй ссылки
5. Максимум 3-5 ссылок на абзац
6. Приоритет: официальные сайты > кейсы > новости
7. ВАЖНО: Верни ПОЛНЫЙ отчет с добавленными ссылками, не обрезай его

ВЕРНИ ПОЛНЫЙ УЛУЧШЕННЫЙ ОТЧЕТ С ДОБАВЛЕННЫМИ ССЫЛКАМИ.
"""
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Retry logic for 503 errors (model overloaded)
                max_retries = 5
                attempt = 0
                
                while attempt < max_retries:
                    try:
                        response = await client.post(
                            f"{self.config.GEMINI_API_URL}/v1beta/models/{self.config.GEMINI_MODEL}:generateContent",
                            headers={
                                "Content-Type": "application/json",
                                "x-goog-api-key": self.config.GEMINI_API_KEY
                            },
                            json={
                                "contents": [{
                                    "parts": [{"text": prompt}]
                                }],
                                "generationConfig": {
                                    "temperature": 0.3
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
                    enhanced_content = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    
                    if enhanced_content:
                        print(f"📊 УЛУЧШЕНИЕ ОТЧЕТА:")
                        print(f"   Исходная длина: {len(report_content)} символов")
                        print(f"   Улучшенная длина: {len(enhanced_content)} символов")
                        return enhanced_content
                    else:
                        print(f"⚠️ ИИ не вернул улучшенный отчет, используем исходный")
                        return report_content
                else:
                    print(f"⚠️ Ошибка улучшения отчета: {response.status_code}")
                    return report_content
                    
        except Exception as e:
            print(f"⚠️ Ошибка при улучшении отчета: {str(e)}")
            return report_content
    
    async def verify_report_links(self, report_content: str) -> str:
        """Verify all links in the report and remove broken ones"""
        try:
            import re
            
            # Find all markdown links in the report
            link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
            links = re.findall(link_pattern, report_content)
            
            if not links:
                print("📋 Ссылки в отчете не найдены")
                return report_content
            
            print(f"🔍 Найдено {len(links)} ссылок в отчете для проверки")
            
            verified_links = []
            broken_links = []
            
            # Check each link
            for i, (text, url) in enumerate(links):
                print(f"🔗 Проверяем ссылку {i+1}/{len(links)}: {url}")
                
                try:
                    # Skip PDF links to our domain - they should work
                    if url.startswith(f'{self.config.BASE_URL}/data/'):
                        verified_links.append((text, url))
                        print(f"✅ PDF ссылка пропущена: {url}")
                        continue
                    
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.head(url, follow_redirects=True)
                        if response.status_code < 400:
                            verified_links.append((text, url))
                            print(f"✅ Ссылка работает: {response.status_code}")
                        else:
                            broken_links.append((text, url))
                            print(f"❌ Ссылка не работает: {response.status_code}, удаляем")
                            
                except Exception as e:
                    broken_links.append((text, url))
                    print(f"⚠️ Ошибка проверки ссылки: {str(e)}, удаляем")
            
            # Remove broken links and their text from report
            if broken_links:
                print(f"🗑️ Удаляем {len(broken_links)} нерабочих ссылок с текстом")
                for text, url in broken_links:
                    # Remove the entire link with text completely
                    report_content = report_content.replace(f"[{text}]({url})", "")
                
                # Clean up extra whitespace and empty lines
                import re
                report_content = re.sub(r'\n\s*\n\s*\n', '\n\n', report_content)  # Remove multiple empty lines
                report_content = re.sub(r'^\s*\n', '', report_content, flags=re.MULTILINE)  # Remove empty lines at start
                report_content = report_content.strip()
            
            # Replace original links with verified alternatives
            for text, url in verified_links:
                # Find and replace the original link with the verified one
                original_pattern = f"[{text}]("
                if original_pattern in report_content:
                    # Find the original link and replace it
                    import re
                    pattern = f"\\[{re.escape(text)}\\]\\([^)]+\\)"
                    replacement = f"[{text}]({url})"
                    report_content = re.sub(pattern, replacement, report_content)
            
            print(f"📊 ИТОГИ ПРОВЕРКИ ССЫЛОК В ОТЧЕТЕ:")
            print(f"   Всего ссылок: {len(links)}")
            print(f"   Рабочих ссылок: {len(verified_links)}")
            print(f"   Нерабочих ссылок: {len(broken_links)}")
            if len(links) > 0:
                percentage = (len(verified_links) / len(links)) * 100
                print(f"   Процент рабочих: {percentage:.1f}%")
            
            return report_content
            
        except Exception as e:
            print(f"⚠️ Ошибка при проверке ссылок в отчете: {str(e)}")
            return report_content
    
