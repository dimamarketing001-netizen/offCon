from typing import Optional, Dict
import re
from b24_client import get_calls_for_lead, update_lead, b24_request
from metrika_client import send_conversion
from config import (
    QUALIFIED_STATUSES,
    COMPANY_METRIKA_MAP,
    FIELD_METRIKA_SENT,
    FIELD_GPT_CITY,
    FIELD_GPT_DEBT,
    FIELD_GPT_QUALIFIED,
    FIELD_GPT_RESULT,
)

FIELD_LEAD_SENT = "UF_CRM_1784810882912"
FIELD_SCORE = "UF_CRM_1785127355773"
FIELD_SEGMENT = "UF_CRM_1784809635845"

FIELD_REGION_BOOST = "UF_CRM_1785129692124"
FIELD_MEETING = "UF_CRM_1785130223297"
FIELD_VISIT = "UF_CRM_1785129752702"
FIELD_CONTRACT = "UF_CRM_1785129817186"
FIELD_PAYMENT = "UF_CRM_1785129856486"

FIELD_LOG = "UF_CRM_1785133075725"

FIELD_CITY = "UF_CRM_1730379820755"

def check_stop_factors(answers: dict, lead: dict) -> bool:
    """
    Если любой стоп-фактор срабатывает —
    отправляем 0 и больше никогда не пересчитываем
    """

    # 1️⃣ ФССП
    if answers.get("exec", "").strip().lower() == "да":
        print("🔴 STOP: ФССП")
        return True

    # 2️⃣ Ипотека
    if answers.get("mortgage", "").strip().lower() == "да":
        print("🔴 STOP: Ипотека")
        return True

    # 3️⃣ Регион
    city = (lead.get(FIELD_CITY) or "").strip().lower()

    if city:
        if city not in ("челябинск", "екатеринбург"):
            print("🔴 STOP: Регион не ЦА")
            return True
    else:
        # ищем utm_region_id
        comments = lead.get("COMMENTS") or ""
        match = re.search(r'utm_region_id%3D(\d+)', comments)
        if match:
            region_id = match.group(1)
            if region_id not in ("54", "56"):
                print("🔴 STOP: utm_region_id не ЦА")
                return True

    return False

def check_region_boost(lead: dict) -> bool:
    city = (lead.get(FIELD_CITY) or "").strip().lower()

    if city in ("челябинск", "екатеринбург"):
        return True

    comments = lead.get("COMMENTS") or ""
    match = re.search(r'utm_region_id%3D(\d+)', comments)
    if match and match.group(1) in ("54", "56"):
        return True

    return False

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

def update_score_and_send(lead: dict, add_value: int, reason: str):
    lead_id = lead.get("ID")
    current_score = int(lead.get(FIELD_SCORE) or 0)

    new_score = current_score + add_value

    ym_uid = parse_ym_uid(lead)
    phone = get_phone(lead)
    metrika_cfg = get_metrika_config(lead)

    if not metrika_cfg or not (ym_uid or phone):
        return

    print(f"📈 {reason}: +{add_value} → {new_score}")

    send_conversion(
        counter_id=metrika_cfg["counter_id"],
        token=metrika_cfg["token"],
        client_id=ym_uid,
        phone=phone,
        goal_name="lead",
        revenue=new_score
    )

    log_text = f"{reason} +{add_value} → {new_score}"

    update_lead(lead_id, {
        FIELD_SCORE: new_score,
        FIELD_LOG: log_text
    })

def process_dynamic_events(lead: dict):
    lead_id = lead.get("ID")
    status_id = lead.get("STATUS_ID")

    # 1️⃣ Регион
    if not lead.get(FIELD_REGION_BOOST):
        if check_region_boost(lead):
            update_score_and_send(lead, 500, "Регион")
            update_lead(lead_id, {FIELD_REGION_BOOST: True})

    # 2️⃣ Оплата (самый приоритет)
    if not lead.get(FIELD_PAYMENT):
        if has_won_deal(lead_id):
            update_score_and_send(lead, 10000, "Оплата")

            update_lead(lead_id, {
                FIELD_PAYMENT: True,
                FIELD_CONTRACT: True,
                FIELD_VISIT: True,
                FIELD_MEETING: True,
                FIELD_REGION_BOOST: True
            })
            return

    # 3️⃣ Договор
    if not lead.get(FIELD_CONTRACT):
        if status_id == "CONVERTED":
            update_score_and_send(lead, 3000, "Договор")

            update_lead(lead_id, {
                FIELD_CONTRACT: True,
                FIELD_VISIT: True,
                FIELD_MEETING: True
            })
            return

    # 4️⃣ Визит
    if not lead.get(FIELD_VISIT):
        if status_id in ("UC_DK6IWL", "UC_YL1CVZ"):
            update_score_and_send(lead, 500, "Визит")

            update_lead(lead_id, {
                FIELD_VISIT: True,
                FIELD_MEETING: True
            })
            return

    # 5️⃣ Назначена встреча
    if not lead.get(FIELD_MEETING):
        if status_id == "UC_TG2I2A":
            update_score_and_send(lead, 300, "Назначена встреча")
            update_lead(lead_id, {
                FIELD_MEETING: True
            })

