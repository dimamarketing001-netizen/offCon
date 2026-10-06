from typing import Optional, Dict, Tuple
import re
from urllib.parse import urlparse, parse_qs

from b24_client import update_lead, b24_request, get_lead
from metrika_client import send_conversion
from config import (
    QUALIFIED_STATUSES,
    COMPANY_METRIKA_MAP,
    ALLOWED_CITIES,
    FIELD_METRIKA_SENT,
    FIELD_LEAD_SENT,
    FIELD_SCORE,
    FIELD_SEGMENT,
    FIELD_REGION_BOOST,
    FIELD_MEETING,
    FIELD_VISIT,
    FIELD_CONTRACT,
    FIELD_PAYMENT,
    FIELD_LOG,
    FIELD_CITY,
    FIELD_FORM_TEXT,
    SKIP_DYNAMIC_SCORING_COMPANIES,  # <-- Импортируем список исключений
)


def is_true(value) -> bool:
    return str(value).strip().lower() in ("1", "true", "y", "yes", "да")


def norm(value: Optional[str]) -> str:
    return (value or "").strip().lower().replace("ё", "е")


def normalize_city_name(value: Optional[str]) -> str:
    city = norm(value)
    city = re.sub(r"\s+\d+$", "", city)
    city = city.split(",")[0].strip()
    city = re.sub(r"[^\w\s\-]+$", "", city)
    city = re.sub(r"\s+", " ", city).strip()
    return city


def get_comment_text(lead: dict) -> str:
    return (
        lead.get(FIELD_FORM_TEXT)
        or lead.get("COMMENTS")
        or ""
    )


def extract_utm_campaign_key(value: str) -> str:
    raw = (value or "").strip()

    if not raw:
        return ""

    if raw.isdigit():
        return raw

    match = re.search(r"_(\d+)\s*$", raw)
    if match:
        return match.group(1)

    match = re.search(r"(\d+)\s*$", raw)
    if match:
        return match.group(1)

    return raw


def parse_ym_uid(lead: dict) -> Optional[str]:
    sources = [
        get_comment_text(lead),
        lead.get("UF_CRM_COOKIES") or "",
        lead.get("UF_CRM_YM_UID") or "",
    ]

    patterns = [
        r"_ym_uid\s*[:=]\s*(\d+)",
        r"yandex\s+clientid\s*[:=]\s*(\d+)",
        r"clientid\s*[:=]\s*(\d+)",
    ]

    for source in sources:
        text = str(source)
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

    return None


