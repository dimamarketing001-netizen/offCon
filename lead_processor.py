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

    # 🔴 STOP
    if exec_proc == "да":
        print("   🔴 STOP-ФАКТОР")
        return 50

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
    if score >= 900:
        return "Премиум"
    elif score >= 800:
        return "Сильный"
    elif score >= 600:
        return "Средний"
    elif score >= 100:
        return "Слабый"
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
    lead_id = lead.get('ID')
    status_id = lead.get('STATUS_ID')

    comments = lead.get("COMMENTS", "")
    answers = extract_quiz_answers(comments)

    lead_sent_flag = str(lead.get(FIELD_LEAD_SENT)).lower() in ("1", "true", "y")

    if answers and not lead_sent_flag:
        metrika_cfg = get_metrika_config(lead)
        if not metrika_cfg:
            print("   ⏭️ Нет маппинга для UTM — lead не отправляем")
        else:
            ym_uid = parse_ym_uid(lead)
            phone = get_phone(lead)

            if ym_uid or phone:

                score = calculate_score(answers)
                segment = get_segment(score)

                print(f"   🏷 Сегмент: {segment}")

                sent = send_conversion(
                    counter_id=metrika_cfg["counter_id"],
                    token=metrika_cfg["token"],
                    client_id=ym_uid,
                    phone=phone,
                    goal_name="lead",
                    revenue=score
                )

                if sent:
                    update_lead(lead_id, {
                        FIELD_LEAD_SENT: True,
                        "UF_CRM_1784809635845": segment
                    })

    # ✅ СПЕЦУСЛОВИЕ: SOURCE_ID = 7 → отправляем сразу в отдельный счётчик
    source_id = str(lead.get('SOURCE_ID') or '').strip()
    ym_uid = parse_ym_uid(lead)
    phone = get_phone(lead)

    if source_id == '7':
        print(f"   🚀 SOURCE_ID=7 → отправляем как case_lead (отдельный счётчик)")
        print(f"   _ym_uid: {ym_uid or '❌'} | Телефон: {phone or '❌'}")

        if not ym_uid:
            print(f"   ⏭️ Нет _ym_uid — пропускаем")
            mark_lead(
                lead_id,
                qualified=False,
                result_text="SOURCE_ID=7, но нет _ym_uid"
            )
            return 'no_ymuid'

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

        return 'sent' if sent else 'metrika_error'

    print(f"\n{'=' * 55}")
    print(f"📋 Лид ID={lead_id} | Статус={status_id}")
    print(f"   UTM_CAMPAIGN: {lead.get('UTM_CAMPAIGN') or '❌ нет'}")

    # 1. Проверяем UTM_CAMPAIGN
    metrika_cfg = get_metrika_config(lead)
    if not metrika_cfg:
        mark_lead(lead_id, qualified=False,
                  result_text="Пропущен: нет UTM_CAMPAIGN в маппинге")
        return 'no_utm'

    # 2. Проверяем _ym_uid
    ym_uid = parse_ym_uid(lead)
    phone = get_phone(lead)

    print(f"   _ym_uid: {ym_uid or '❌'} | Телефон: {phone or '❌'}")

    if not ym_uid:
        print(f"   ⏭️ Нет _ym_uid — пропускаем")
        mark_lead(lead_id, qualified=False,
                  result_text="Пропущен: нет _ym_uid")
        return 'no_ymuid'

    # 3. Статус уже квалифицирован — сразу в Метрику
    if status_id in QUALIFIED_STATUSES:
        print(f"   ✅ Статус квалифицирован: {status_id}")
        sent = send_conversion(
            counter_id=metrika_cfg['counter_id'],
            token=metrika_cfg['token'],
            client_id=ym_uid,
            phone=phone
        )
        mark_lead(lead_id, qualified=True,
                  result_text=f"Квалифицирован по статусу: {status_id}",
                  metrika_sent=sent)
        return 'sent' if sent else 'metrika_error'

    # 4. Анализируем комментарий
    comment_type = detect_comment_type(comments)
    if not comment_type:
        print(f"   ⏭️ Комментарий не содержит данных для анализа")
        mark_lead(lead_id, qualified=False,
                  result_text="Пропущен: неизвестный формат комментария")
        return 'no_calls'  # используем тот же статус для "нечего анализировать"

    print(f"   🔍 Анализируем комментарий (тип: {comment_type})...")
    analysis = analyze_comments(comments)

    if analysis['qualified']:
        city = analysis.get('city')
        debt = analysis.get('debt_amount')

        print(f"   ✅ КВАЛИФИЦИРОВАН! Город={city}, Долг={debt}")
        print(f"   Причина: {analysis['reason']}")

        sent = send_conversion(
            counter_id=metrika_cfg['counter_id'],
            token=metrika_cfg['token'],
            client_id=ym_uid,
            phone=phone
        )
        mark_lead(
            lead_id, qualified=True,
            city=city, debt=debt,
            result_text=f"Квалиф. по комментарию ({comment_type}): {analysis['reason']}",
            metrika_sent=sent
        )
        return 'sent' if sent else 'metrika_error'

    # Не квалифицирован
    print(f"   ❌ Не квалифицирован: {analysis['reason']}")
    mark_lead(lead_id, qualified=False,
              result_text=f"Не квалиф: {analysis['reason']}")
    return 'not_qualified'