"""
garmin_export.py
----------------
Conecta no Garmin Connect e extrai o máximo de informações disponíveis,
salvando tudo em um arquivo JSON.

Uso:
    python garmin_export.py --email seu@email.com --password suasenha
    python garmin_export.py --email seu@email.com --password suasenha --days 90
    python garmin_export.py --email seu@email.com --password suasenha --output meus_dados.json
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from getpass import getpass

from garminconnect import Garmin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def json_serial(obj):
    """Serializador JSON para tipos não padrão (date, datetime)."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Tipo não serializável: {type(obj)}")


def safe(func, *args, label="", **kwargs):
    """Chama func com args/kwargs e retorna None em caso de erro."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        log.warning(f"  [{label}] Falha: {e}")
        return None


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------

def extract_all(client: Garmin, start_str: str, end_str: str) -> dict:
    today = date.today()
    start = date.fromisoformat(start_str)
    end = date.fromisoformat(end_str)
    days = (end - start).days + 1

    data = {}

    # --- Perfil do usuário ---
    log.info("Extraindo perfil do usuário...")
    data["profile"] = safe(client.get_full_name, label="profile")
    data["unit_system"] = safe(client.get_unit_system, label="unit_system")
    data["stats"] = safe(client.get_stats, today.isoformat(), label="stats")
    data["user_summary"] = safe(client.get_user_summary, today.isoformat(), label="user_summary")

    # --- Atividades ---
    log.info("Extraindo atividades de %s até %s (%d dias)...", start_str, end_str, days)
    activities = safe(client.get_activities_by_date, start_str, end_str, label="activities") or []
    data["activities"] = activities
    log.info("  %d atividades encontradas.", len(activities))

    # Detalhes de cada atividade
    log.info("Extraindo detalhes de cada atividade...")
    activity_details = []
    for i, act in enumerate(activities, 1):
        act_id = act.get("activityId")
        log.info("  [%d/%d] activityId=%s", i, len(activities), act_id)
        detail = {
            "activityId": act_id,
            "details": safe(client.get_activity_details, act_id, label=f"details/{act_id}"),
            "splits": safe(client.get_activity_splits, act_id, label=f"splits/{act_id}"),
            "split_summaries": safe(client.get_activity_split_summaries, act_id, label=f"split_summaries/{act_id}"),
            "weather": safe(client.get_activity_weather, act_id, label=f"weather/{act_id}"),
            "hr_timeseries": safe(client.get_activity_hr_in_timezones, act_id, label=f"hr_timezones/{act_id}"),
            "exercise_sets": safe(client.get_activity_exercise_sets, act_id, label=f"exercise_sets/{act_id}"),
        }
        activity_details.append(detail)
    data["activity_details"] = activity_details

    # --- Sono ---
    log.info("Extraindo dados de sono...")
    sleep_data = []
    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()
        result = safe(client.get_sleep_data, d, label=f"sleep/{d}")
        if result:
            sleep_data.append(result)
    data["sleep"] = sleep_data

    # --- Passos / Steps ---
    log.info("Extraindo passos diários...")
    steps_data = []
    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()
        result = safe(client.get_steps_data, d, label=f"steps/{d}")
        if result:
            steps_data.append({"date": d, "steps": result})
    data["steps"] = steps_data

    # --- Frequência cardíaca ---
    log.info("Extraindo frequência cardíaca...")
    hr_data = []
    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()
        result = safe(client.get_heart_rates, d, label=f"hr/{d}")
        if result:
            hr_data.append(result)
    data["heart_rates"] = hr_data

    # --- Estresse ---
    log.info("Extraindo dados de estresse...")
    stress_data = []
    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()
        result = safe(client.get_stress_data, d, label=f"stress/{d}")
        if result:
            stress_data.append(result)
    data["stress"] = stress_data

    # --- SpO2 ---
    log.info("Extraindo SpO2...")
    spo2_data = []
    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()
        result = safe(client.get_spo2_data, d, label=f"spo2/{d}")
        if result:
            spo2_data.append(result)
    data["spo2"] = spo2_data

    # --- Respiração ---
    log.info("Extraindo dados de respiração...")
    respiration_data = []
    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()
        result = safe(client.get_respiration_data, d, label=f"respiration/{d}")
        if result:
            respiration_data.append(result)
    data["respiration"] = respiration_data

    # --- Body Battery ---
    log.info("Extraindo Body Battery...")
    body_battery = []
    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()
        result = safe(client.get_body_battery, d, label=f"body_battery/{d}")
        if result:
            body_battery.append(result)
    data["body_battery"] = body_battery

    # --- Hidratação ---
    log.info("Extraindo hidratação...")
    hydration_data = []
    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()
        result = safe(client.get_hydration_data, d, label=f"hydration/{d}")
        if result:
            hydration_data.append(result)
    data["hydration"] = hydration_data

    # --- Peso / Composição corporal ---
    log.info("Extraindo peso e composição corporal...")
    data["weigh_ins"] = safe(
        client.get_weigh_ins, start_str, end_str, label="weigh_ins"
    )
    daily_weigh_ins = []
    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()
        result = safe(client.get_daily_weigh_ins, d, label=f"daily_weigh_ins/{d}")
        if result:
            daily_weigh_ins.append(result)
    data["daily_weigh_ins"] = daily_weigh_ins

    # --- Dados de fitness / capacidade ---
    log.info("Extraindo dados de fitness...")
    data["max_metrics"] = safe(client.get_max_metrics, today.isoformat(), label="max_metrics")
    data["training_readiness"] = safe(
        client.get_training_readiness, today.isoformat(), label="training_readiness"
    )
    data["training_status"] = safe(
        client.get_training_status, today.isoformat(), label="training_status"
    )
    data["race_predictions"] = safe(
        client.get_race_predictions, label="race_predictions"
    )
    data["fitnessage_data"] = safe(
        client.get_fitnessage_data, today.isoformat(), label="fitnessage_data"
    )

    # --- Períodos de intensidade e carga de treino ---
    log.info("Extraindo intensidade e carga de treino...")
    intensity_data = []
    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()
        result = safe(client.get_intensity_minutes_data, d, label=f"intensity_minutes/{d}")
        if result:
            intensity_data.append(result)
    data["intensity_minutes"] = intensity_data
    data["weekly_intensity"] = safe(
        client.get_weekly_intensity_minutes, start_str, end_str, label="weekly_intensity"
    )

    # --- HRV ---
    log.info("Extraindo HRV...")
    hrv_data = []
    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()
        result = safe(client.get_hrv_data, d, label=f"hrv/{d}")
        if result:
            hrv_data.append(result)
    data["hrv"] = hrv_data

    # --- FC em repouso (RHR) ---
    log.info("Extraindo FC em repouso...")
    rhr_data = []
    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()
        result = safe(client.get_rhr_day, d, label=f"rhr/{d}")
        if result:
            rhr_data.append(result)
    data["rhr"] = rhr_data

    # --- Estresse dia todo ---
    log.info("Extraindo estresse diário completo...")
    all_day_stress = []
    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()
        result = safe(client.get_all_day_stress, d, label=f"all_day_stress/{d}")
        if result:
            all_day_stress.append(result)
    data["all_day_stress"] = all_day_stress

    # --- Passos diários (range) e semanais ---
    log.info("Extraindo passos (range e semanal)...")
    data["daily_steps_range"] = safe(client.get_daily_steps, start_str, end_str, label="daily_steps_range")
    data["weekly_steps"] = safe(client.get_weekly_steps, end_str, label="weekly_steps")

    # --- Andares subidos ---
    log.info("Extraindo andares subidos...")
    floors_data = []
    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()
        result = safe(client.get_floors, d, label=f"floors/{d}")
        if result:
            floors_data.append(result)
    data["floors"] = floors_data

    # --- Metas ---
    log.info("Extraindo metas...")
    data["goals"] = safe(client.get_goals, label="goals")

    # --- Dispositivos ---
    log.info("Extraindo dispositivos registrados...")
    data["devices"] = safe(client.get_devices, label="devices")
    data["device_settings"] = []
    devices = data.get("devices") or []
    for dev in devices:
        dev_id = dev.get("deviceId")
        if dev_id:
            settings = safe(client.get_device_settings, dev_id, label=f"device_settings/{dev_id}")
            if settings:
                data["device_settings"].append({"deviceId": dev_id, "settings": settings})

    # Metadados da extração
    data["_meta"] = {
        "extracted_at": datetime.now().isoformat(),
        "period_start": start_str,
        "period_end": end_str,
        "days_total": days,
    }

    return data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Exporta todos os dados do Garmin Connect para JSON."
    )
    parser.add_argument("--email", help="E-mail do Garmin Connect")
    parser.add_argument("--password", help="Senha do Garmin Connect")
    parser.add_argument(
        "--start",
        default="2026-01-01",
        help="Data de início no formato YYYY-MM-DD (padrão: 2026-01-01)",
    )
    parser.add_argument(
        "--end",
        default=date.today().isoformat(),
        help="Data de fim no formato YYYY-MM-DD (padrão: hoje)",
    )
    parser.add_argument(
        "--output",
        default="garmin_data.json",
        help="Arquivo JSON de saída (padrão: garmin_data.json)",
    )
    args = parser.parse_args()

    DEFAULT_EMAIL = "thiagomartinipereira@gmail.com"
    DEFAULT_PASSWORD = "Fof@1977"

    email = args.email or os.environ.get("GARMIN_EMAIL") or DEFAULT_EMAIL
    password = args.password or os.environ.get("GARMIN_PASSWORD") or DEFAULT_PASSWORD

    if not email or not password:
        log.error("E-mail e senha são obrigatórios.")
        sys.exit(1)

    log.info("Autenticando no Garmin Connect...")
    try:
        client = Garmin(email, password)
        client.login()
        log.info("Autenticado com sucesso.")
    except Exception as e:
        log.error("Falha na autenticação: %s", e)
        sys.exit(1)

    log.info("Iniciando extração de %s até %s...", args.start, args.end)
    data = extract_all(client, args.start, args.end)

    log.info("Salvando dados em '%s'...", args.output)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=json_serial)

    log.info("Concluído! Arquivo salvo: %s", os.path.abspath(args.output))

    # ── Upload para Supabase Storage (opcional, via variáveis de ambiente) ──
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if supabase_url and supabase_key:
        try:
            import httpx
            with open(args.output, "rb") as f:
                content = f.read()
            headers = {
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "x-upsert": "true",
            }
            upload_url = f"{supabase_url}/storage/v1/object/garmin/garmin_data.json"
            resp = httpx.put(upload_url, content=content, headers=headers, timeout=300)
            if resp.status_code in (200, 201):
                log.info("Upload para Supabase Storage concluído.")
            else:
                log.warning("Supabase retornou %s: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            log.warning("Falha no upload para Supabase: %s", e)
    else:
        log.info("SUPABASE_URL/SUPABASE_SERVICE_KEY não definidos — upload ignorado.")


if __name__ == "__main__":
    main()
