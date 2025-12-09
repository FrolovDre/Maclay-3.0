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

    async def _call_deepseek(self, prompt: str, temperature: float = 0.7, max_new_tokens: int = 4096) -> str:
        """Call DeepSeek model via Hugging Face Inference API"""
        api_url = f"{self.config.HF_API_URL}/models/{self.config.HF_MODEL}"
        headers = {
            "Authorization": f"Bearer {self.config.HF_API_TOKEN}",
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

        async with httpx.AsyncClient(timeout=270.0) as client:
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
                    return self._extract_generated_text(result)
                except Exception as e:
                    attempt += 1
                    if attempt >= max_retries:
                        raise e
                    await asyncio.sleep(2 ** attempt)

    def _extract_generated_text(self, result: Any) -> str:
        """Extract generated text from Hugging Face Inference response"""
        if isinstance(result, list) and result:
            item = result[0]
            if isinstance(item, dict):
                return item.get("generated_text") or item.get("text") or ""
            if isinstance(item, str):
                return item
        if isinstance(result, dict):
            return result.get("generated_text") or result.get("text") or ""
        return ""
        
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
@@ -188,117 +236,68 @@ class ResearchProcessor:
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
        
        try:
            await self.send_update("data_collection", "active", 40, "Выполняем HTTP запрос...")
            content = await self._call_deepseek(prompt, temperature=0.7, max_new_tokens=2048)
            await self.send_update("data_collection", "active", 70, "Обрабатываем ответ...")

            print(f"✅ Ответ успешно получен: {len(content)} символов")
            await self.send_update("data_collection", "active", 90, "Структурируем данные...")

            market_data = self.parse_market_data(content, research_type)

            await self.send_update("data_collection", "completed", 100, f"Найдено {len(market_data.get('companies', []))} компаний")

            return market_data
        except Exception as e:
            error_msg = f"API Error: {str(e)}"
            print(f"❌ {error_msg}")
            await self.send_update("data_collection", "error", 0, error_msg)
            raise

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
@@ -331,297 +330,163 @@ class ResearchProcessor:
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

        try:
            await self.send_update("local_documents", "active", 70, "Отправляем запрос к ИИ...")
            content = await self._call_deepseek(prompt, temperature=0.2, max_new_tokens=1024)
            await self.send_update("local_documents", "active", 85, "Обрабатываем ответ ИИ...")
        except Exception as e:
            await self.send_update("local_documents", "error", 0, f"API Error: {e}")
            return {"insights": [], "files": [f["file"] for f in files_payload]}
        
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
        
        try:
            content = await self._call_deepseek(prompt, temperature=0.5, max_new_tokens=2048)
            await self.send_update("case_analysis", "active", 70, "Обрабатываем результаты анализа...")

            await self.send_update("case_analysis", "active", 90, "Структурируем кейсы...")

            cases = self.parse_cases(content)
            await self.send_update("case_analysis", "completed", 100, f"Проанализировано {len(cases)} кейсов")

            return cases
        except Exception as e:
            raise Exception(f"API Error: {e}")
    
    
    
    
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
        
        try:
            response_text = await self._call_deepseek(prompt, temperature=0.3, max_new_tokens=4096)

            await self.send_update("report_generation", "active", 70, "Обрабатываем ответ...")
            await self.send_update("report_generation", "active", 90, "Форматируем отчет...")

            report_content = self.extract_report_content(response_text)

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
        except Exception as e:
            raise Exception(f"API Error: {e}")
    
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
@@ -1071,135 +936,115 @@ class ResearchProcessor:
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
    
    def parse_market_data(self, content: str, research_type: str) -> Dict[str, Any]:
        """Parse market data from generated text"""
        try:
            companies = self.extract_companies_from_text(content)

            return {
                "raw_content": content,
                "companies": companies,
                "research_type": research_type,
                "timestamp": datetime.now().isoformat(),
                "total_found": len(companies)
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
    
    def parse_cases(self, content: str) -> List[Dict[str, Any]]:
        """Parse cases from generated text"""
        try:
            return self.extract_cases_from_text(content)
        except Exception:
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
@@ -1240,167 +1085,115 @@ class ResearchProcessor:
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
    
    def extract_report_content(self, response_text: str) -> str:
        """Extract report content from generated text"""
        return response_text or "Ошибка при генерации отчета"
    
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
            
            try:
                enhanced_content = await self._call_deepseek(prompt, temperature=0.3, max_new_tokens=4096)

                if enhanced_content:
                    print(f"📊 УЛУЧШЕНИЕ ОТЧЕТА:")
                    print(f"   Исходная длина: {len(report_content)} символов")
                    print(f"   Улучшенная длина: {len(enhanced_content)} символов")
                    return enhanced_content
                else:
                    print(f"⚠️ ИИ не вернул улучшенный отчет, используем исходный")
                    return report_content
            except Exception as e:
                print(f"⚠️ Ошибка улучшения отчета: {e}")
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
            
            return report_contenimport pdfplumber
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

    async def _call_deepseek(self, prompt: str, temperature: float = 0.7, max_new_tokens: int = 4096) -> str:
        """Call DeepSeek model via Hugging Face Inference API"""
        api_url = f"{self.config.HF_API_URL}/models/{self.config.HF_MODEL}"
        headers = {
            "Authorization": f"Bearer {self.config.HF_API_TOKEN}",
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

        async with httpx.AsyncClient(timeout=270.0) as client:
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
                    return self._extract_generated_text(result)
                except Exception as e:
                    attempt += 1
                    if attempt >= max_retries:
                        raise e
                    await asyncio.sleep(2 ** attempt)

    def _extract_generated_text(self, result: Any) -> str:
        """Extract generated text from Hugging Face Inference response"""
        if isinstance(result, list) and result:
            item = result[0]
            if isinstance(item, dict):
                return item.get("generated_text") or item.get("text") or ""
            if isinstance(item, str):
                return item
        if isinstance(result, dict):
            return result.get("generated_text") or result.get("text") or ""
        return ""
        
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
@@ -188,117 +236,68 @@ class ResearchProcessor:
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
        
        try:
            await self.send_update("data_collection", "active", 40, "Выполняем HTTP запрос...")
            content = await self._call_deepseek(prompt, temperature=0.7, max_new_tokens=2048)
            await self.send_update("data_collection", "active", 70, "Обрабатываем ответ...")

            print(f"✅ Ответ успешно получен: {len(content)} символов")
            await self.send_update("data_collection", "active", 90, "Структурируем данные...")

            market_data = self.parse_market_data(content, research_type)

            await self.send_update("data_collection", "completed", 100, f"Найдено {len(market_data.get('companies', []))} компаний")

            return market_data
        except Exception as e:
            error_msg = f"API Error: {str(e)}"
            print(f"❌ {error_msg}")
            await self.send_update("data_collection", "error", 0, error_msg)
            raise

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
@@ -331,297 +330,163 @@ class ResearchProcessor:
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

        try:
            await self.send_update("local_documents", "active", 70, "Отправляем запрос к ИИ...")
            content = await self._call_deepseek(prompt, temperature=0.2, max_new_tokens=1024)
            await self.send_update("local_documents", "active", 85, "Обрабатываем ответ ИИ...")
        except Exception as e:
            await self.send_update("local_documents", "error", 0, f"API Error: {e}")
            return {"insights": [], "files": [f["file"] for f in files_payload]}
        
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
        
        try:
            content = await self._call_deepseek(prompt, temperature=0.5, max_new_tokens=2048)
            await self.send_update("case_analysis", "active", 70, "Обрабатываем результаты анализа...")

            await self.send_update("case_analysis", "active", 90, "Структурируем кейсы...")

            cases = self.parse_cases(content)
            await self.send_update("case_analysis", "completed", 100, f"Проанализировано {len(cases)} кейсов")

            return cases
        except Exception as e:
            raise Exception(f"API Error: {e}")
    
    
    
    
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
        
        try:
            response_text = await self._call_deepseek(prompt, temperature=0.3, max_new_tokens=4096)

            await self.send_update("report_generation", "active", 70, "Обрабатываем ответ...")
            await self.send_update("report_generation", "active", 90, "Форматируем отчет...")

            report_content = self.extract_report_content(response_text)

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
        except Exception as e:
            raise Exception(f"API Error: {e}")
    
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
@@ -1071,135 +936,115 @@ class ResearchProcessor:
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
    
    def parse_market_data(self, content: str, research_type: str) -> Dict[str, Any]:
        """Parse market data from generated text"""
        try:
            companies = self.extract_companies_from_text(content)

            return {
                "raw_content": content,
                "companies": companies,
                "research_type": research_type,
                "timestamp": datetime.now().isoformat(),
                "total_found": len(companies)
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
    
    def parse_cases(self, content: str) -> List[Dict[str, Any]]:
        """Parse cases from generated text"""
        try:
            return self.extract_cases_from_text(content)
        except Exception:
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
@@ -1240,167 +1085,115 @@ class ResearchProcessor:
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
    
    def extract_report_content(self, response_text: str) -> str:
        """Extract report content from generated text"""
        return response_text or "Ошибка при генерации отчета"
    
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
            
            try:
                enhanced_content = await self._call_deepseek(prompt, temperature=0.3, max_new_tokens=4096)

                if enhanced_content:
                    print(f"📊 УЛУЧШЕНИЕ ОТЧЕТА:")
                    print(f"   Исходная длина: {len(report_content)} символов")
                    print(f"   Улучшенная длина: {len(enhanced_content)} символов")
                    return enhanced_content
                else:
                    print(f"⚠️ ИИ не вернул улучшенный отчет, используем исходный")
                    return report_content
            except Exception as e:
                print(f"⚠️ Ошибка улучшения отчета: {e}")
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
                print(f"🔗 Проверяем ссылку {i+1}/{len(links)}: {url}")t
            
        except Exception as e:
            print(f"⚠️ Ошибка при проверке ссылок в отчете: {str(e)}")
            return report_content
    
