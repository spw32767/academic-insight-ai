# ติดตั้ง Paper AI บน Windows VM

คู่มือนี้สมมติว่า VM ใช้ Windows Server 2025 และมี `fund-management` frontend/backend รันอยู่แล้ว โดยติดตั้ง `academic-insight-ai` บน **VM เดียวกับ backend** หากอยู่คนละ VM ให้เปลี่ยน URL ของ AI API ใน backend เป็น IP ภายในเครือข่าย และอนุญาตเฉพาะ backend ให้เข้าถึงพอร์ต 8101/8102

ปัจจุบันโค้ด Paper AI ทั้งสาม repo (`academic-insight-ai`, `fund-management-api`, `frontend_project_fund`) อยู่บน branch `codex/paper-ai-system` การทดสอบบนเครื่อง/เซิร์ฟเวอร์ทดสอบให้ใช้ branch นี้ทั้งสาม repo ส่วนเซิร์ฟเวอร์จริงที่ deploy จาก `main` เท่านั้น ต้องรวมและทดสอบโค้ดใน `main` ของแต่ละ repo ก่อนดึงขึ้น VM อย่าดึงเฉพาะ AI repo โดยที่ backend/frontend ยังเป็นรุ่นเดิม

สเปกที่ตรวจไว้ก่อนหน้า (4 vCPU, RAM ประมาณ 32 GB, ไม่ทราบว่ามี GPU หรือไม่) ใช้ทดลอง `qwen3:4b` ได้ แต่ความเร็วจริงต้องวัดบน VM และควรเริ่มจากคำขอทีละรายการ ระหว่าง OCR และการสรุปข้อความอาจใช้เวลานานกว่าเครื่องพัฒนา

## 1. เตรียมโปรแกรมบน VM

