import os
from dotenv import load_dotenv

load_dotenv()

# ===== БИТРИКС24 =====
B24_WEBHOOK = os.getenv("B24_WEBHOOK", "").strip()
METRIKA_TOKEN = os.getenv("METRIKA_TOKEN", "").strip()

if not B24_WEBHOOK:
    raise RuntimeError("B24_WEBHOOK is not configured in .env")
if not METRIKA_TOKEN:
    raise RuntimeError("METRIKA_TOKEN is not configured in .env")
COMPANY_METRIKA_MAP = {
"713904508": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713988705": {
        "counter_id": "112101373",
        "token": METRIKA_TOKEN,
    },
"713894743": {
        "counter_id": "108673607",
        "token": METRIKA_TOKEN,
    },
"713853855": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713811312": {
        "counter_id": "110270327",
        "token": METRIKA_TOKEN,
    },
"713530764": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713853321": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713685932": {
        "counter_id": "108673607",
        "token": METRIKA_TOKEN,
    },
"713574142": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713536397": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713538109": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713538150": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713538292": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713538297": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713538302": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713538307": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713538315": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713538327": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539056": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539062": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539082": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539100": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539118": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539122": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539130": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539137": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539145": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539166": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539174": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539182": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539187": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539193": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539207": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539217": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539226": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539229": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539235": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539247": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539253": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539261": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539268": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539272": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539286": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539292": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539300": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539314": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539320": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539330": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539339": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539344": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539350": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539355": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539364": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539370": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539378": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539383": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539386": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539392": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539396": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539404": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539410": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539422": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539433": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539441": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539457": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539462": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539468": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539483": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539488": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539500": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539507": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
"713539512": {
        "counter_id": "111540304",
        "token": METRIKA_TOKEN,
    },
}

# Статусы которые сразу квалифицированы
QUALIFIED_STATUSES = [
    "10",
    "11",
    "12",
    "CONVERTED"
]

# ===== ПОЛЯ В Б24 =====
FIELD_LEAD_SENT = "UF_CRM_1786470227303"
FIELD_SCORE = "UF_CRM_1786470518869"
FIELD_SEGMENT = "UF_CRM_1786470569871"

FIELD_REGION_BOOST = "UF_CRM_1786470626693"
FIELD_MEETING = "UF_CRM_1786470683011"
FIELD_VISIT = "UF_CRM_1786470734539"
FIELD_CONTRACT = "UF_CRM_1786470801159"
FIELD_PAYMENT = "UF_CRM_1786470855942"

FIELD_LOG = "UF_CRM_1786470902564"
FIELD_METRIKA_SENT = "UF_CRM_1786471589314"
FIELD_CITY = "UF_CRM_1622543817615"
FIELD_FORM_TEXT = "UF_CRM_1651049909485"

# ===== ЦЕЛЕВЫЕ ГОРОДА =====
# Все значения уже нормализованы: lowercase, без цифр на конце, "ё" -> "е"
ALLOWED_CITIES = {
    "абакан",
    "ангарск",
    "архангельск",
    "барнаул",
    "благовещенск",
    "братск",
    "брянск",
    "великий новгород",
    "владивосток",
    "владикавказ",
    "вологда",
    "воронеж",
    "екатеринбург",
    "иваново",
    "ижевск",
    "иркутск",
    "йошкар-ола",
    "казань",
    "калуга",
    "кемерово",
    "киров",
    "комсомольск-на-амуре",
    "красноярск",
    "курган",
    "луганск",
    "махачкала",
    "москва",
    "нальчик",
    "находка",
    "нижневартовск",
    "нижний тагил",
    "новокузнецк",
    "омск",
    "орел",
    "оренбург",
    "орск",
    "пенза",
    "пермь",
    "петрозаводск",
    "петропавловск-камчатский",
    "псков",
    "ростов-на-дону",
    "самара",
    "санкт-петербург",
    "смоленск",
    "сочи",
    "сургут",
    "сыктывкар",
    "тольятти",
    "томск",
    "тула",
    "тюмень",
    "улан-удэ",
    "уссурийск",
    "уфа",
    "хабаровск",
    "чебоксары",
    "челябинск",
    "череповец",
    "чита",
    "шахты",
    "южно-сахалинск",
    "якутск",
    "ярославль",
}

# ===== ПУТИ =====
TEMP_DIR = "/tmp/audio_processing"
METRIKA_GOAL = "qualified_lead"

# ===== ИСКЛЮЧЕНИЯ ДЛЯ ПОВТОРНОГО СКОРИНГА =====
# ID кампаний (после очистки от нижних подчеркиваний),
# для которых НЕ должен рассчитываться повторный скоринг (динамика)
SKIP_DYNAMIC_SCORING_COMPANIES = {
    "713853321",
}