def get_unprocessed_leads() -> list:
    """Лиды за 21 день которые не обработаны"""
    date_from = (datetime.now() - timedelta(days=21)).strftime("%Y-%m-%d")

    leads  = []
    start  = 0

    while True:
        data = b24_request("crm.lead.list", {
            "filter": {
                ">=DATE_CREATE": date_from,
                "UF_CRM_LEAD_METRIKA_SENT": False
            },
            "select": [
                "ID", "TITLE", "STATUS_ID",
                "COMMENTS", "PHONE", "EMAIL",
                "DATE_CREATE",
                # UTM поля
                "UTM_SOURCE",
                "UTM_MEDIUM",
                "UTM_CAMPAIGN",   # ← номер компании здесь
                "UTM_CONTENT",
                "UTM_TERM",
                "UF_CRM_LEAD_METRIKA_SENT",
                "UF_CRM_LEAD_GPT_QUALIFIED"
            ],
            "order": {"DATE_CREATE": "DESC"},
            "start": start
        })

        result = data.get('result', [])
        if not result:
            break

        leads.extend(result)
        print(f"   Загружено лидов: {len(leads)}")

        if len(result) < 50:
            break

        start += 50
        time.sleep(0.5)

    return leads