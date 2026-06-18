# ===== БИТРИКС24 =====
B24_WEBHOOK = "https://b24-p41gmg.bitrix24.ru/rest/30/6k67fjhrmukh7ql7/"

# ===== GROQ =====
GROQ_API_KEY = "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"
GROQ_TEXT_MODEL = "llama-3.3-70b-versatile"

COMPANY_METRIKA_MAP = {
    "710292269": {
        "counter_id": "109482954",
        "token":      "97cd861e1b4d47ac96b286c4eaa51423",
    },
    "710003041": {
        "counter_id": "109281290",
        "token":      "2222aa52b80b4a30b053f4609d9621d8",
    },
    "710450259": {
        "counter_id": "103733376",
        "token":      "270b4f8690e04214a2441a59ed9b89b7",
    },
    "702962264": {
        "counter_id": "103733376",
        "token":      "270b4f8690e04214a2441a59ed9b89b7",
    },
    "710042583": {
        "counter_id": "109320307",
        "token":      "97cd861e1b4d47ac96b286c4eaa51423",
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

# ===== ПУТИ =====
TEMP_DIR = "/tmp/audio_processing"