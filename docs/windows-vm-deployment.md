# ติดตั้ง Paper AI บน Windows VM

คู่มือนี้สมมติว่า VM ใช้ Windows Server 2025 และมี `fund-management` frontend/backend รันอยู่แล้ว โดยติดตั้ง `academic-insight-ai` บน **VM เดียวกับ backend** หากอยู่คนละ VM ให้เปลี่ยน URL ของ AI API ใน backend เป็น IP ภายในเครือข่าย และอนุญาตเฉพาะ backend ให้เข้าถึงพอร์ต 8101/8102

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
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env
```

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

## 5. เชื่อม backend เดิม

ดึงโค้ด backend/frontend รุ่นที่มีการเชื่อม Paper AI แล้ว ตรวจว่า migration `045_20260920_add_paper_ai_fields.sql` และ `046_20260922_allow_paper_classification_preface.sql` ถูกใช้กับ **ฐานข้อมูลที่ถูกต้อง** แล้ว (`paper_categories` มี 7 หมวด และมี `paper_ai_jobs`) ไม่ต้องรัน migration ซ้ำหากใช้งานไปแล้ว

ใน `.env` ของ `fund-management-api` บน VM ให้ตั้งค่า:

```dotenv
PAPER_READER_API_URL=http://127.0.0.1:8102
PAPER_CLASSIFICATION_API_URL=http://127.0.0.1:8101
PAPER_AI_API_KEY=<ค่าเดียวกับ AI_API_KEY>
PAPER_AI_TIMEOUT_SECONDS=600
```

รีสตาร์ตเฉพาะ backend ให้โหลดค่าใหม่ Frontend เรียก backend เดิมและไม่ต้องรู้ `AI_API_KEY` โดยตรง หน้าขอทุนใช้ Reader เพื่อเติมข้อมูลและสรุป PDF; การจัดหมวดบทความเป็น API อีกตัวที่ backend เรียกแยก

## 6. ทดสอบก่อนเปิดใช้งานจริง

1. ตรวจ `/health` ทั้งสอง API และ `ollama list` ให้ผ่าน
2. เข้าแบบฟอร์มขอทุนด้วยบัญชีทดสอบ แนบ PDF บทความจริง ตรวจชื่อเรื่อง DOI, Abstract ต้นฉบับ และสรุปภาษาไทย โดยยังไม่ส่งคำร้อง
3. แนบ PDF ที่ไม่ใช่บทความวิจัย ต้องเห็นข้อความว่า `ไฟล์ที่แนบไม่พบลักษณะของบทความวิจัย กรุณาแนบไฟล์ PDF ที่มีข้อมูลบทความ`
4. ทดลอง PDF สแกนอย่างน้อยหนึ่งไฟล์เพื่อยืนยันเส้นทาง OCR จริง (`ocrmypdf`, Tesseract ภาษาไทย/อังกฤษ และ Ghostscript)
5. ทดลอง API จัดหมวดกับบทความหนึ่งรายการผ่าน backend หรือ Postman โดยใช้หมวดจาก `paper_categories` และตรวจผลก่อนอัปเดตข้อมูลจำนวนมาก

หลังผ่านการทดสอบ ให้ตั้ง Ollama, Reader และ Classification API ให้เริ่มอัตโนมัติหลังรีบูตด้วยบัญชีบริการที่อ่าน `.env` และใช้โมเดลของ Ollama ได้ หากใช้ Windows service manager เช่น NSSM ให้กำหนด `Application` เป็น Python ใน `.venv`, `Arguments` เป็น `-m uvicorn ...`, และ `Startup directory` เป็น `C:\services\academic-insight-ai` แยกสองบริการ จากนั้นรีบูต VM หนึ่งครั้งและตรวจ `/health` กับการอ่าน PDF ซ้ำ
