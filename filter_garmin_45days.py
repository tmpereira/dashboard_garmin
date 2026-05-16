"""
filter_garmin_45days.py
-----------------------
Lê garmin_data.json e salva somente os dados dos últimos 45 dias
em garmin_data_45.json.

Uso:
    python filter_garmin_45days.py
    python filter_garmin_45days.py --input garmin_data.json --output garmin_data_45.json --days 45
"""

import argparse
import json
from datetime import date, datetime, timedelta


def parse_date(value) -> date | None:
    """Tenta extrair uma data de uma string ISO ou timestamp."""
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(value).date()
        except Exception:
            return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(str(value)[:26], fmt).date()
        except ValueError:
            continue
    return None


def in_range(value, cutoff: date) -> bool:
    d = parse_date(value)
    return d is not None and d >= cutoff


# Mapeamento: chave -> campo de data usado para filtrar
DATE_FIELDS = {
    "activities":         ["startTimeLocal", "startTimeGMT"],
    "activity_details":   None,   # filtrado pelo activityId cruzado com activities
    "sleep":              ["dailySleepDTO.calendarDate", "calendarDate"],
    "steps":              ["date"],
    "heart_rates":        ["dateTime", "calendarDate"],
    "stress":             ["calendarDate", "startTimestampGMT"],
    "spo2":               ["calendarDate"],
    "respiration":        ["startTimestampGMT", "calendarDate"],
    "body_battery":       ["date", "calendarDate"],
    "hydration":          ["calendarDate"],
    "daily_weigh_ins":    ["calendarDate", "date"],
    "intensity_minutes":  ["calendarDate", "startDate"],
    "hrv":                ["calendarDate", "startTimestampGMT"],
    "rhr":                ["calendarDate", "statisticsStartDate"],
    "all_day_stress":     ["calendarDate"],
    "floors":             ["calendarDate", "startTimestampGMT"],
    "daily_steps_range":  ["calendarDate", "startDate"],
    "movement":           ["calendarDate"],
}


def get_nested(obj: dict, dotted_key: str):
    """Acessa chave aninhada com notação 'pai.filho'."""
    parts = dotted_key.split(".")
    for p in parts:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(p)
    return obj


def filter_list(items: list, date_fields: list, cutoff: date) -> list:
    """Filtra uma lista mantendo apenas itens dentro do intervalo."""
    result = []
    for item in items:
        if not isinstance(item, dict):
            result.append(item)
            continue
        for field in date_fields:
            val = get_nested(item, field)
            if val is not None:
                if in_range(val, cutoff):
                    result.append(item)
                break
        else:
            # Sem campo de data reconhecível → mantém
            result.append(item)
    return result


def filter_data(data: dict, cutoff: date) -> dict:
    filtered = {}

    # Campos que não são listas (perfil, dispositivos, etc.) → copia direto
    non_list_keys = {
        "profile", "unit_system", "stats", "user_summary",
        "max_metrics", "training_readiness", "training_status",
        "race_predictions", "fitnessage_data", "weekly_intensity",
        "weekly_steps", "weigh_ins", "goals", "devices",
        "device_settings", "_meta",
    }
    for key in non_list_keys:
        if key in data:
            filtered[key] = data[key]

    # Filtra atividades e guarda IDs válidos para cruzar com activity_details
    activities_raw = data.get("activities", [])
    fields = DATE_FIELDS["activities"]
    filtered_activities = filter_list(activities_raw, fields, cutoff)
    filtered["activities"] = filtered_activities
    valid_ids = {a.get("activityId") for a in filtered_activities}

    # activity_details: filtra pelos IDs das atividades dentro do período
    details_raw = data.get("activity_details", [])
    filtered["activity_details"] = [
        d for d in details_raw if d.get("activityId") in valid_ids
    ]

    # Demais listas
    for key, date_fields in DATE_FIELDS.items():
        if key in ("activities", "activity_details") or date_fields is None:
            continue
        raw = data.get(key, [])
        if isinstance(raw, list):
            filtered[key] = filter_list(raw, date_fields, cutoff)
        else:
            filtered[key] = raw

    return filtered


def main():
    parser = argparse.ArgumentParser(
        description="Filtra garmin_data.json pelos últimos N dias."
    )
    parser.add_argument("--input",  default="garmin_data.json",    help="Arquivo JSON de entrada")
    parser.add_argument("--output", default="garmin_data_45.json", help="Arquivo JSON de saída")
    parser.add_argument("--days",   type=int, default=45,          help="Número de dias (padrão: 45)")
    args = parser.parse_args()

    cutoff = date.today() - timedelta(days=args.days)
    print(f"Lendo '{args.input}'...")

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Filtrando dados a partir de {cutoff.isoformat()} (últimos {args.days} dias)...")
    filtered = filter_data(data, cutoff)

    # Atualiza metadados
    if "_meta" in filtered:
        filtered["_meta"]["filtered_at"] = datetime.now().isoformat()
        filtered["_meta"]["filter_cutoff"] = cutoff.isoformat()
        filtered["_meta"]["filter_days"] = args.days

    print(f"Salvando em '{args.output}'...")
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)

    # Resumo
    print("\nResumo:")
    for key in ("activities", "sleep", "steps", "heart_rates", "stress", "hrv"):
        orig = len(data.get(key, []))
        filt = len(filtered.get(key, []))
        print(f"  {key}: {orig} → {filt} registros")
    print(f"\nConcluído! Arquivo salvo: {args.output}")


if __name__ == "__main__":
    main()
