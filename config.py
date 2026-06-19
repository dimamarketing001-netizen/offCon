import os
from dotenv import load_dotenv

# ===== БИТРИКС24 =====
B24_WEBHOOK = "https://b24-p41gmg.bitrix24.ru/rest/30/6k67fjhrmukh7ql7/"

# ===== GROQ =====
GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
GROQ_TEXT_MODEL = "llama-3.3-70b-versatile"

COMPANY_METRIKA_MAP = {
    "710292269": {
        "counter_id": "109482954",
        "token":      "y0__wgBELe_ke4IGPjkQyDqne79FzC_lOrsCOIpWjENCnLKn74WmNMNNRxgWI6T",
    },
    "710003041": {
        "counter_id": "109281290",
        "token":      "y0__wgBEITzhfAFGMn1QyD8hu79FzDmwdSSCBDYiojwZM58EnVMEpUlO9pc43vS",
    },
    "710450259": {
        "counter_id": "103733376",
        "token":      "y0__wgBEJKIlYkIGND1QyDY8u39F4F5gozY3hR9fDx2dqodPhjfbKkN",
    },
    "702962264": {
        "counter_id": "103733376",
        "token":      "y0__wgBEJKIlYkIGND1QyDY8u39F4F5gozY3hR9fDx2dqodPhjfbKkN",
    },
    "710042583": {
        "counter_id": "109320307",
        "token":      "y0__wgBEOKP6uwIGKXqQyD2ku79FzC_lOrsCLTQoHuQWNDD8o8RbGy-ErlItk1n",
    },
}

# ===== БИЗНЕС ЛОГИКА =====
ALLOWED_CITIES = ["екатеринбург", "челябинск"]
MIN_DEBT_AMOUNT = 300_000
MIN_CALL_DURATION = 40  # секунд

# Статусы которые сразу квалифицированы
QUALIFIED_STATUSES = [
    "UC_O5Z3U3",
    "UC_TG2I2A",
    "UC_DK6IWL",
    "UC_YL1CVZ",
    "CONVERTED"
]

# ===== ПОЛЯ В Б24 =====
FIELD_METRIKA_SENT  = "UF_CRM_LEAD_METRIKA_SENT"
FIELD_GPT_CITY      = "UF_CRM_LEAD_GPT_CITY"
FIELD_GPT_DEBT      = "UF_CRM_LEAD_GPT_DEBT"
FIELD_GPT_QUALIFIED = "UF_CRM_LEAD_GPT_QUALIFIED"
FIELD_GPT_RESULT    = "UF_CRM_LEAD_GPT_RESULT"
FIELD_TRANSCRIPT = "UF_CRM_LEAD_TRANSCRIPT"

# ===== ПУТИ =====
TEMP_DIR = "/tmp/audio_processing"
METRIKA_GOAL = "qualified_lead"