def parse_ym_uid(lead: dict) -> Optional[str]:
    """
    Ищем _ym_uid:
    1. Сначала в COMMENTS
    2. Если нет — в UF_CRM_COOKIES
    """

    # 1️⃣ Ищем в комментариях
    comments = lead.get("COMMENTS") or ""
    match = re.search(r'_ym_uid=(\d+)', comments)
    if match:
        return match.group(1)

    # 2️⃣ Ищем в поле куки
    cookies = lead.get('UF_CRM_COOKIES') or ''
    match = re.search(r'_ym_uid=(\d+)', cookies)
    if match:
        return match.group(1)

    return None


def get_phone(lead: dict) -> Optional[str]:
    phones = lead.get('PHONE', [])
    if phones and isinstance(phones, list):
        return phones[0].get('VALUE')
    return None


def get_metrika_config(lead: dict) -> Optional[dict]:
    utm_campaign = (lead.get('UTM_CAMPAIGN') or '').strip()

    if not utm_campaign:
        print(f"   ⏭️ Нет UTM_CAMPAIGN — пропускаем")
        return None

    config = COMPANY_METRIKA_MAP.get(utm_campaign)
    if not config:
        print(f"   ⏭️ UTM_CAMPAIGN={utm_campaign} не найден в маппинге")
        return None

    print(f"   ✅ UTM_CAMPAIGN={utm_campaign} → counter={config['counter_id']}")
    return config


def extract_field(comments: str, field_name: str) -> Optional[str]:
    """
    Извлекаем значение поля из комментария.
    Ищем строку вида 'field_name: значение'
    """
    pattern = re.compile(
        r'^\s*' + re.escape(field_name) + r'\s*:\s*(.+)$',
        re.MULTILINE | re.IGNORECASE
    )
    match = pattern.search(comments or '')
    if match:
        return match.group(1).strip()
    return None


def detect_comment_type(comments: str) -> Optional[str]:
    """
    Определяем тип комментария:
    - 'quiz_questions' — формат с вопросами 1__Ваш_долг...
    - 'debt_quiz' — формат с region, delay_status, source: debt-quiz
    - None — неизвестный формат
    """
    if not comments:
        return None

    if '1__Ваш_долг_более_500_000_рублей' in comments:
        return 'quiz_questions'

    if 'source: debt-quiz' in comments or 'delay_status:' in comments:
        return 'debt_quiz'

    return None


def check_quiz_questions(comments: str) -> dict:
    """
    Проверяем формат с вопросами (1__Ваш_долг...).

    Квалификация:
    1. долг >= 500 000 — Да
    2. кредиторы подавали в суд — Нет или Не знаю
    3. исполнительное производство — Нет или Не знаю
    4. действующая ипотека — Нет
    5. обязательство по алиментам — Нет или Не знаю
    """
    debt = extract_field(comments, '1__Ваш_долг_более_500_000_рублей')
    court = extract_field(comments, '2__Кредиторы_подавали_на_Вас_в_суд')
    exec_proc = extract_field(comments, '3__В_отношении_вас_велось_исполнительное_производство')
    mortgage = extract_field(comments, '4__Имеется_ли_у_вас_действующая_ипотека')
    alimony = extract_field(comments, '5__Имеется_ли_обязательство_по_выплате_алиментов')

    print(f"   📝 Тип: quiz_questions")
    print(f"      Долг > 500к: {debt}")
    print(f"      Суд: {court}")
    print(f"      Исп. производство: {exec_proc}")
    print(f"      Ипотека: {mortgage}")
    print(f"      Алименты: {alimony}")

    reasons = []

    # 1. Долг должен быть >= 500 000
    debt_ok = debt and 'да' in debt.lower()
    if not debt_ok:
        reasons.append(f"Долг < 500к ({debt})")

    # 2. Суд — Нет или Не знаю
    court_ok = court and court.lower() in ('нет', 'не знаю')
    if not court_ok:
        reasons.append(f"Суд: {court}")

    # 3. Исполнительное производство — Нет или Не знаю
    exec_ok = exec_proc and exec_proc.lower() in ('нет', 'не знаю')
    if not exec_ok:
        reasons.append(f"Исп.произв: {exec_proc}")

    # 4. Ипотека — Нет
    mortgage_ok = mortgage and mortgage.lower() == 'нет'
    if not mortgage_ok:
        reasons.append(f"Ипотека: {mortgage}")

    # 5. Алименты — Нет или Не знаю
    alimony_ok = alimony and alimony.lower() in ('нет', 'не знаю')
    if not alimony_ok:
        reasons.append(f"Алименты: {alimony}")

    qualified = debt_ok and court_ok and exec_ok and mortgage_ok and alimony_ok

    return {
        'qualified': qualified,
        'reason': '; '.join(reasons) if reasons else 'Все условия выполнены',
        'city': None,
        'debt_amount': debt
    }


