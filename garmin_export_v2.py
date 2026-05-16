"""
garmin_export_v2.py
-------------------
Exporta dados do Garmin Connect em formato compacto e pré-calculado.
O JSON gerado é leve (~1-5 MB) e contém todos os cálculos prontos para
o frontend Vue consumir diretamente, sem processamento adicional.

Uso:
    python garmin_export_v2.py
    python garmin_export_v2.py --start 2026-01-01 --end 2026-05-16
    python garmin_export_v2.py --output garmin_data.json
"""

import argparse
import json
import logging
import math
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean

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
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Tipo não serializável: {type(obj)}")


def safe(func, *args, label="", **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        log.warning("  [%s] Falha: %s", label, e)
        return None


# ---------------------------------------------------------------------------
# Processamento de séries diárias
# ---------------------------------------------------------------------------

def process_sleep(sleep_records):
    """Converte registros brutos de sono em resumos diários (horas)."""
    daily = []
    for rec in (sleep_records or []):
        dto = rec.get("dailySleepDTO") or {}
        cal_date = dto.get("calendarDate") or rec.get("calendarDate")
        if not cal_date:
            continue
        deep  = dto.get("deepSleepSeconds") or 0
        light = dto.get("lightSleepSeconds") or 0
        rem   = dto.get("remSleepSeconds") or 0
        awake = dto.get("awakeSleepSeconds") or 0
        total = dto.get("sleepTimeSeconds") or (deep + light + rem)
        if total > 0:
            daily.append({
                "date":    cal_date,
                "total_h": round(total / 3600, 2),
                "deep_h":  round(deep  / 3600, 2),
                "light_h": round(light / 3600, 2),
                "rem_h":   round(rem   / 3600, 2),
                "awake_h": round(awake / 3600, 2),
            })

    daily.sort(key=lambda x: x["date"])

    avg = {}
    if daily:
        for k in ("total_h", "deep_h", "light_h", "rem_h", "awake_h"):
            vals = [d[k] for d in daily if d[k] > 0]
            avg[k] = round(mean(vals), 2) if vals else 0.0

    return daily, avg


def process_heart_rates(hr_records):
    """Resumo diário de FC (min, repouso, máx)."""
    daily = []
    for rec in (hr_records or []):
        cal_date = rec.get("calendarDate")
        max_hr   = rec.get("maxHeartRate")
        resting  = rec.get("restingHeartRate")
        min_hr   = rec.get("minHeartRate")
        if cal_date and max_hr:
            daily.append({"date": cal_date, "max": max_hr, "resting": resting, "min": min_hr})
    daily.sort(key=lambda x: x["date"])
    return daily


def process_hrv(hrv_records):
    """Resumo diário de HRV."""
    daily = []
    for rec in (hrv_records or []):
        summary = rec.get("hrvSummary") or {}
        cal_date    = summary.get("calendarDate")
        last_night  = summary.get("lastNightAvg")
        weekly      = summary.get("weeklyAvg")
        if cal_date and last_night:
            daily.append({"date": cal_date, "last_night_avg": last_night, "weekly_avg": weekly})
    daily.sort(key=lambda x: x["date"])
    return daily


def process_steps_daily(daily_steps_range):
    """Passos diários: {'date', 'steps'}."""
    result = []
    for rec in (daily_steps_range or []):
        cal_date = rec.get("calendarDate")
        steps    = rec.get("steps") or rec.get("totalSteps") or 0
        if cal_date:
            result.append({"date": cal_date, "steps": int(steps)})
    result.sort(key=lambda x: x["date"])
    return result


def process_steps_weekly(weekly_steps):
    """Passos semanais: {'date', 'total_steps'}."""
    result = []
    for rec in (weekly_steps or []):
        cal_date = rec.get("calendarDate")
        vals     = rec.get("values") or rec
        total    = (vals.get("totalSteps") if isinstance(vals, dict) else None) or rec.get("totalSteps") or 0
        if cal_date:
            result.append({"date": cal_date, "total_steps": int(total)})
    result.sort(key=lambda x: x["date"])
    return result


def process_intensity_weekly(weekly_intensity):
    """Minutos de intensidade semanais: {'date', 'moderate_min', 'vigorous_min'}."""
    result = []
    for rec in (weekly_intensity or []):
        cal_date = rec.get("calendarDate")
        moderate = rec.get("moderateValue") or rec.get("moderateIntensityMinutes") or 0
        vigorous = rec.get("vigorousValue") or rec.get("vigorousIntensityMinutes") or 0
        if cal_date:
            result.append({"date": cal_date, "moderate_min": int(moderate), "vigorous_min": int(vigorous)})
    result.sort(key=lambda x: x["date"])
    return result


def process_stress_body_battery(stress_records, body_battery_records):
    """Merge stress + body battery em resumos diários: {'date', 'avg_stress', 'body_battery_max'}."""
    bb_map = {}
    for rec in (body_battery_records or []):
        items = rec if isinstance(rec, list) else [rec]
        for item in items:
            d = str(item.get("date") or item.get("calendarDate") or "")[:10]
            val = item.get("charged") or item.get("bodyBatteryMostRecentValue")
            vals_arr = item.get("bodyBatteryValuesArray") or []
            if vals_arr:
                nums = [v[1] for v in vals_arr if isinstance(v, (list, tuple)) and len(v) > 1 and v[1] is not None]
                if nums:
                    val = max(nums)
            if d and val is not None:
                bb_map[d] = max(bb_map.get(d, 0), int(val))

    stress_map = {}
    for rec in (stress_records or []):
        cal_date = str(rec.get("calendarDate") or "")[:10]
        level    = rec.get("overallStressLevel") or rec.get("avgStressLevel")
        if cal_date and level is not None:
            stress_map[cal_date] = int(level)

    all_dates = sorted(set(list(stress_map) + list(bb_map)))
    return [{"date": d, "avg_stress": stress_map.get(d), "body_battery_max": bb_map.get(d)} for d in all_dates]


def process_activities(raw_activities):
    """Retorna lista de atividades com apenas os campos necessários para o dashboard."""
    result = []
    for act in (raw_activities or []):
        type_obj = act.get("activityType") or {}
        type_key = (type_obj.get("typeKey") if isinstance(type_obj, dict) else str(type_obj)) or ""
        act_date = (act.get("startTimeLocal") or act.get("startTimeGMT") or "")[:10]
        result.append({
            "id":              act.get("activityId"),
            "date":            act_date,
            "name":            act.get("activityName") or "",
            "type":            type_key,
            "distance_m":      round(act.get("distance") or 0, 1),
            "duration_s":      round(act.get("duration") or 0),
            "avg_hr":          act.get("averageHR") or act.get("avgHr") or 0,
            "max_hr":          act.get("maxHR") or 0,
            "calories":        act.get("calories") or 0,
            "elevation_gain":  round(act.get("elevationGain") or 0),
            "avg_speed_ms":    round(act.get("averageSpeed") or act.get("avgSpeed") or 0, 4),
            "cadence":         act.get("averageRunningCadenceInStepsPerMinute") or 0,
            "training_effect": act.get("aerobicTrainingEffect") or 0,
            "location":        act.get("locationName") or "",
        })
    result.sort(key=lambda x: x["date"])
    return result


# ---------------------------------------------------------------------------
# Cálculos derivados (PMC, pace, EF, correlação)
# ---------------------------------------------------------------------------

FC_MAX_REF = 190

TYPE_FACTORS = {
    "running":           1.0,
    "trail_running":     1.0,
    "cycling":           0.85,
    "swimming":          0.90,
    "strength_training": 0.65,
    "walking":           0.50,
}


def trimp_value(act):
    dur_min = (act.get("duration_s") or 0) / 60
    avg_hr  = act.get("avg_hr") or (FC_MAX_REF * 0.7)
    hr_ratio = min(avg_hr / FC_MAX_REF, 1.0)
    type_key = (act.get("type") or "").lower()
    factor = 0.5
    for k, v in TYPE_FACTORS.items():
        if k in type_key:
            factor = v
            break
    return dur_min * hr_ratio * factor


def calc_pmc(activities, hrv_daily, sleep_daily, stress_daily):
    """Calcula CTL/ATL/TSB (PMC) e score de Prontidão."""
    empty = {
        "ctl": 0, "atl": 0, "tsb": 0, "trimp_7d": 0, "activities_7d": 0,
        "readiness": 0, "training_status": "–", "acute_load_label": "–",
        "hrv_score": 0, "sleep_score": 0, "body_battery_score": 0, "tsb_score": 0,
        "history": [],
    }
    if not activities:
        return empty

    trimp_by_date = defaultdict(float)
    for act in activities:
        d = act.get("date")
        if d:
            trimp_by_date[d] += trimp_value(act)

    all_dates = sorted(trimp_by_date)
    if not all_dates:
        return empty

    CTL_ALPHA = 2 / (42 + 1)
    ATL_ALPHA = 2 / (7 + 1)

    ctl = atl = 0.0
    history = []
    current = date.fromisoformat(all_dates[0])
    today   = date.today()

    while current <= today:
        d_str = current.isoformat()
        t = trimp_by_date.get(d_str, 0.0)
        ctl = ctl + CTL_ALPHA * (t - ctl)
        atl = atl + ATL_ALPHA * (t - atl)
        history.append({"date": d_str, "ctl": round(ctl, 1), "atl": round(atl, 1), "tsb": round(ctl - atl, 1)})
        current += timedelta(days=1)

    current_ctl = round(ctl, 1)
    current_atl = round(atl, 1)
    current_tsb = round(ctl - atl, 1)

    cutoff_7d = (today - timedelta(days=7)).isoformat()
    trimp_7d = sum(v for d_str, v in trimp_by_date.items() if d_str >= cutoff_7d)
    acts_7d  = sum(1 for a in activities if (a.get("date") or "") >= cutoff_7d)

    # HRV score (0–100)
    hrv_score = 0
    if hrv_daily:
        latest = sorted(hrv_daily, key=lambda x: x["date"])[-1]
        val = latest.get("last_night_avg") or 0
        if val:
            low, high = 30, 80
            if val >= high:
                hrv_score = 100
            elif val >= low:
                hrv_score = int(50 + (val - low) / (high - low) * 50)
            else:
                hrv_score = int(max(0, val / low * 50))

    # Sleep score
    sleep_score = 0
    if sleep_daily:
        last = sorted(sleep_daily, key=lambda x: x["date"])[-1]
        h = last.get("total_h") or 0
        if h:
            if 7 <= h <= 9:      sleep_score = 100
            elif h > 9:          sleep_score = max(70, int(100 - (h - 9) * 10))
            elif h >= 5:         sleep_score = int(20 + (h - 5) / 2 * 80)
            else:                sleep_score = 20

    # Body Battery score
    bb_score = 0
    if stress_daily:
        last_bb = sorted([s for s in stress_daily if s.get("body_battery_max")], key=lambda x: x["date"])
        if last_bb:
            bb_score = min(100, int(last_bb[-1].get("body_battery_max") or 0))

    # TSB score
    if current_tsb > 15:      tsb_score = 100
    elif current_tsb > 5:     tsb_score = 90
    elif current_tsb > -10:   tsb_score = 70
    elif current_tsb > -30:   tsb_score = 50
    else:                     tsb_score = 20

    readiness = round(hrv_score * 0.40 + bb_score * 0.30 + sleep_score * 0.20 + tsb_score * 0.10)

    if current_tsb > 10:      training_status = "Descansado"
    elif current_tsb > -5:    training_status = "Produtivo"
    elif current_tsb > -15:   training_status = "Acumulando"
    elif current_tsb > -30:   training_status = "Evoluindo"
    else:                     training_status = "Sobretreinando"

    if current_atl > 80:      acute_label = "Muito Alta"
    elif current_atl > 50:    acute_label = "Alta"
    elif current_atl > 25:    acute_label = "Moderada"
    elif current_atl > 10:    acute_label = "Baixa"
    else:                     acute_label = "Muito Baixa"

    return {
        "ctl": current_ctl, "atl": current_atl, "tsb": current_tsb,
        "trimp_7d": round(trimp_7d, 1), "activities_7d": acts_7d,
        "readiness": readiness, "training_status": training_status, "acute_load_label": acute_label,
        "hrv_score": hrv_score, "sleep_score": sleep_score,
        "body_battery_score": bb_score, "tsb_score": tsb_score,
        "history": history,
    }


def calc_pace_evolution(activities):
    """Pace de corridas + média móvel de 5 corridas."""
    runs = [
        a for a in (activities or [])
        if "run" in (a.get("type") or "").lower()
        and a.get("avg_speed_ms", 0) > 0
        and a.get("distance_m", 0) >= 1000
    ]
    runs.sort(key=lambda x: x["date"])

    paces = [round(1000 / r["avg_speed_ms"]) for r in runs]
    result = []
    window = 5
    for i, run in enumerate(runs):
        win = paces[max(0, i - window + 1): i + 1]
        result.append({
            "date":         run["date"],
            "pace_sec_km":  paces[i],
            "distance_km":  round(run["distance_m"] / 1000, 2),
            "ma5":          round(mean(win), 1),
        })
    return result


def calc_ef_monthly(activities):
    """Fator de Eficiência (EF) por mês para corridas."""
    monthly = defaultdict(list)
    for act in (activities or []):
        if "run" not in (act.get("type") or "").lower():
            continue
        speed = act.get("avg_speed_ms") or 0
        hr    = act.get("avg_hr") or 0
        if speed > 0 and hr > 0:
            ef = (speed * 60) / hr
            monthly[act["date"][:7]].append(ef)

    return [
        {"month": mo, "ef": round(mean(vals), 4), "count": len(vals)}
        for mo, vals in sorted(monthly.items())
    ]


def calc_sleep_pace_correlation(activities, sleep_daily):
    """Correlação de Pearson entre sono (h) da noite anterior e pace da corrida."""
    sleep_map = {s["date"]: s.get("total_h", 0) for s in (sleep_daily or [])}
    points = []
    for act in (activities or []):
        if "run" not in (act.get("type") or "").lower():
            continue
        speed = act.get("avg_speed_ms") or 0
        if speed <= 0:
            continue
        prev = (date.fromisoformat(act["date"]) - timedelta(days=1)).isoformat()
        sleep_h = sleep_map.get(prev)
        if sleep_h and sleep_h > 0:
            points.append({
                "sleep_h":     round(sleep_h, 2),
                "pace_sec_km": round(1000 / speed),
                "dist_km":     round((act.get("distance_m") or 0) / 1000, 2),
            })

    r = None
    if len(points) >= 3:
        xs = [p["sleep_h"] for p in points]
        ys = [p["pace_sec_km"] for p in points]
        mx, my = mean(xs), mean(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        dx  = math.sqrt(sum((x - mx) ** 2 for x in xs))
        dy  = math.sqrt(sum((y - my) ** 2 for y in ys))
        if dx > 0 and dy > 0:
            r = round(num / (dx * dy), 3)

    return {"r": r, "points": points}


# ---------------------------------------------------------------------------
# Extração principal
# ---------------------------------------------------------------------------

def extract_all(client: Garmin, start_str: str, end_str: str) -> dict:
    today = date.today()
    start = date.fromisoformat(start_str)
    end   = date.fromisoformat(end_str)
    days  = (end - start).days + 1

    # --- Perfil e métricas únicas ---
    log.info("Extraindo perfil e métricas únicas...")
    profile           = safe(client.get_full_name,          label="profile")
    user_summary      = safe(client.get_user_summary,       today.isoformat(), label="user_summary")
    max_metrics       = safe(client.get_max_metrics,        today.isoformat(), label="max_metrics")
    fitnessage_data   = safe(client.get_fitnessage_data,    today.isoformat(), label="fitnessage_data")
    race_predictions  = safe(client.get_race_predictions,   label="race_predictions")

    # --- Atividades (sem detalhes/GPS) ---
    log.info("Extraindo atividades de %s até %s (%d dias)...", start_str, end_str, days)
    raw_activities = safe(client.get_activities_by_date, start_str, end_str, label="activities") or []
    log.info("  %d atividades encontradas.", len(raw_activities))

    # --- Séries diárias ---
    log.info("Extraindo séries diárias...")
    sleep_raw, hr_raw, hrv_raw, stress_raw, bb_raw = [], [], [], [], []

    for offset in range(days):
        d = (start + timedelta(days=offset)).isoformat()

        r = safe(client.get_sleep_data,             d, label=f"sleep/{d}")
        if r: sleep_raw.append(r)

        r = safe(client.get_heart_rates,            d, label=f"hr/{d}")
        if r: hr_raw.append(r)

        r = safe(client.get_hrv_data,               d, label=f"hrv/{d}")
        if r: hrv_raw.append(r)

        r = safe(client.get_stress_data,            d, label=f"stress/{d}")
        if r: stress_raw.append(r)

        r = safe(client.get_body_battery,           d, label=f"bb/{d}")
        if r: bb_raw.append(r)

    daily_steps_range = safe(client.get_daily_steps,            start_str, end_str, label="daily_steps_range")
    weekly_steps      = safe(client.get_weekly_steps,           end_str,            label="weekly_steps")
    weekly_intensity  = safe(client.get_weekly_intensity_minutes, start_str, end_str, label="weekly_intensity")

    # --- Processar séries (strip de timeseries raw) ---
    log.info("Processando séries diárias...")
    sleep_daily, sleep_avg = process_sleep(sleep_raw)
    heart_rates            = process_heart_rates(hr_raw)
    hrv_daily              = process_hrv(hrv_raw)
    steps_daily            = process_steps_daily(daily_steps_range)
    steps_weekly           = process_steps_weekly(weekly_steps)
    intensity_weekly       = process_intensity_weekly(weekly_intensity)
    stress_daily           = process_stress_body_battery(stress_raw, bb_raw)
    activities             = process_activities(raw_activities)

    # --- Cálculos derivados ---
    log.info("Calculando PMC, pace, EF, correlação sono×pace...")
    pmc                  = calc_pmc(activities, hrv_daily, sleep_daily, stress_daily)
    pace_evolution       = calc_pace_evolution(activities)
    ef_monthly           = calc_ef_monthly(activities)
    sleep_pace_corr      = calc_sleep_pace_correlation(activities, sleep_daily)

    # --- Simplificar campos de API ---
    vo2max = None
    try:
        vo2max = max_metrics[0]["generic"]["vo2MaxPreciseValue"]
    except (TypeError, IndexError, KeyError):
        pass

    fitness_age = None
    if fitnessage_data:
        fitness_age = {
            "fitness_age":          fitnessage_data.get("fitnessAge"),
            "chronological_age":    fitnessage_data.get("chronologicalAge"),
            "achievable_fitness_age": fitnessage_data.get("achievableFitnessAge"),
        }

    race_pred = None
    if race_predictions:
        race_pred = {
            "time5K":           race_predictions.get("time5K"),
            "time10K":          race_predictions.get("time10K"),
            "timeHalfMarathon": race_predictions.get("timeHalfMarathon"),
            "timeMarathon":     race_predictions.get("timeMarathon"),
        }

    return {
        "profile":          profile,
        "user_summary":     user_summary,
        "vo2max":           vo2max,
        "fitness_age":      fitness_age,
        "race_predictions": race_pred,
        "_meta": {
            "extracted_at": datetime.now().isoformat(),
            "period_start": start_str,
            "period_end":   end_str,
            "days_total":   days,
        },
        # Séries diárias (só resumos)
        "sleep":             sleep_daily,
        "sleep_avg":         sleep_avg,
        "heart_rates":       heart_rates,
        "hrv":               hrv_daily,
        "steps_daily":       steps_daily,
        "steps_weekly":      steps_weekly,
        "intensity_weekly":  intensity_weekly,
        "stress_daily":      stress_daily,
        # Atividades (campos essenciais apenas — sem GPS/splits/detalhes)
        "activities":        activities,
        # Cálculos pré-prontos
        "pmc":               pmc,
        "pace_evolution":    pace_evolution,
        "ef_monthly":        ef_monthly,
        "sleep_pace_correlation": sleep_pace_corr,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Exporta dados Garmin em formato compacto pré-calculado.")
    parser.add_argument("--email",   help="E-mail do Garmin Connect")
    parser.add_argument("--password", help="Senha do Garmin Connect")
    parser.add_argument("--start",   default="2026-01-01",        help="Data início YYYY-MM-DD")
    parser.add_argument("--end",     default=date.today().isoformat(), help="Data fim YYYY-MM-DD")
    parser.add_argument("--output",  default="garmin_data.json",  help="Arquivo JSON de saída")
    args = parser.parse_args()

    email    = args.email    or os.environ.get("GARMIN_EMAIL")
    password = args.password or os.environ.get("GARMIN_PASSWORD")

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

    log.info("Extraindo de %s até %s...", args.start, args.end)
    data = extract_all(client, args.start, args.end)

    log.info("Salvando em '%s'...", args.output)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=json_serial)

    size_mb = os.path.getsize(args.output) / (1024 * 1024)
    log.info("Concluído! Arquivo: %s (%.1f MB)", os.path.abspath(args.output), size_mb)

    # ── Upload para Supabase Storage ────────────────────────────────────────
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
            resp = httpx.put(
                f"{supabase_url}/storage/v1/object/garmin/garmin_data.json",
                content=content, headers=headers, timeout=300,
            )
            if resp.status_code in (200, 201):
                log.info("Upload Supabase concluído.")
            else:
                log.warning("Supabase %s: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            log.warning("Falha no upload Supabase: %s", e)
    else:
        log.info("Supabase não configurado — upload ignorado.")


if __name__ == "__main__":
    main()