ติดตั้ง Git, Python 3.12 แบบ 64-bit และ Ollama สำหรับ Windows ให้คำสั่ง `git`, `py -3.12` และ `ollama` ใช้งานได้ใน PowerShell ที่เปิดใหม่ การใช้ Ollama แบบ standalone service เหมาะกับ VM ที่ต้องทำงานหลังไม่มีผู้ใช้ login; ดู [คู่มือ Ollama บน Windows](https://github.com/ollama/ollama/blob/main/docs/windows.mdx) หากใช้แอป Ollama แบบปกติ ให้ตรวจว่ามันรันอยู่ก่อนสั่ง `ollama serve` เพราะพอร์ต 11434 ใช้ซ้ำไม่ได้

สำหรับ PDF สแกน ให้ติดตั้ง Tesseract 64-bit พร้อมภาษา `eng`, `tha` และ `osd`; ติดตั้ง Ghostscript 64-bit และ `uv` แล้วเปิด PowerShell ใหม่เพื่อติดตั้ง OCRmyPDF:

```powershell
uv tool install ocrmypdf
tesseract --list-langs
ocrmypdf --version
```

ตรวจว่าผล `tesseract --list-langs` มี `tha`, `eng` และ `osd` ครบ เพราะ Reader เรียก OCRmyPDF ด้วย `-l tha+eng` และเปิดการหมุนหน้าอัตโนมัติ หาก `tha` ไม่มี ให้เพิ่ม `tha.traineddata` ในโฟลเดอร์ `tessdata` ของ Tesseract ดู [คู่มือติดตั้ง OCRmyPDF บน Windows](https://ocrmypdf.readthedocs.io/en/stable/installation.html) และ [คู่มือติดตั้ง Tesseract](https://github.com/tesseract-ocr/tessdoc/blob/main/Installation.md) ระบบ Reader นี้เรียก `ocrmypdf` เป็นไฟล์ executable โดยตรง จึงควรใช้การติดตั้งแบบ native Windows

## 2. ดึง repo และติดตั้ง Python package

ตัวอย่างใช้ `C:\services` เปลี่ยนตำแหน่งได้ตาม VM:

```powershell
New-Item -ItemType Directory -Force C:\services | Out-Null
Set-Location C:\services
git clone https://github.com/spw32767/academic-insight-ai.git
Set-Location C:\services\academic-insight-ai
```

เฉพาะเซิร์ฟเวอร์ทดสอบที่ใช้โค้ด Paper AI ก่อนรวมเข้า `main` ให้สลับ branch ก่อนติดตั้ง package:

```powershell
git switch codex/paper-ai-system
```

จากนั้นติดตั้งด้วย Python ใน virtual environment:

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .
& .\.venv\Scripts\python.exe -m uvicorn --version
Copy-Item .env.example .env
```

ถ้าคำสั่งตรวจ `uvicorn` แจ้งว่า `No module named uvicorn` แสดงว่า package ยังไม่ได้ติดตั้งลง `.venv` ตัวนี้ ให้รัน `& .\.venv\Scripts\python.exe -m pip install -e .` ซ้ำ แล้วตรวจอีกครั้ง อย่าใช้ Python คนละตัวกับที่ใช้เปิดบริการ

ไฟล์ `.env` อยู่เฉพาะบน VM และ **ไม่ต้อง commit** ตั้งค่าอย่างน้อย:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
DEFAULT_MODEL=qwen3-4b
CLASSIFICATION_MODEL=qwen3-4b
READER_MODEL=qwen3-4b
AI_API_KEY=<สร้างคีย์สุ่มที่ยาวและไม่ซ้ำ>
CLASSIFICATION_API_HOST=127.0.0.1
CLASSIFICATION_API_PORT=8101
READER_API_HOST=127.0.0.1
READER_API_PORT=8102
OCRMY_PDF_COMMAND=ocrmypdf
```

สร้างคีย์ด้วย `& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"` แล้วใส่ค่าเดียวกันใน `PAPER_AI_API_KEY` ของ backend. `DATABASE_URL` ไม่จำเป็นสำหรับ AI API ทั้งสอง; ใช้เฉพาะงาน batch ที่อ่านฐานข้อมูลโดยตรง

## 3. เตรียม Ollama และโมเดล

ตรวจว่า Ollama ตอบสนองแล้วค่อยดึงโมเดล:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags
ollama pull qwen3:4b
ollama list
```

ถ้า `/api/tags` ไม่ตอบสนอง ให้เริ่ม Ollama ก่อน; ใช้ `ollama serve` เฉพาะเมื่อยังไม่มี instance รันอยู่ ตั้ง Ollama ให้เริ่มอัตโนมัติภายใต้บัญชีบริการเมื่อทดสอบผ่านแล้ว และให้ AI APIs เข้าถึง `127.0.0.1:11434` ได้

## 4. เริ่ม AI API แยกกัน

เปิด PowerShell สองหน้าต่าง โดยสั่ง `Set-Location C:\services\academic-insight-ai` ในแต่ละหน้าต่าง:

```powershell
& .\.venv\Scripts\python.exe -m uvicorn academic_insight_ai.apis.reader:app --host 127.0.0.1 --port 8102
```

```powershell
& .\.venv\Scripts\python.exe -m uvicorn academic_insight_ai.apis.classification:app --host 127.0.0.1 --port 8101
```

การเช็กสถานะจากอีกหน้าต่าง:

```powershell
Invoke-RestMethod http://127.0.0.1:8102/health
Invoke-RestMethod http://127.0.0.1:8101/health
```

ทั้งสองควรคืน `status: ok`. พอร์ตเหล่านี้ไม่ควรเปิดออกอินเทอร์เน็ต หากต้องให้ backend อีกเครื่องเรียก ให้ bind กับ IP ภายในและกำหนด firewall ให้เฉพาะเครื่อง backend

## 5. เตรียมฐานข้อมูลและเชื่อม fund-management

ดึงโค้ด backend และ frontend รุ่นที่มี Paper AI ทั้งคู่ ถ้าเป็นเซิร์ฟเวอร์ทดสอบให้ checkout `codex/paper-ai-system` ทั้งสอง repo; หากเป็นเซิร์ฟเวอร์จริงให้ดึง `main` หลังรวมโค้ดแล้ว

ก่อนรัน SQL ใน phpMyAdmin ให้สำรองฐานข้อมูล เลือกฐานข้อมูล fund-management ที่ถูกต้อง แล้วตรวจ:

```sql
SELECT DATABASE();
SHOW TABLES LIKE 'scopus_benchmark_documents';
SHOW TABLES LIKE 'scopus_documents';
SHOW TABLES LIKE 'publication_reward_details';
SHOW TABLES LIKE 'sdgs';
SHOW TABLES LIKE 'submission_sdgs';
```

ตาราง SDG เป็นส่วนของระบบ fund-management เดิม (migration 031/032) ไม่ต้องสร้างใหม่สำหรับฟีเจอร์แนะนำ SDG นี้

สำหรับฐานข้อมูลที่ยังไม่ได้เพิ่ม Paper AI ให้รัน migration ตามลำดับ **045 → 046 → 047** ทีละไฟล์ และตรวจผลก่อนรันไฟล์ถัดไป:

- 045 เพิ่ม `paper_categories` 7 หมวด, `paper_ai_jobs` และช่อง AI ใน benchmark/คำร้อง
- 046 เพิ่มค่า `Preface` สำหรับบทความที่ยังจัดหมวดไม่ได้
- 047 เพิ่มช่องจัดหมวดใน `scopus_documents` และตารางติดตามการจัดหมวดแบบชุดใหญ่

ถ้าเคยรันไฟล์ใดแล้ว ให้ข้ามไฟล์นั้น ห้ามรัน `ALTER TABLE` ซ้ำ Migration 047 ใช้ `ALTER TABLE scopus_documents` จึงต้องมีตารางนี้จาก schema เดิมก่อน หากไม่มี ให้ตรวจ schema/ฐานข้อมูลที่เลือกก่อน อย่ารัน 047 ต่อจนกว่าจะแก้สาเหตุ

ใน `.env` ของ `fund-management-api` บน VM ให้ตั้งค่า:

```dotenv
PAPER_READER_API_URL=http://127.0.0.1:8102
PAPER_CLASSIFICATION_API_URL=http://127.0.0.1:8101
PAPER_AI_API_KEY=<ค่าเดียวกับ AI_API_KEY>
PAPER_AI_TIMEOUT_SECONDS=600
```

build และรีสตาร์ต backend ให้โหลดค่าใหม่ จากนั้น build และรีสตาร์ต frontend รุ่นเดียวกัน Frontend เรียก backend เดิมและไม่ต้องรู้ `AI_API_KEY` โดยตรง หน้าขอทุนใช้ Reader เพื่อเติมข้อมูล สรุป PDF และเสนอ SDG หลักหนึ่งเป้าหมายจากรายการ `sdgs` ที่ใช้งานอยู่ ผู้ยื่นคำร้องตรวจและเปลี่ยน SDG ได้ก่อนบันทึก หาก AI วิเคราะห์ SDG ไม่สำเร็จ การนำเข้าข้อมูลบทความยังดำเนินต่อได้ ส่วนการจัดหมวดบทความ Scopus ใช้ Classification API แยกต่างหาก

## 6. ทดสอบก่อนเปิดใช้งานจริง

1. ตรวจ `/health` ทั้งสอง API และ `ollama list` ให้ผ่าน
2. เข้าแบบฟอร์มขอทุนด้วยบัญชีทดสอบ แนบ PDF บทความจริง ตรวจชื่อเรื่อง DOI, Abstract ต้นฉบับ สรุปภาษาไทย และ SDG ที่เลือกอัตโนมัติ หมายเหตุใต้ช่องต้องบอกว่าเป็นข้อเสนอจาก AI และผู้ใช้ต้องเปลี่ยน SDG เองได้ โดยยังไม่ส่งคำร้อง
3. แนบ PDF ที่ไม่ใช่บทความวิจัย ต้องเห็นข้อความว่า `ไฟล์ที่แนบไม่พบลักษณะของบทความวิจัย กรุณาแนบไฟล์ PDF ที่มีข้อมูลบทความ`
4. ทดลอง PDF สแกนอย่างน้อยหนึ่งไฟล์เพื่อยืนยันเส้นทาง OCR จริง (`ocrmypdf`, Tesseract ภาษาไทย/อังกฤษ และ Ghostscript)
5. บนเซิร์ฟเวอร์ทดสอบ หยุด Reader ชั่วคราวแล้วแนบ PDF เพื่อตรวจว่าฟอร์มแจ้งข้อผิดพลาดเมื่ออ่านไม่ได้ จากนั้นเปิด Reader กลับและตรวจ `/health` อีกครั้ง
6. ทดลองหน้าจัดหมวด Scopus แยก `scopus_benchmark_documents` กับ `scopus_documents` เลือกปีและเริ่มจำนวนน้อยก่อน ตรวจหมวด, confidence, ความคืบหน้า และข้อมูลในตารางที่เลือกก่อนจัดหมวดจำนวนมาก

หลังผ่านการทดสอบ ให้ตั้ง Ollama, Reader และ Classification API ให้เริ่มอัตโนมัติหลังรีบูตด้วยบัญชีบริการที่อ่าน `.env` และใช้โมเดลของ Ollama ได้ หากใช้ Windows service manager เช่น NSSM ให้กำหนด `Application` เป็น Python ใน `.venv`, `Arguments` เป็น `-m uvicorn ...`, และ `Startup directory` เป็น `C:\services\academic-insight-ai` แยกสองบริการ จากนั้นรีบูต VM หนึ่งครั้งและตรวจ `/health` กับการอ่าน PDF ซ้ำ