def check_debt_quiz(comments: str) -> dict:
    """
    Проверяем формат debt-quiz (region, delay_status...).

    Квалификация:
    1. region — Челябинская область или Свердловская область
    2. delay_status — Менее 3 месяцев или Нет просрочек, но платить тяжело
    """
    region = extract_field(comments, 'region')
    delay_status = extract_field(comments, 'delay_status')
    city = extract_field(comments, 'city')
    debt_amount = extract_field(comments, 'debt_amount')

    print(f"   📝 Тип: debt_quiz")
    print(f"      Регион: {region}")
    print(f"      Просрочка: {delay_status}")
    print(f"      Город: {city}")
    print(f"      Сумма долга: {debt_amount}")

    reasons = []

    # 1. Регион
    allowed_regions = ['челябинская область', 'свердловская область']
    region_ok = region and region.lower() in allowed_regions
    if not region_ok:
        reasons.append(f"Регион: {region}")

    # 2. Просрочка
    allowed_delays = ['менее 3 месяцев', 'нет просрочек, но платить тяжело']
    delay_ok = delay_status and delay_status.lower() in allowed_delays
    if not delay_ok:
        reasons.append(f"Просрочка: {delay_status}")

    qualified = region_ok and delay_ok

    return {
        'qualified': qualified,
        'reason': '; '.join(reasons) if reasons else 'Все условия выполнены',
        'city': city,
        'debt_amount': debt_amount
    }

def extract_quiz_answers(comments: str) -> Dict[str, str]:
    answers = {}
    if not comments:
        return answers

    pattern = re.compile(r'^\s*([1-7])__[^:]+:\s*(.+)$', re.MULTILINE)

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
        if key:
            answers[key] = value.strip()

    return answers


def calculate_score(data: Dict[str, str]) -> int:
    def norm(v):
        return (v or "").strip().lower()

    debt = norm(data.get("debt"))
    court = norm(data.get("court"))
    exec_proc = norm(data.get("exec"))
    mortgage = norm(data.get("mortgage"))
    alimony = norm(data.get("alimony"))
    income = norm(data.get("income"))
    property_ = norm(data.get("property"))

    score = 0

    if "более 500" in debt:

        score += 200
    elif "менее 500" in debt:
        score += 120

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

    if property_ == "нет":
        score += 100
    elif property_ == "да":
        score += 60

    score = max(0, min(score, 1000))

    print(f"   📊 SCORE={score}")
    return score


def get_segment(score: int) -> str:
    """
    Сегментация LTV-лида.
    Учитывает динамические начисления.
    """

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

def analyze_comments(comments: str) -> dict:
    """
    Главная функция анализа комментариев.
    Определяет тип и проверяет условия квалификации.
    """
    comment_type = detect_comment_type(comments)

    if comment_type == 'quiz_questions':
        return check_quiz_questions(comments)
    elif comment_type == 'debt_quiz':
        return check_debt_quiz(comments)
    else:
        print(f"   ⚠️ Неизвестный формат комментария")
        return {
            'qualified': False,
            'reason': 'Неизвестный формат комментария',
            'city': None,
            'debt_amount': None
        }


def mark_lead(lead_id: str, qualified: bool, city: str = None,
              debt: float = None, result_text: str = None,
              metrika_sent: bool = False):
    fields = {
        FIELD_GPT_QUALIFIED: True if qualified else False,
        FIELD_METRIKA_SENT: True if metrika_sent else False,
        FIELD_GPT_CITY: city or '',
        FIELD_GPT_DEBT: str(debt) if debt else '',
        FIELD_GPT_RESULT: result_text or ''
    }
    result = update_lead(lead_id, fields)
    if result:
        print(f"   💾 Лид {lead_id} обновлён в Б24")
    else:
        print(f"   ❌ Ошибка обновления лида {lead_id}")

