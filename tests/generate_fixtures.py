# -*- coding: utf-8 -*-
"""
Генератор прикладных фикстур для бенчмарка PASH (Директива 010).
Создает 5 реалистичных, но сгенерированных файлов для замера экономии.
"""
import os
from pathlib import Path

# Используем абсолютные пути
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = PROJECT_ROOT / "tests" / "applied_fixtures"
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

# 1. Юридический текст NDA (~45k знаков)
nda_base = """THIS NON-DISCLOSURE AGREEMENT (the "Agreement") is entered into as of the date of last signature below (the "Effective Date"), by and between the undersigned party ("Recipient") and the disclosing party ("Discloser"). 
WHEREAS, Discloser possesses certain confidential and proprietary information relating to its business, products, and services; and WHEREAS, Recipient desires to receive such information for the purpose of evaluating a potential business relationship.
NOW, THEREFORE, in consideration of the mutual covenants contained herein, the parties agree as follows:
1. Definition of Confidential Information. "Confidential Information" means any and all non-public information disclosed by Discloser to Recipient, whether orally or in writing, that is designated as confidential or that reasonably should be understood to be confidential given the nature of the information and the circumstances of disclosure.
2. Obligations of Recipient. Recipient shall hold and maintain the Confidential Information in strictest confidence for the sole and exclusive benefit of the Discloser. Recipient shall carefully restrict access to Confidential Information to employees, contractors, and third parties as is reasonably required and shall require those persons to sign nondisclosure restrictions at least as protective as those in this Agreement.
"""
with open(FIXTURE_DIR / "1_legal_nda.txt", "w", encoding="utf-8") as f:
    f.write(nda_base * 150) # ~45k знаков

# 2. TechCrunch HTML (~120 КБ)
html_base = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Startup Raises $50M in Series B</title>
<script>console.log("analytics tracking script v4.2.1 initialized");</script>
<style>body{font-family:Arial,sans-serif;margin:0;padding:20px;color:#333;}</style>
</head><body>
<article><h1>AI Startup Secures Major Funding Round</h1>
<p>SAN FRANCISCO — In a landmark deal, the artificial intelligence company announced today that it has raised $50 million in Series B funding, led by top-tier venture capital firms. The funds will be used to expand the engineering team and accelerate the development of their core machine learning platform.</p>
<p>Industry analysts suggest this valuation reflects the growing demand for scalable, enterprise-grade AI solutions. "We are thrilled to partner with investors who share our vision for the future of work," said the CEO in a press statement.</p>
<!-- Repeated content to simulate a long article with boilerplate -->
</article>
</body></html>"""
with open(FIXTURE_DIR / "2_techcrunch_page.html", "w", encoding="utf-8") as f:
    f.write(html_base * 250) # ~120KB

# 3. AWS Server Log (800 строк)
log_base = """2023-10-27T10:15:30.123Z [INFO] (node:1234) Starting application server on port 8080
2023-10-27T10:15:30.456Z [DEBUG] Database connection pool initialized with 10 connections
2023-10-27T10:15:31.789Z [WARN] High memory usage detected: 75% of allocated heap
2023-10-27T10:15:32.012Z [ERROR] Connection timeout to Redis cache at 10.0.0.5:6379
2023-10-27T10:15:32.345Z [INFO] Retrying connection to Redis cache (attempt 1/3)
2023-10-27T10:15:33.678Z [ERROR] Fatal: Unable to establish connection to Redis cache after 3 attempts
"""
with open(FIXTURE_DIR / "3_aws_server.log", "w", encoding="utf-8") as f:
    for i in range(800):
        f.write(log_base.replace("10:15:3", f"10:{15+i//60}:{(i%60):02d}"))

# 4. Company Contacts HTML (Разметка + 1 email)
contact_row = """<tr><td>John Doe</td><td>Engineering</td><td>john.doe@example.com</td></tr>"""
contacts_html = f"""<!DOCTYPE html>
<html><body><h1>Our Team</h1>
<table border="1">{contact_row * 40}</table>
<p>For all enterprise inquiries, please contact our main office at: <strong>enterprise-sales@globaltech-corp.com</strong></p>
</body></html>"""
with open(FIXTURE_DIR / "4_company_contacts.html", "w", encoding="utf-8") as f:
    f.write(contacts_html)

# 5. Monolith Script (2500 строк, редкая переменная)
func_base = """
def process_data_batch_{0}(data):
    # Processing logic for batch {0}
    if not data:
        return None
    result = []
    for item in data:
        result.append(item * 2)
    return result
"""
with open(FIXTURE_DIR / "5_monolith_script.py", "w", encoding="utf-8") as f:
    for i in range(1200):
        f.write(func_base.format(i))
    f.write("\n# CRITICAL CONFIGURATION\nAPI_SECRET_KEY = 'sk-live-9a8b7c6d5e4f3g2h1'\n# END CRITICAL\n")

print(f"✅ Фикстуры успешно сгенерированы в {FIXTURE_DIR}")