def parse_yclid(lead: dict) -> Optional[str]:
    source_description = (lead.get("SOURCE_DESCRIPTION") or "").strip()
    if not source_description:
        return None

    try:
        parsed = urlparse(source_description)
        qs = parse_qs(parsed.query)

        for key in ("utm_yclid", "yclid"):
            values = qs.get(key)
            if values and values[0]:
                return values[0].strip()
    except Exception:
        pass

    match = re.search(r"(?:utm_yclid|yclid)=([0-9]+)", source_description, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def get_metrika_ids(lead: dict) -> Tuple[Optional[str], Optional[str]]:
    ym_uid = parse_ym_uid(lead)
    if ym_uid:
        return ym_uid, None

    yclid = parse_yclid(lead)
    if yclid:
        return None, yclid

    return None, None


def get_phone(lead: dict) -> Optional[str]:
    phones = lead.get("PHONE", [])
    if phones and isinstance(phones, list):
        return phones[0].get("VALUE")
    return None


def get_metrika_config(lead: dict) -> Optional[dict]:
    utm_campaign_raw = (lead.get("UTM_CAMPAIGN") or "").strip()

    if not utm_campaign_raw:
        print("   ⏭️ Нет UTM_CAMPAIGN — пропускаем")
        return None

    utm_campaign_key = extract_utm_campaign_key(utm_campaign_raw)

    print(f"   🔎 UTM_CAMPAIGN raw='{utm_campaign_raw}' → key='{utm_campaign_key}'")

    config = COMPANY_METRIKA_MAP.get(utm_campaign_key)
    if not config:
        print(f"   ⏭️ UTM_CAMPAIGN key={utm_campaign_key} не найден в маппинге")
        return None

    print(f"   ✅ UTM_CAMPAIGN key={utm_campaign_key} → counter={config['counter_id']}")
    return config


def extract_field(comments: str, field_name: str) -> Optional[str]:
    pattern = re.compile(
        r"^\s*" + re.escape(field_name) + r"\s*:\s*(.+)$",
        re.MULTILINE | re.IGNORECASE
    )
    match = pattern.search(comments or "")
    if match:
        return match.group(1).strip()
    return None


def extract_credit_amnesty_answer(comments: str, label: str) -> Optional[str]:
    pattern = re.compile(
        rf"•\s*{re.escape(label)}\s*:\s*(.+?)(?=(?:\s*•\s*[^:]+:\s*)|(?:\s*═══)|$)",
        re.IGNORECASE | re.DOTALL
    )
    match = pattern.search(comments or "")
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    return None


def extract_legacy_label_answer(comments: str, label: str) -> Optional[str]:
    pattern = re.compile(
        rf"{re.escape(label)}\s*:\s*(?:\r?\n)+\s*-\s*(.+)",
        re.IGNORECASE
    )
    match = pattern.search(comments or "")
    if match:
        return match.group(1).strip()
    return None


def extract_city_from_source_description(lead: dict) -> str:
    source_description = (lead.get("SOURCE_DESCRIPTION") or "").strip()
    if not source_description:
        return ""

    try:
        parsed = urlparse(source_description)
        qs = parse_qs(parsed.query)

        values = qs.get("r_name")
        if values and values[0]:
            return normalize_city_name(values[0])
    except Exception:
        pass

    return ""


def extract_city_from_title(lead: dict) -> str:
    title = lead.get("TITLE") or ""
    match = re.search(r"^[^|]+\|\s*([^|]+?)\s*\|", title)
    if match:
        return normalize_city_name(match.group(1))
    return ""


def extract_city_from_comments(comments: str) -> str:
    comments = comments or ""

    patterns = [
        r"Город\s*:\s*-\s*([A-Za-zА-Яа-яЁё\-\s]+?)(?=\s*(?::\s*-\s*Заявка|Регион\s*:|═══|$))",
        r"Город\s*:\s*([A-Za-zА-Яа-яЁё\-\s]+?)(?=\s*(?:Регион\s*:|═══|$))",
    ]

    for pattern in patterns:
        match = re.search(pattern, comments, re.IGNORECASE | re.DOTALL)
        if match:
            return normalize_city_name(match.group(1))

    city = extract_field(comments, "city")
    if city:
        return normalize_city_name(city)

    region_match = re.search(r"Регион\s*:\s*([^,\n\r•]+)", comments, re.IGNORECASE)
    if region_match:
        return normalize_city_name(region_match.group(1))

    return ""


def get_effective_city(lead: dict, parsed_city: Optional[str] = None) -> str:
    city_from_field = normalize_city_name(lead.get(FIELD_CITY))
    if city_from_field:
        return city_from_field

    if parsed_city:
        return normalize_city_name(parsed_city)

    city_from_comments = extract_city_from_comments(get_comment_text(lead))
    if city_from_comments:
        return city_from_comments

    city_from_source = extract_city_from_source_description(lead)
    if city_from_source:
        return city_from_source

    city_from_title = extract_city_from_title(lead)
    if city_from_title:
        return city_from_title

    return ""


def detect_comment_type(comments: str) -> Optional[str]:
    if not comments:
        return None

    lowered = norm(comments)

    if "1__ваш_долг_более_500_000_рублей" in lowered:
        return "quiz_questions"

    if "source: debt-quiz" in lowered or "delay_status:" in lowered:
        return "debt_quiz"

    if "кредитная амнистия" in lowered or "═══ ответы ═══" in lowered or "алименты/штрафы:" in lowered:
        return "credit_amnesty"

    if (
        "ваш долг более 500 000 рублей:" in lowered
        and "кредиторы подавали на вас в суд:" in lowered
        and "в отношении вас велось исполнительное производство:" in lowered
    ):
        return "quiz_text_legacy"

    return None


def normalize_old_debt_value(value: str) -> str:
    v = norm(value)

    if v == "да":
        return "более 500"
    if v == "нет":
        return "менее 500"
    if "более" in v and "500" in v:
        return "более 500"
    if "менее" in v and "500" in v:
        return "менее 500"

    return v


def normalize_court_value(value: str) -> str:
    v = norm(value)

    if "не знаю" in v or "не знает" in v:
        return "не знаю"
    if v.startswith("нет"):
        return "нет"
    if v.startswith("да"):
        return "да"
    if "пока не было" in v:
        return "нет"
    if "подавали" in v and "не " not in v:
        return "да"

    return v


def normalize_exec_value(value: str) -> str:
    v = norm(value)

    if "не знаю" in v or "не знает" in v:
        return "не знаю"
    if "было, но прекратилось" in v:
        return "нет"
    if "приставов не было" in v or "не было" in v:
        return "нет"
    if "идет взыскание" in v or "идёт взыскание" in v:
        return "да"
    if v.startswith("нет"):
        return "нет"
    if v.startswith("да"):
        return "да"

    return v


def normalize_mortgage_value(value: str) -> str:
    v = norm(value)

    if "нет" in v:
        return "нет"
    if "да" in v or "есть ипотека" in v:
        return "да"

    return v


def normalize_income_value(value: str) -> str:
    v = norm(value)

    if v == "да":
        return "да"
    if v == "нет":
        return "нет"

    if "официальная работа" in v or "официально" in v:
        return "official"
    if "неофициаль" in v:
        return "informal"
    if "пенсия" in v or "пособие" in v:
        return "pension"
    if "дохода нет" in v:
        return "no"

    return v


def normalize_property_value(value: str) -> str:
    v = norm(value)

    if v == "нет":
        return "нет"
    if v == "да":
        return "да"

    if "ничего нет" in v:
        return "none"
    if "есть автомобиль" in v or "автомобил" in v:
        return "car"
    if "есть недвижимость" in v or "недвижим" in v:
        return "estate"
    if "не знаю" in v:
        return "unknown"

    return v


def normalize_alimony_value(value: str) -> str:
    v = norm(value)

    if "не знаю" in v or "не знает" in v:
        return "не знаю"
    if v == "нет" or "таких долгов нет" in v:
        return "нет"
    if "понемногу" in v:
        return "mixed"
    if "алим" in v:
        return "alimony"
    if "штраф" in v or "налог" in v:
        return "fines"
    if v.startswith("да"):
        return "да"

    return v


def normalize_credit_amnesty_debt(value: str) -> str:
    v = norm(value)
    digits = []

    for item in re.findall(r"\d[\d\s]*", value or ""):
        try:
            digits.append(int(item.replace(" ", "")))
        except ValueError:
            pass

    if "до" in v and any(n <= 300000 for n in digits):
        return "less-300"

    if "более" in v and any(n >= 1500000 for n in digits):
        return "1500-plus"

    if len(digits) >= 2:
        low = min(digits)
        high = max(digits)

        if low <= 300000 and high <= 500000:
            return "300-500"
        if low >= 500000 or high >= 1500000:
            return "500-1500"

    if len(digits) == 1:
        number = digits[0]

        if number <= 300000:
            return "less-300"
        if 300000 < number <= 500000:
            return "300-500"
        if number > 500000 and number < 1500000:
            return "500-1500"
        if number >= 1500000 and "более" in v:
            return "1500-plus"
        if number >= 1500000:
            return "500-1500"

    return v


def extract_quiz_answers(comments: str) -> Dict[str, str]:
    answers = {}
    if not comments:
        return answers

    pattern = re.compile(r"^\s*([1-7])__[^:]+:\s*(.+)$", re.MULTILINE)

    mapping = {
        "1": "debt",
        "2": "court",
        "3": "exec",
        "4": "mortgage",
        "5": "alimony",
        "6": "income",
        "7": "property"
    }

    for q_num, value in pattern.findall(comments):
        key = mapping.get(q_num)
        if not key:
            continue

        if key == "debt":
            answers[key] = normalize_old_debt_value(value)
        elif key == "court":
            answers[key] = normalize_court_value(value)
        elif key == "exec":
            answers[key] = normalize_exec_value(value)
        elif key == "mortgage":
            answers[key] = normalize_mortgage_value(value)
        elif key == "alimony":
            answers[key] = normalize_alimony_value(value)
        elif key == "income":
            answers[key] = normalize_income_value(value)
        elif key == "property":
            answers[key] = normalize_property_value(value)

    return answers


def extract_quiz_text_legacy_answers(comments: str) -> Dict[str, str]:
    answers = {}

    mapping = {
        "Ваш долг более 500 000 рублей": ("debt", normalize_old_debt_value),
        "Кредиторы подавали на Вас в суд": ("court", normalize_court_value),
        "В отношении вас велось исполнительное производство": ("exec", normalize_exec_value),
        "Имеется ли у вас действующая ипотека": ("mortgage", normalize_mortgage_value),
        "Имеется ли обязательство по выплате алиментов": ("alimony", normalize_alimony_value),
        "У вас есть официальный доход": ("income", normalize_income_value),
        "На вас оформлена недвижимость или авто кроме единственного жилья": ("property", normalize_property_value),
    }

    for label, (key, normalizer) in mapping.items():
        value = extract_legacy_label_answer(comments, label)
        if value is not None:
            answers[key] = normalizer(value)

    return answers


def parse_credit_amnesty_answers(comments: str) -> dict:
    city = extract_city_from_comments(comments)

    debt_raw = extract_credit_amnesty_answer(comments, "Сумма долга")
    court_raw = extract_credit_amnesty_answer(comments, "Кредиторы подавали в суд")
    exec_raw = extract_credit_amnesty_answer(comments, "Исполнительное производство")
    income_raw = extract_credit_amnesty_answer(comments, "Официальный доход")
    mortgage_raw = extract_credit_amnesty_answer(comments, "Ипотека")
    property_raw = extract_credit_amnesty_answer(comments, "Имущество кроме единственного жилья")
    alimony_raw = extract_credit_amnesty_answer(comments, "Алименты/штрафы")

    print("   📝 Тип: credit_amnesty")
    print(f"      Город: {city or '-'}")
    print(f"      Сумма долга: {debt_raw}")
    print(f"      Суд: {court_raw}")
    print(f"      Исп. производство: {exec_raw}")
    print(f"      Доход: {income_raw}")
    print(f"      Ипотека: {mortgage_raw}")
    print(f"      Имущество: {property_raw}")
    print(f"      Алименты/штрафы: {alimony_raw}")

    answers = {
        "debt": normalize_credit_amnesty_debt(debt_raw or ""),
        "court": normalize_court_value(court_raw or ""),
        "exec": normalize_exec_value(exec_raw or ""),
        "income": normalize_income_value(income_raw or ""),
        "mortgage": normalize_mortgage_value(mortgage_raw or ""),
        "property": normalize_property_value(property_raw or ""),
        "alimony": normalize_alimony_value(alimony_raw or ""),
    }

    return {
        "comment_type": "credit_amnesty",
        "answers": answers,
        "city": city,
    }


def extract_base_scoring_payload(lead: dict) -> dict:
    comments = get_comment_text(lead)
    comment_type = detect_comment_type(comments)

    if comment_type == "quiz_questions":
        return {
            "comment_type": comment_type,
            "answers": extract_quiz_answers(comments),
            "city": get_effective_city(lead),
        }

    if comment_type == "quiz_text_legacy":
        return {
            "comment_type": comment_type,
            "answers": extract_quiz_text_legacy_answers(comments),
            "city": get_effective_city(lead),
        }

    if comment_type == "credit_amnesty":
        return parse_credit_amnesty_answers(comments)

    return {
        "comment_type": comment_type,
        "answers": {},
        "city": get_effective_city(lead),
    }


def check_stop_factors(answers: dict, lead: dict, city: Optional[str] = None) -> bool:
    if norm(answers.get("exec")) == "да":
        print("🔴 STOP: ФССП / активное взыскание")
        return True

    if norm(answers.get("mortgage")) == "да":
        print("🔴 STOP: Ипотека")
        return True

    if norm(answers.get("alimony")) in ("да", "alimony", "fines", "mixed"):
        print("🔴 STOP: Алименты / штрафы")
        return True

    effective_city = get_effective_city(lead, city)
    if effective_city:
        if effective_city not in ALLOWED_CITIES:
            print(f"🔴 STOP: Город не ЦА ({effective_city})")
            return True

    return False


def check_region_boost(lead: dict) -> bool:
    city = get_effective_city(lead)
    return bool(city and city in ALLOWED_CITIES)


def has_won_deal(lead_id: str) -> bool:
    deals = b24_request("crm.deal.list", {
        "filter": {
            "LEAD_ID": lead_id,
            "TYPE_ID": "SALE",
            "CATEGORY_ID": 0,
            "STAGE_ID": "WON"
        },
        "select": ["ID"]
    }).get("result", [])

    return bool(deals)


def calculate_score(data: Dict[str, str]) -> int:
    debt = norm(data.get("debt"))
    court = norm(data.get("court"))
    exec_proc = norm(data.get("exec"))
    mortgage = norm(data.get("mortgage"))
    alimony = norm(data.get("alimony"))
    income = norm(data.get("income"))
    property_ = norm(data.get("property"))

    score = 0

    if debt == "более 500":
        score += 200
    elif debt == "менее 500":
        score += 120
    elif debt == "less-300":
        score += 0
    elif debt == "300-500":
        score += 50
    elif debt == "500-1500":
        score += 100
    elif debt == "1500-plus":
        score += 200

    if court == "нет":
        score += 150
    elif court == "не знаю":
        score += 120
    elif court == "да":
        score += 60

    if exec_proc == "нет":
        score += 200
    elif exec_proc == "не знаю":
        score += 150

    if mortgage == "нет":
        score += 100
    elif mortgage == "да":
        score += 40

    if alimony == "нет":
        score += 50
    elif alimony == "не знаю":
        score += 20

    if income == "да":
        score += 200
    elif income == "нет":
        score += 80
    elif income == "official":
        score += 200
    elif income == "informal":
        score += 150
    elif income == "pension":
        score += 140
    elif income == "no":
        score += 80

    if property_ == "нет":
        score += 100
    elif property_ == "да":
        score += 60
    elif property_ == "none":
        score += 100
    elif property_ == "car":
        score += 60
    elif property_ == "estate":
        score += 40
    elif property_ == "unknown":
        score += 50

    score = max(0, min(score, 1000))

    print(f"   📊 SCORE={score}")
    return score


def get_segment(score: int) -> str:
    if score == 0:
        return "Стоп-лид"
    if score >= 10000:
        return "LTV MAX"
    if score >= 3000:
        return "Контракт"
    if score >= 1000:
        return "Прогретый"
    if score >= 600:
        return "Квалифицирован"
    if score >= 100:
        return "Холодный"
    return "Красная зона"


def update_score_and_send(lead_id: str, add_value: int, reason: str) -> bool:
    current_lead = get_lead(lead_id)
    if not current_lead:
        print(f"   ❌ Не удалось получить лид {lead_id} из Б24")
        return False

    current_score = int(current_lead.get(FIELD_SCORE) or 0)
    new_score = current_score + add_value
    segment = get_segment(new_score)

    ym_uid, yclid = get_metrika_ids(current_lead)
    phone = get_phone(current_lead)
    metrika_cfg = get_metrika_config(current_lead)

    print(f"📈 {reason}: +{add_value} → {new_score}")

    if metrika_cfg and (ym_uid or yclid or phone):
        send_conversion(
            counter_id=metrika_cfg["counter_id"],
            token=metrika_cfg["token"],
            client_id=ym_uid,
            yclid=yclid,
            phone=phone,
            goal_name="lead",
            revenue=new_score
        )
    else:
        print("   ⏭️ Нет данных для отправки в Метрику, обновляем только Б24")

    log_text = f"{reason} +{add_value} → {new_score}"

    update_lead(lead_id, {
        FIELD_SCORE: new_score,
        FIELD_SEGMENT: segment,
        FIELD_LOG: log_text
    })

    return True


def process_dynamic_events(lead: dict):
    lead_id = lead.get("ID")
    status_id = str(lead.get("STATUS_ID") or "")

    if not is_true(lead.get(FIELD_REGION_BOOST)):
        if check_region_boost(lead):
            if update_score_and_send(lead_id, 500, "Регион"):
                update_lead(lead_id, {FIELD_REGION_BOOST: True})

    if not is_true(lead.get(FIELD_PAYMENT)):
        if has_won_deal(lead_id):
            if update_score_and_send(lead_id, 10000, "Оплата"):
                update_lead(lead_id, {
                    FIELD_PAYMENT: True,
                    FIELD_CONTRACT: True,
                    FIELD_VISIT: True,
                    FIELD_MEETING: True,
                    FIELD_REGION_BOOST: True
                })
            return

    if not is_true(lead.get(FIELD_CONTRACT)):
        if status_id == "CONVERTED":
            if update_score_and_send(lead_id, 3000, "Договор"):
                update_lead(lead_id, {
                    FIELD_CONTRACT: True,
                    FIELD_VISIT: True,
                    FIELD_MEETING: True
                })
            return

    if not is_true(lead.get(FIELD_VISIT)):
        if status_id in ("11", "12"):
            if update_score_and_send(lead_id, 500, "Визит"):
                update_lead(lead_id, {
                    FIELD_VISIT: True,
                    FIELD_MEETING: True
                })
            return

    if not is_true(lead.get(FIELD_MEETING)):
        if status_id == "10":
            if update_score_and_send(lead_id, 300, "Назначена встреча"):
                update_lead(lead_id, {
                    FIELD_MEETING: True
                })


def check_quiz_questions(comments: str) -> dict:
    debt = extract_field(comments, "1__Ваш_долг_более_500_000_рублей")
    court = extract_field(comments, "2__Кредиторы_подавали_на_Вас_в_суд")
    exec_proc = extract_field(comments, "3__В_отношении_вас_велось_исполнительное_производство")
    mortgage = extract_field(comments, "4__Имеется_ли_у_вас_действующая_ипотека")
    alimony = extract_field(comments, "5__Имеется_ли_обязательство_по_выплате_алиментов")

    print("   📝 Тип: quiz_questions")
    print(f"      Долг > 500к: {debt}")
    print(f"      Суд: {court}")
    print(f"      Исп. производство: {exec_proc}")
    print(f"      Ипотека: {mortgage}")
    print(f"      Алименты: {alimony}")

    reasons = []

    debt_ok = debt and "да" in debt.lower()
    if not debt_ok:
        reasons.append(f"Долг < 500к ({debt})")

    court_ok = court and court.lower() in ("нет", "не знаю")
    if not court_ok:
        reasons.append(f"Суд: {court}")

    exec_ok = exec_proc and exec_proc.lower() in ("нет", "не знаю")
    if not exec_ok:
        reasons.append(f"Исп.произв: {exec_proc}")

    mortgage_ok = mortgage and mortgage.lower() == "нет"
    if not mortgage_ok:
        reasons.append(f"Ипотека: {mortgage}")

    alimony_ok = alimony and alimony.lower() in ("нет", "не знаю")
    if not alimony_ok:
        reasons.append(f"Алименты: {alimony}")

    qualified = debt_ok and court_ok and exec_ok and mortgage_ok and alimony_ok

    return {
        "qualified": qualified,
        "reason": "; ".join(reasons) if reasons else "Все условия выполнены",
        "city": None,
        "debt_amount": debt
    }


def check_quiz_text_legacy(comments: str) -> dict:
    debt = extract_legacy_label_answer(comments, "Ваш долг более 500 000 рублей")
    court = extract_legacy_label_answer(comments, "Кредиторы подавали на Вас в суд")
    exec_proc = extract_legacy_label_answer(comments, "В отношении вас велось исполнительное производство")
    mortgage = extract_legacy_label_answer(comments, "Имеется ли у вас действующая ипотека")
    alimony = extract_legacy_label_answer(comments, "Имеется ли обязательство по выплате алиментов")

    print("   📝 Тип: quiz_text_legacy")
    print(f"      Долг: {debt}")
    print(f"      Суд: {court}")
    print(f"      Исп. производство: {exec_proc}")
    print(f"      Ипотека: {mortgage}")
    print(f"      Алименты: {alimony}")

    reasons = []

    debt_ok = debt and "да" in debt.lower()
    if not debt_ok:
        reasons.append(f"Долг < 500к ({debt})")

    court_n = normalize_court_value(court or "")
    court_ok = court_n in ("нет", "не знаю")
    if not court_ok:
        reasons.append(f"Суд: {court}")

    exec_n = normalize_exec_value(exec_proc or "")
    exec_ok = exec_n in ("нет", "не знаю")
    if not exec_ok:
        reasons.append(f"Исп.произв: {exec_proc}")

    mortgage_n = normalize_mortgage_value(mortgage or "")
    mortgage_ok = mortgage_n == "нет"
    if not mortgage_ok:
        reasons.append(f"Ипотека: {mortgage}")

    alimony_n = normalize_alimony_value(alimony or "")
    alimony_ok = alimony_n in ("нет", "не знаю")
    if not alimony_ok:
        reasons.append(f"Алименты: {alimony}")

    qualified = debt_ok and court_ok and exec_ok and mortgage_ok and alimony_ok

    return {
        "qualified": qualified,
        "reason": "; ".join(reasons) if reasons else "Все условия выполнены",
        "city": None,
        "debt_amount": debt
    }


def check_debt_quiz(comments: str) -> dict:
    region = extract_field(comments, "region")
    delay_status = extract_field(comments, "delay_status")
    city = extract_field(comments, "city")
    debt_amount = extract_field(comments, "debt_amount")

    print("   📝 Тип: debt_quiz")
    print(f"      Регион: {region}")
    print(f"      Просрочка: {delay_status}")
    print(f"      Город: {city}")
    print(f"      Сумма долга: {debt_amount}")

    reasons = []

    allowed_regions = ["челябинская область", "свердловская область"]
    region_ok = region and region.lower() in allowed_regions
    if not region_ok:
        reasons.append(f"Регион: {region}")

    allowed_delays = ["менее 3 месяцев", "нет просрочек, но платить тяжело"]
    delay_ok = delay_status and delay_status.lower() in allowed_delays
    if not delay_ok:
        reasons.append(f"Просрочка: {delay_status}")

    qualified = region_ok and delay_ok

    return {
        "qualified": qualified,
        "reason": "; ".join(reasons) if reasons else "Все условия выполнены",
        "city": city,
        "debt_amount": debt_amount
    }


def analyze_comments(comments: str) -> dict:
    comment_type = detect_comment_type(comments)

    if comment_type == "quiz_questions":
        return check_quiz_questions(comments)
    elif comment_type == "quiz_text_legacy":
        return check_quiz_text_legacy(comments)
    elif comment_type == "debt_quiz":
        return check_debt_quiz(comments)
    elif comment_type == "credit_amnesty":
        print("   ℹ️ Формат credit_amnesty используется только для скоринга")
        return {
            "qualified": False,
            "reason": "Формат используется только для скоринга",
            "city": None,
            "debt_amount": None
        }
    else:
        print("   ⚠️ Неизвестный формат комментария")
        return {
            "qualified": False,
            "reason": "Неизвестный формат комментария",
            "city": None,
            "debt_amount": None
        }


def send_legacy_qualified_conversion(lead: dict, reason: str) -> str:
    lead_id = lead.get("ID")

    fresh_lead = get_lead(lead_id) or lead

    metrika_cfg = get_metrika_config(fresh_lead) or get_metrika_config(lead)
    if not metrika_cfg:
        return "no_utm"

    ym_uid, yclid = get_metrika_ids(fresh_lead)
    phone = get_phone(fresh_lead)

    if not ym_uid and not yclid:
        print(f"⏭️ Нет ym_uid/yclid для old qualified conversion | lead={lead_id}")
        return "no_ymuid"

    current_score = int(fresh_lead.get(FIELD_SCORE) or lead.get(FIELD_SCORE) or 1)

    sent = send_conversion(
        counter_id=metrika_cfg["counter_id"],
        token=metrika_cfg["token"],
        client_id=ym_uid,
        yclid=yclid,
        phone=phone,
        goal_name="lead",
        revenue=current_score
    )

    if sent:
        update_lead(lead_id, {
            FIELD_METRIKA_SENT: True,
            FIELD_LOG: reason
        })
        print(f"✅ Старая квалификация отправлена: {reason}")
        return "sent"

    print(f"❌ Ошибка отправки старой квалификации: {reason}")
    return "metrika_error"


def process_initial_lead(lead: dict) -> str:
    lead_id = lead.get("ID")
    status_id = str(lead.get("STATUS_ID") or "")

    print(f"\n{'=' * 60}")
    print(f"📋 Лид ID={lead_id} | Статус={status_id}")

    comments = get_comment_text(lead)
    ym_uid, yclid = get_metrika_ids(lead)
    phone = get_phone(lead)

    lead_sent_flag = is_true(lead.get(FIELD_LEAD_SENT))
    metrika_sent_flag = is_true(lead.get(FIELD_METRIKA_SENT))

    result = "not_qualified"

    if not lead_sent_flag:
        payload = extract_base_scoring_payload(lead)
        answers = payload.get("answers") or {}
        parsed_city = payload.get("city")

        if answers:
            metrika_cfg = get_metrika_config(lead)
            if not metrika_cfg:
                return "no_utm"

            if check_stop_factors(answers, lead, parsed_city):
                if ym_uid or yclid or phone:
                    send_conversion(
                        counter_id=metrika_cfg["counter_id"],
                        token=metrika_cfg["token"],
                        client_id=ym_uid,
                        yclid=yclid,
                        phone=phone,
                        goal_name="lead",
                        revenue=0
                    )

                update_lead(lead_id, {
                    FIELD_LEAD_SENT: True,
                    FIELD_SCORE: 0,
                    FIELD_SEGMENT: get_segment(0),
                    FIELD_LOG: "STOP-фактор"
                })

                print("🔴 STOP отправлен как 0. Больше не пересчитывается.")
                return "sent"

            base_score = calculate_score(answers)

            if ym_uid or yclid or phone:
                send_conversion(
                    counter_id=metrika_cfg["counter_id"],
                    token=metrika_cfg["token"],
                    client_id=ym_uid,
                    yclid=yclid,
                    phone=phone,
                    goal_name="lead",
                    revenue=base_score
                )

            segment = get_segment(base_score)

            update_lead(lead_id, {
                FIELD_LEAD_SENT: True,
                FIELD_SCORE: base_score,
                FIELD_SEGMENT: segment,
                FIELD_LOG: f"Базовый скоринг {base_score}"
            })

            print(f"✅ Базовый скоринг отправлен: {base_score}")

            lead_sent_flag = True
            lead[FIELD_LEAD_SENT] = True
            lead[FIELD_SCORE] = base_score
            lead[FIELD_SEGMENT] = segment
            result = "sent"

    if metrika_sent_flag:
        return result

    if lead_sent_flag and int(lead.get(FIELD_SCORE) or 0) == 0:
        print("⛔ STOP-лид. Старая квалификация отключена.")
        return result

    if status_id in QUALIFIED_STATUSES:
        return send_legacy_qualified_conversion(
            lead,
            f"Квалифицирован по статусу: {status_id}"
        )

    comment_type = detect_comment_type(comments)

    if comment_type in ("quiz_questions", "quiz_text_legacy", "debt_quiz"):
        analysis = analyze_comments(comments)

        if analysis["qualified"]:
            return send_legacy_qualified_conversion(
                lead,
                "Квалифицирован по комментарию"
            )

    return result


def process_dynamic_lead(lead: dict) -> str:
    lead_id = lead.get("ID")
    status_id = str(lead.get("STATUS_ID") or "")

    print(f"\n{'=' * 60}")
    print(f"📈 Динамика лида ID={lead_id} | Статус={status_id}")

    if not is_true(lead.get(FIELD_LEAD_SENT)):
        print("⏭️ Базовый скоринг ещё не отправлялся")
        return "skip"

    if int(lead.get(FIELD_SCORE) or 0) == 0:
        print("⛔ STOP-лид. Дальнейшая проверка отключена.")
        return "skip"

    # === НАЧАЛО ИЗМЕНЕНИЙ: Проверка исключения для повторного скоринга ===
    utm_campaign_raw = (lead.get("UTM_CAMPAIGN") or "").strip()
    if utm_campaign_raw:
        utm_campaign_key = extract_utm_campaign_key(utm_campaign_raw)
        if utm_campaign_key in SKIP_DYNAMIC_SCORING_COMPANIES:
            print(f"⏭️ Пропуск повторного скоринга: кампания ID={utm_campaign_key} в списке SKIP_DYNAMIC_SCORING_COMPANIES")
            return "skip"
    # === КОНЕЦ ИЗМЕНЕНИЙ ===

    process_dynamic_events(lead)
    return "ok"


def process_lead(lead: dict) -> str:
    return process_initial_lead(lead)