def process_lead(lead: dict) -> str:
    lead_id = lead.get("ID")
    status_id = lead.get("STATUS_ID")

    print(f"\n{'=' * 60}")
    print(f"📋 Лид ID={lead_id} | Статус={status_id}")

    ym_uid = parse_ym_uid(lead)
    phone = get_phone(lead)

    # ------------------------------------------------------------
    # ✅ 1. БАЗОВЫЙ СКОРИНГ (если ещё не отправляли)
    # ------------------------------------------------------------

    lead_sent_flag = str(lead.get(FIELD_LEAD_SENT)).lower() in ("1", "true", "y")

    comments = lead.get("COMMENTS", "")
    answers = extract_quiz_answers(comments)

    if answers and not lead_sent_flag:

        metrika_cfg = get_metrika_config(lead)
        if not metrika_cfg:
            print("⏭ Нет маппинга UTM — пропуск")
            return "no_utm"

        # ✅ STOP-факторы
        if check_stop_factors(answers, lead):
            if ym_uid or phone:
                send_conversion(
                    counter_id=metrika_cfg["counter_id"],
                    token=metrika_cfg["token"],
                    client_id=ym_uid,
                    phone=phone,
                    goal_name="lead",
                    revenue=0
                )

            update_lead(lead_id, {
                FIELD_LEAD_SENT: True,
                FIELD_SCORE: 0,
                FIELD_LOG: "STOP-фактор"
            })

            print("🔴 STOP отправлен как 0. Больше не пересчитывается.")
            return "sent"

        # ✅ Базовый скоринг 0–1000
        base_score = calculate_score(answers)

        if ym_uid or phone:
            send_conversion(
                counter_id=metrika_cfg["counter_id"],
                token=metrika_cfg["token"],
                client_id=ym_uid,
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

    # ------------------------------------------------------------
    # ✅ 2. ДИНАМИЧЕСКИЕ СОБЫТИЯ (каждый запуск)
    # ------------------------------------------------------------

    lead_sent_flag = str(lead.get(FIELD_LEAD_SENT)).lower() in ("1", "true", "y")

    if lead_sent_flag:

        # если score = 0 (стоп) — больше не трогаем
        if int(lead.get(FIELD_SCORE) or 0) == 0:
            print("⛔ STOP-лид. Дальнейшая проверка отключена.")
            return "sent"

        process_dynamic_events(lead)

    # ------------------------------------------------------------
    # ✅ 3. SOURCE_ID = 7 (case_lead)
    # ------------------------------------------------------------

    source_id = str(lead.get("SOURCE_ID") or "").strip()

    if source_id == "7":

        if not ym_uid:
            print("⏭ SOURCE_ID=7 но нет ym_uid")
            return "no_ymuid"

        sent = send_conversion(
            counter_id="103733006",
            token="y0__wgBEJKIlYkIGND1QyDY8u39F4F5gozY3hR9fDx2dqodPhjfbKkN",
            client_id=ym_uid,
            phone=phone,
            goal_name="case_lead"
        )

        mark_lead(
            lead_id,
            qualified=True,
            result_text="Отправлен как case_lead (SOURCE_ID=7)",
            metrika_sent=sent
        )

        return "sent" if sent else "metrika_error"

    # ------------------------------------------------------------
    # ✅ 4. СТАРАЯ ЛОГИКА КВАЛИФИКАЦИИ (ЭТАП 2)
    # ------------------------------------------------------------

    metrika_cfg = get_metrika_config(lead)
    if not metrika_cfg:
        return "no_utm"

    if not ym_uid:
        return "no_ymuid"

    if status_id in QUALIFIED_STATUSES:

        sent = send_conversion(
            counter_id=metrika_cfg["counter_id"],
            token=metrika_cfg["token"],
            client_id=ym_uid,
            phone=phone
        )

        mark_lead(
            lead_id,
            qualified=True,
            result_text=f"Квалифицирован по статусу: {status_id}",
            metrika_sent=sent
        )

        return "sent" if sent else "metrika_error"

    comment_type = detect_comment_type(comments)

    if comment_type:
        analysis = analyze_comments(comments)

        if analysis["qualified"]:

            sent = send_conversion(
                counter_id=metrika_cfg["counter_id"],
                token=metrika_cfg["token"],
                client_id=ym_uid,
                phone=phone
            )

            mark_lead(
                lead_id,
                qualified=True,
                city=analysis.get("city"),
                debt=analysis.get("debt_amount"),
                result_text=f"Квалиф. по комментарию",
                metrika_sent=sent
            )

            return "sent" if sent else "metrika_error"

    return "not_qualified"