import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
from garminconnect import Garmin
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)

# Configuração da página
st.set_page_config(
    page_title="Dashboard Garmin",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .main {
        padding-top: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# FUNÇÕES DE AUTENTICAÇÃO E CONEXÃO GARMIN
# ============================================

@st.cache_resource
def init_garmin_session():
    """Inicializa a sessão do Garmin Connect"""
    return None

def authenticate_garmin(email, password):
    """Autentica com Garmin Connect"""
    try:
        client = Garmin(email, password)
        client.login()
        st.session_state.garmin_client = client
        st.session_state.garmin_authenticated = True
        st.success("✅ Autenticado com sucesso no Garmin Connect!")
        return True
    except Exception as e:
        st.error(f"❌ Erro na autenticação: {str(e)}")
        return False

def _parse_activity_date(activity):
    """Extrai a data de uma atividade tentando múltiplos campos do Garmin"""
    # 1. startTimeLocal  →  "2025-11-13 07:30:00"
    local = activity.get('startTimeLocal')
    if local:
        try:
            return pd.to_datetime(local)
        except Exception:
            pass

    # 2. startTimeGMT  →  "2025-11-13 10:30:00"
    gmt = activity.get('startTimeGMT')
    if gmt:
        try:
            return pd.to_datetime(gmt)
        except Exception:
            pass

    # 3. startTimeInSeconds  →  Unix timestamp
    ts = activity.get('startTimeInSeconds')
    if ts and ts > 0:
        try:
            return pd.to_datetime(ts, unit='s')
        except Exception:
            pass

    # 4. Fallback: data inválida marcada como NaT (será filtrada depois)
    return pd.NaT


def get_activities_from_garmin(days=30):
    """Busca atividades do Garmin Connect"""
    try:
        if not st.session_state.get('garmin_client'):
            st.error("❌ Não conectado ao Garmin. Faça login primeiro.")
            return pd.DataFrame()
        
        client = st.session_state.garmin_client
        
        # Buscar atividades dos últimos X dias
        activities = client.get_activities(0, 500)  # Busca até 500 atividades
        
        # Converter para DataFrame
        data = []
        for activity in activities:
            try:
                # Calcular ritmo para corridas
                distance_km = activity.get('distance', 0) / 1000 if activity.get('distance') else 0
                duration_min = activity.get('duration', 0) / 60 if activity.get('duration') else 0
                
                data.append({
                    'id': activity.get('activityId'),
                    'name': activity.get('activityName', 'Sem nome'),
                    'type': activity.get('activityType', {}).get('typeKey', 'unknown'),
                    'date': _parse_activity_date(activity),
                    'distance_km': distance_km,
                    'duration_min': duration_min,
                    'calories': activity.get('calories', 0),
                    'avg_hr': activity.get('avgHr', 0),
                    'max_hr': activity.get('maxHr', 0),
                    'steps': activity.get('steps', 0),
                    'elevation_gain': activity.get('elevationGain', 0),
                    'elevation_loss': activity.get('elevationLoss', 0),
                })
            except Exception as e:
                st.warning(f"⚠️ Erro ao processar atividade: {e}")
                continue
        
        df = pd.DataFrame(data)
        
        if len(df) > 0:
            df['date'] = pd.to_datetime(df['date'])
            df = df.dropna(subset=['date'])  # remover atividades sem data válida
            st.session_state.garmin_data = df
            st.success(f"✅ {len(df)} atividades carregadas do Garmin!")
            return df
        else:
            st.warning("⚠️ Nenhuma atividade encontrada no Garmin")
            return pd.DataFrame()
    
    except Exception as e:
        st.error(f"❌ Erro ao buscar atividades: {str(e)}")
        return pd.DataFrame()

def map_activity_type(type_key):
    """Mapeia tipo de atividade para português"""
    mapping = {
        'running': 'running',
        'cycling': 'cycling',
        'strength_training': 'strength_training',
        'strength': 'strength_training',
        'ride': 'cycling',
        'indoor_run': 'running',
        'indoor_cycling': 'cycling',
        'treadmill_running': 'running',
    }
    return mapping.get(type_key.lower(), 'other')

def calculate_pmc(df):
    """
    Calcula Performance Management Chart (PMC):
    - CTL (Chronic Training Load / Condicionamento): EWMA 42 dias do trimp diário
    - ATL (Acute Training Load / Fadiga): EWMA 7 dias do trimp diário
    - TSB (Training Stress Balance / Estado Físico): CTL - ATL
    
    TRIMP estimado = duração_min * (FC_média / FC_máx_estimada) * fator_tipo
    """
    if df.empty:
        return pd.DataFrame()

    # Criar série diária com trimp
    df = df.copy()
    df['date_only'] = df['date'].dt.normalize()

    # Estimar TRIMP por atividade
    fc_max_ref = 190.0
    type_factor = {'running': 1.0, 'cycling': 0.85, 'strength_training': 0.65, 'other': 0.5}

    def trimp(row):
        avg_hr = row['avg_hr'] if row['avg_hr'] > 0 else fc_max_ref * 0.7
        hr_ratio = min(avg_hr / fc_max_ref, 1.0)
        factor = type_factor.get(row['type'], 0.7)
        return row['duration_min'] * hr_ratio * factor

    df['trimp'] = df.apply(trimp, axis=1)

    # Somar trimp por dia
    daily = df.groupby('date_only')['trimp'].sum().reset_index()
    daily.columns = ['date', 'trimp']

    # Expandir para todos os dias no intervalo
    date_range = pd.date_range(daily['date'].min(), daily['date'].max(), freq='D')
    daily = daily.set_index('date').reindex(date_range, fill_value=0).reset_index()
    daily.columns = ['date', 'trimp']

    # CTL: EWMA 42 dias (α = 2/(42+1))
    # ATL: EWMA 7 dias  (α = 2/(7+1))
    ctl_alpha = 2 / (42 + 1)
    atl_alpha = 2 / (7 + 1)

    ctl_list, atl_list, tsb_list = [], [], []
    ctl, atl = 0.0, 0.0
    for _, row in daily.iterrows():
        tsb_list.append(ctl - atl)   # TSB do dia anterior (estado ao acordar)
        ctl = ctl + ctl_alpha * (row['trimp'] - ctl)
        atl = atl + atl_alpha * (row['trimp'] - atl)
        ctl_list.append(ctl)
        atl_list.append(atl)

    daily['ctl'] = ctl_list
    daily['atl'] = atl_list
    daily['tsb'] = tsb_list

    return daily


def create_pmc_chart(pmc_df):
    """Cria o gráfico PMC com CTL, ATL e TSB"""
    if pmc_df.empty:
        return None

    fig = go.Figure()

    # 1. Faixas de fundo (Zonas de TSB)
    fig.add_hrect(y0=-100, y1=-30, fillcolor="red",   opacity=0.1, line_width=0, annotation_text="Alto Risco")
    fig.add_hrect(y0=-30,  y1=-10, fillcolor="green", opacity=0.1, line_width=0, annotation_text="Evoluindo")
    fig.add_hrect(y0=-10,  y1=5,   fillcolor="gray",  opacity=0.1, line_width=0, annotation_text="Manutenção")

    # 2. TSB (Estado Físico) como área sombreada
    fig.add_trace(go.Scatter(
        x=pmc_df['date'], y=pmc_df['tsb'],
        fill='tozeroy',
        name='Estado Físico (TSB)',
        line=dict(color='lightgray', width=1),
        opacity=0.5
    ))

    # 3. CTL (Condicionamento) - linha principal mais grossa
    fig.add_trace(go.Scatter(
        x=pmc_df['date'], y=pmc_df['ctl'],
        name='Condicionamento (CTL)',
        line=dict(color='#3498db', width=4)
    ))

    all_vals = pd.concat([pmc_df['ctl'], pmc_df['tsb']]).dropna()
    y_min = all_vals.min()
    y_max = all_vals.max()
    y_pad = max(abs(y_max - y_min) * 0.05, 1)

    fig.update_layout(
        title='<b>📊 Performance Management Chart (PMC)</b><br>'
              '<sub>CTL=Condicionamento (42d) | TSB=Estado Físico (CTL−ATL)</sub>',
        xaxis_title='Data',
        yaxis_title='Carga / Stress',
        yaxis=dict(range=[y_min - y_pad, y_max + y_pad]),
        template='plotly_dark',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        hovermode='x unified',
        height=500,
    )

    return fig


def create_tsb_histogram(pmc_df):
    """Histograma diário do Estado Físico (TSB) nos últimos 60 dias"""
    if pmc_df.empty:
        return None

    df60 = pmc_df[pmc_df['date'] >= pmc_df['date'].max() - pd.Timedelta(days=59)].copy()

    # Cor de cada barra conforme a zona de TSB
    def tsb_color(v):
        if v > 5:    return '#3498db'   # Descansado/Adaptando — azul
        if v > -10:  return '#95a5a6'   # Manutenção — cinza
        if v > -30:  return '#2ecc71'   # Evoluindo — verde
        return '#e74c3c'                # Alto Risco — vermelho

    colors = [tsb_color(v) for v in df60['tsb']]

    fig = go.Figure()

    # Zonas de fundo (igual ao PMC)
    fig.add_hrect(y0=-100, y1=-30, fillcolor='red',   opacity=0.1, line_width=0)
    fig.add_hrect(y0=-30,  y1=-10, fillcolor='green', opacity=0.1, line_width=0)
    fig.add_hrect(y0=-10,  y1=5,   fillcolor='gray',  opacity=0.1, line_width=0)

    # Barras reais com cor por zona
    fig.add_trace(go.Bar(
        x=df60['date'],
        y=df60['tsb'],
        marker_color=colors,
        name='TSB diário',
        showlegend=False,
        hovertemplate='<b>%{x|%d/%m/%Y}</b><br>TSB: %{y:.1f}<extra></extra>'
    ))

    fig.add_hline(y=0, line_color='white', line_width=1, line_dash='dash')

    # Entradas de legenda usando Scatter com marcador quadrado (não afeta as barras)
    legend_zones = [
        ('#3498db', 'Descansado / Adaptando (TSB > 5)'),
        ('#95a5a6', 'Manutenção (−10 a 5)'),
        ('#2ecc71', 'Evoluindo (−30 a −10)'),
        ('#e74c3c', 'Alto Risco (TSB < −30)'),
    ]
    for color, label in legend_zones:
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode='markers',
            marker=dict(symbol='square', size=10, color=color),
            name=label,
            showlegend=True,
        ))

    y_min = df60['tsb'].min()
    y_max = df60['tsb'].max()
    y_pad = max(abs(y_max - y_min) * 0.05, 1)

    fig.update_layout(
        title='<b>📅 Estado Físico Diário (TSB) — Últimos 60 dias</b>',
        xaxis_title='Data',
        yaxis_title='TSB',
        yaxis=dict(range=[y_min - y_pad, y_max + y_pad]),
        template='plotly_dark',
        hovermode='x unified',
        height=380,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )

    return fig


@st.cache_data(ttl=3600)
def get_activity_hr_details(activity_id, _client):
    """Busca dados detalhados de frequência cardíaca de uma atividade"""
    if not activity_id:
        return None
    try:
        activity_details = _client.get_activity_details(activity_id)
        
        if not activity_details:
            return None
        
        hr_data = []
        
        # Estrutura principal: metricDescriptors + activityDetailMetrics
        metric_descriptors = activity_details.get('metricDescriptors', [])
        detail_metrics = activity_details.get('activityDetailMetrics', [])
        
        if metric_descriptors and detail_metrics:
            # Encontrar índices de heartRate e timestamp
            hr_index = None
            time_index = None
            for desc in metric_descriptors:
                key = desc.get('key', '')
                idx = desc.get('metricsIndex')
                if key in ('directHeartRate', 'heartRate'):
                    hr_index = idx
                elif key in ('directTimestamp', 'timestamp'):
                    time_index = idx
            
            if hr_index is not None:
                start_time = None
                for i, entry in enumerate(detail_metrics):
                    metrics = entry.get('metrics', [])
                    if len(metrics) <= hr_index:
                        continue
                    hr_value = metrics[hr_index]
                    if hr_value is None:
                        continue
                    
                    # Calcular tempo em segundos
                    if time_index is not None and len(metrics) > time_index and metrics[time_index] is not None:
                        ts = metrics[time_index]
                    else:
                        ts = entry.get('startTimeInSeconds')
                    
                    if ts is not None:
                        if start_time is None:
                            start_time = ts
                        time_sec = ts - start_time
                    else:
                        time_sec = i * 2  # ~2s por amostra
                    
                    hr_data.append({'time': time_sec, 'hr': float(hr_value)})
        
        return hr_data if hr_data else None
    
    except Exception as e:
        st.warning(f"⚠️ Erro ao buscar dados de FC: {e}")
        return None


@st.cache_data(ttl=3600)
def get_activity_all_metrics(activity_id, _client):
    """Busca todas as métricas disponíveis de uma atividade (pace, FC, elevação, cadência, etc.)"""
    if not activity_id:
        return None
    try:
        details = _client.get_activity_details(activity_id)
        if not details:
            return None

        descriptors = details.get('metricDescriptors', [])
        raw_metrics = details.get('activityDetailMetrics', [])
        if not descriptors or not raw_metrics:
            return None

        idx_map = {
            d['key']: d['metricsIndex']
            for d in descriptors
            if d.get('key') and d.get('metricsIndex') is not None
        }

        rows = []
        for entry in raw_metrics:
            vals = entry.get('metrics', [])
            rows.append({key: (vals[idx] if idx < len(vals) else None) for key, idx in idx_map.items()})

        if not rows:
            return None

        df = pd.DataFrame(rows)

        # Eixo de distância (metros → km)
        for dk in ('directDistance', 'sumDistance', 'distance'):
            if dk in df.columns:
                df['dist_km'] = pd.to_numeric(df[dk], errors='coerce') / 1000
                break

        # Eixo de tempo (segundos → minutos)
        for tk in ('directTimestamp', 'timestamp'):
            if tk in df.columns:
                ts = pd.to_numeric(df[tk], errors='coerce')
                df['time_min'] = (ts - ts.iloc[0]) / 60
                break

        if 'dist_km' not in df.columns and 'time_min' not in df.columns:
            df['time_min'] = (pd.RangeIndex(len(df)) * 2) / 60

        return df
    except Exception:
        return None


@st.cache_data(ttl=3600)
def get_activity_summary(activity_id, _client):
    """Busca o resumo completo de uma atividade (estatísticas detalhadas)."""
    if not activity_id:
        return None
    try:
        return _client.get_activity(activity_id)
    except Exception:
        return None


def _fmt_pace(speed_mps):
    if not speed_mps or speed_mps <= 0:
        return "—"
    sec_per_km = 1000 / speed_mps
    m, s = divmod(int(sec_per_km), 60)
    return f"{m}:{s:02d} /km"


def _fmt_speed(speed_mps):
    if not speed_mps or speed_mps <= 0:
        return "—"
    return f"{speed_mps * 3.6:.1f} km/h"


def _fmt_time(seconds):
    if not seconds or seconds <= 0:
        return "—"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _row(label, value):
    return (f"<tr><td style='padding:4px 12px 4px 0;color:#aaa;white-space:nowrap'>{label}</td>"
            f"<td style='padding:4px 0;font-weight:500'>{value}</td></tr>")


def render_activity_summary(summary, selected):
    """Renderiza o resumo estatístico de uma corrida à semelhança do Garmin."""
    if not summary:
        st.info("ℹ️ Resumo detalhado não disponível para esta atividade.")
        return

    # A API retorna os dados dentro de 'summaryDTO'
    s = summary.get('summaryDTO', summary)

    def v(key, default=None):
        val = s.get(key, default)
        return val if val not in (None, 0, 0.0, '') else default

    # ---- Ritmo / Velocidade ----
    avg_speed = s.get('averageSpeed')
    mov_speed = s.get('averageMovingSpeed')
    gap_speed = s.get('avgGradeAdjustedSpeed')
    max_speed = s.get('maxSpeed')

    pace_rows = ""
    if avg_speed:  pace_rows += _row("Ritmo médio", _fmt_pace(avg_speed))
    if mov_speed:  pace_rows += _row("Ritmo movimentação médio", _fmt_pace(mov_speed))
    if gap_speed:  pace_rows += _row("Ritmo méd. ajust. por inclin.", _fmt_pace(gap_speed))
    if max_speed:  pace_rows += _row("Melhor ritmo", _fmt_pace(max_speed))

    vel_rows = ""
    if avg_speed:  vel_rows += _row("Velocidade média", _fmt_speed(avg_speed))
    if mov_speed:  vel_rows += _row("Veloc. média de movimento", _fmt_speed(mov_speed))
    if gap_speed:  vel_rows += _row("Vel. méd. ajust. por inclin.", _fmt_speed(gap_speed))
    if max_speed:  vel_rows += _row("Velocidade máxima", _fmt_speed(max_speed))

    # ---- Cronometragem ----
    total_dur   = s.get('duration')
    moving_dur  = s.get('movingDuration')
    elapsed_dur = s.get('elapsedDuration')
    time_rows = ""
    if total_dur:   time_rows += _row("Tempo total", _fmt_time(total_dur))
    if moving_dur:  time_rows += _row("Tempo em movimento", _fmt_time(moving_dur))
    if elapsed_dur: time_rows += _row("Tempo transcorrido", _fmt_time(elapsed_dur))

    # ---- Corrida/Caminhada (a partir de splitSummaries) ----
    rw_rows = ""
    splits = summary.get('splitSummaries', [])
    run_dur  = next((sp.get('duration', 0) for sp in splits if sp.get('splitType') == 'RWD_RUN'),  None)
    walk_dur = next((sp.get('duration', 0) for sp in splits if sp.get('splitType') == 'RWD_WALK'), None)
    if run_dur:  rw_rows += _row("Tempo de corrida", _fmt_time(run_dur))
    if walk_dur: rw_rows += _row("Tempo da caminhada", _fmt_time(walk_dur))

    # ---- Frequência Cardíaca ----
    avg_hr = s.get('averageHR') or selected.get('avg_hr')
    max_hr = s.get('maxHR') or selected.get('max_hr')
    hr_rows = ""
    if avg_hr: hr_rows += _row("Frequência cardíaca média", f"{avg_hr:.0f} bpm")
    if max_hr: hr_rows += _row("Frequência cardíaca máxima", f"{max_hr:.0f} bpm")

    # ---- Efeito de Treino ----
    ae  = s.get('trainingEffect')
    ane = s.get('anaerobicTrainingEffect')
    ben_raw = s.get('trainingEffectLabel', '')
    ben_map = {
        'LACTATE_THRESHOLD': 'Limite (Aeróbico alto)',
        'BASE_AEROBIC_TRAINING': 'Treinamento Aeróbico Base',
        'TEMPO_RUN': 'Tempo',
        'AEROBIC_CAPACITY': 'Capacidade Aeróbica',
        'RECOVERY': 'Recuperação',
    }
    ben = ben_map.get(ben_raw, ben_raw.replace('_', ' ').title()) if ben_raw else None
    te_rows = ""
    if ben: te_rows += _row("Principal benefício", ben)
    if ae:  te_rows += _row("Aeróbico", f"{float(ae):.1f}")
    if ane: te_rows += _row("Anaeróbico", f"{float(ane):.1f}")

    # ---- Potência ----
    avg_pwr = s.get('averagePower')
    max_pwr = s.get('maxPower')
    pwr_rows = ""
    if avg_pwr: pwr_rows += _row("Potência média", f"{avg_pwr:.0f} W")
    if max_pwr: pwr_rows += _row("Energia máxima", f"{max_pwr:.0f} W")

    # ---- Dinâmica de Corrida ----
    avg_cad  = s.get('averageRunCadence')
    max_cad  = s.get('maxRunCadence')
    stride   = s.get('strideLength')   # cm
    vert_rat = s.get('verticalRatio')  # %
    vert_osc = s.get('verticalOscillation')  # cm
    gct      = s.get('groundContactTime')    # ms
    dyn_rows = ""
    if avg_cad:  dyn_rows += _row("Cadência corrida média", f"{avg_cad:.0f} epm")
    if max_cad:  dyn_rows += _row("Cadência corrida máx.", f"{max_cad:.0f} epm")
    if stride:   dyn_rows += _row("Compr. médio dos passos", f"{stride / 100:.2f} m")
    if vert_rat: dyn_rows += _row("Propor. de média vertical", f"{vert_rat:.1f}%")
    if vert_osc: dyn_rows += _row("Oscilação vertical média", f"{vert_osc:.1f} cm")
    if gct:      dyn_rows += _row("Tpo méd. contato com solo", f"{gct:.0f} ms")

    # ---- Elevação ----
    asc   = s.get('elevationGain') or selected.get('elevation_gain')
    desc  = s.get('elevationLoss') or selected.get('elevation_loss')
    e_min = s.get('minElevation')
    e_max = s.get('maxElevation')
    elev_rows = ""
    if asc:   elev_rows += _row("Subida total", f"{float(asc):.0f} m")
    if desc:  elev_rows += _row("Descida total", f"{float(desc):.0f} m")
    if e_min: elev_rows += _row("Elevação mínima", f"{e_min:.0f} m")
    if e_max: elev_rows += _row("Elevação máxima", f"{e_max:.0f} m")

    # ---- Nutrição & Hidratação ----
    rest_cal = s.get('bmrCalories')
    act_cal  = s.get('calories', 0) - (rest_cal or 0) if s.get('calories') else None
    tot_cal  = s.get('calories') or selected.get('calories')
    sweat    = s.get('waterEstimated')
    steps    = s.get('steps')
    nut_rows = ""
    if rest_cal:           nut_rows += _row("Calorias em repouso", f"{rest_cal:.0f}")
    if act_cal and act_cal > 0: nut_rows += _row("Calorias ativas", f"{act_cal:.0f}")
    if tot_cal:            nut_rows += _row("Total de calorias queimadas", f"{float(tot_cal):.0f}")
    if sweat:              nut_rows += _row("Perda de suor estimada", f"{sweat:.0f} ml")

    # ---- Temperatura ----
    avg_tmp = s.get('averageTemperature')
    min_tmp = s.get('minTemperature')
    max_tmp = s.get('maxTemperature')
    tmp_rows = ""
    if avg_tmp: tmp_rows += _row("Temperatura média", f"{avg_tmp:.0f}°C")
    if min_tmp: tmp_rows += _row("Temperatura mínima", f"{min_tmp:.0f}°C")
    if max_tmp: tmp_rows += _row("Temperatura máxima", f"{max_tmp:.0f}°C")

    # ---- Minutos de Intensidade ----
    mod_int  = s.get('moderateIntensityMinutes')
    high_int = s.get('vigorousIntensityMinutes')
    tot_int  = (mod_int or 0) + (high_int or 0) or None
    int_rows = ""
    if mod_int:  int_rows += _row("Moderado", f"{mod_int} min")
    if high_int: int_rows += _row("Alta", f"{high_int} min")
    if tot_int:  int_rows += _row("Total", f"{tot_int} min")

    # ---- Body Battery / Connect IQ ----
    bb_impact = s.get('differenceBodyBattery')
    # Connect IQ: appID f275eca7 → field 2=HRSS, 3=HRSS/h, 4=TRIMP
    ciq = {m['developerFieldNumber']: float(m['value'])
           for m in summary.get('connectIQMeasurements', [])
           if m.get('appID') == 'f275eca7-701a-4db8-b3da-d0ea8fd7955c'}
    hrss   = ciq.get(2)
    hrss_h = ciq.get(3)
    trimp  = ciq.get(4)
    bb_rows = ""
    if bb_impact is not None: bb_rows += _row("Body Battery (impacto)", f"{bb_impact:.0f}")
    if hrss:      bb_rows += _row("HRSS", f"{hrss:.1f}")
    if hrss_h:    bb_rows += _row("HRSS/h", f"{hrss_h:.1f}")
    if trimp:     bb_rows += _row("TRIMP", f"{trimp:.1f}")

    def _section(title, rows):
        if not rows:
            return ""
        return (f"<div style='margin-bottom:1.4rem'>"
                f"<p style='font-size:0.72rem;font-weight:700;text-transform:uppercase;"
                f"letter-spacing:1px;color:#888;margin-bottom:4px'>{title}</p>"
                f"<table style='border-collapse:collapse;width:100%'>{rows}</table>"
                f"</div>")

    html = (
        _section("Ritmo", pace_rows) +
        _section("Velocidade", vel_rows) +
        _section("Cronometragem", time_rows) +
        _section("Detecção de Corrida / Caminhada", rw_rows) +
        _section("Freq. Cardíaca", hr_rows) +
        _section("Efeito de Treino", te_rows) +
        _section("Potência", pwr_rows) +
        _section("Dinâmica de Corrida", dyn_rows) +
        _section("Elevação", elev_rows) +
        _section("Nutrição & Hidratação", nut_rows) +
        _section("Temperatura", tmp_rows) +
        _section("Minutos de Intensidade", int_rows) +
        _section("Body Battery / Connect IQ", bb_rows)
    )

    if html.strip():
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.info("ℹ️ Nenhum dado de resumo disponível para esta atividade.")


def _create_metric_chart(df, y_key, title, y_label, color, x_key=None,
                          fill=True, invert_y=False, height=280,
                          hoverformat='.1f', transform_fn=None):
    """Cria gráfico genérico de uma métrica ao longo da distância/tempo."""
    if df is None or y_key not in df.columns:
        return None

    if x_key is None:
        x_key = 'dist_km' if 'dist_km' in df.columns else 'time_min'
    x_label = 'Distância (km)' if x_key == 'dist_km' else 'Tempo (min)'

    if x_key not in df.columns:
        return None

    y = pd.to_numeric(df[y_key], errors='coerce')
    x = df[x_key]

    if transform_fn:
        y = y.apply(lambda v: transform_fn(v) if pd.notna(v) and v > 0 else None)
        y = pd.to_numeric(y, errors='coerce')

    mask = y.notna() & (y > 0)
    if mask.sum() < 5:
        return None

    y = y[mask]
    x = x[mask]

    y_min = float(y.min())
    y_max = float(y.max())
    y_pad = max(abs(y_max - y_min) * 0.05, 0.5)

    fill_color = 'rgba(255,255,255,0.08)'
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y, mode='lines',
        line=dict(color=color, width=1.8),
        fill='tozeroy' if fill else None,
        fillcolor=fill_color if fill else None,
        showlegend=False,
        hovertemplate=f'<b>%{{x:.2f}}</b><br>{y_label}: %{{y:{hoverformat}}}<extra></extra>',
    ))

    avg = float(y.mean())
    fig.add_hline(y=avg, line_dash='dash', line_color='white', line_width=1, opacity=0.4,
                  annotation_text=f'Média: {avg:{hoverformat}}',
                  annotation_position='top right',
                  annotation=dict(font=dict(size=10, color='white')))

    yaxis_cfg = dict(range=[y_min - y_pad, y_max + y_pad])
    if invert_y:
        yaxis_cfg['autorange'] = 'reversed'

    fig.update_layout(
        title=f'<b>{title}</b>',
        xaxis_title=x_label,
        yaxis_title=y_label,
        yaxis=yaxis_cfg,
        template='plotly_dark',
        height=height,
        showlegend=False,
        hovermode='x unified',
        margin=dict(l=50, r=90, t=50, b=40),
    )
    return fig


def create_hr_graph(hr_data, activity_duration_min):
    """Cria gráfico de frequência cardíaca ao longo do tempo"""
    if not hr_data or len(hr_data) == 0:
        return None
    
    try:
        # Converter para DataFrame
        df_hr = pd.DataFrame(hr_data)
        
        # Converter tempo para minutos se for timestamp
        if 'time' in df_hr.columns:
            # Se for um valor numérico, assumir que é segundos
            if pd.api.types.is_numeric_dtype(df_hr['time']):
                df_hr['time_min'] = df_hr['time'] / 60
            else:
                # Se for string ou datetime, tentar converter
                try:
                    df_hr['time'] = pd.to_datetime(df_hr['time'])
                    df_hr['time_min'] = (df_hr['time'] - df_hr['time'].iloc[0]).dt.total_seconds() / 60
                except:
                    df_hr['time_min'] = range(len(df_hr))
        
        # Calcular estatísticas
        avg_hr = df_hr['hr'].mean()
        max_hr = df_hr['hr'].max()
        min_hr = df_hr['hr'].min()
        
        # Criar gráfico
        fig = go.Figure()
        
        # Adicionar zonas de frequência cardíaca (baseado em estimativa de 220-age)
        # Para simplificar, usar zonas genéricas
        max_estimated = 200  # Estimativa conservadora
        
        # Zonas de intensidade
        zona1_limit = max_estimated * 0.5   # Recuperação (< 50%)
        zona2_limit = max_estimated * 0.6   # Aeróbica leve (50-60%)
        zona3_limit = max_estimated * 0.7   # Aeróbica moderada (60-70%)
        zona4_limit = max_estimated * 0.85  # Limiar anaeróbico (70-85%)
        # Acima: Anaeróbica (> 85%)
        
        # Adicionar zonas como áreas sombreadas (como background)
        x_range = [df_hr['time_min'].min(), df_hr['time_min'].max()]
        
        # Zona 1: Recuperação
        fig.add_vrect(x0=x_range[0], x1=x_range[1], y0=0, y1=zona1_limit,
                     fillcolor="#3498db", opacity=0.05, layer="below", line_width=0)
        
        # Zona 2: Aeróbica leve
        fig.add_vrect(x0=x_range[0], x1=x_range[1], y0=zona1_limit, y1=zona2_limit,
                     fillcolor="#2ecc71", opacity=0.05, layer="below", line_width=0)
        
        # Zona 3: Aeróbica moderada
        fig.add_vrect(x0=x_range[0], x1=x_range[1], y0=zona2_limit, y1=zona3_limit,
                     fillcolor="#f39c12", opacity=0.05, layer="below", line_width=0)
        
        # Zona 4: Limiar anaeróbico
        fig.add_vrect(x0=x_range[0], x1=x_range[1], y0=zona3_limit, y1=zona4_limit,
                     fillcolor="#e74c3c", opacity=0.05, layer="below", line_width=0)
        
        # Zona 5: Anaeróbica
        fig.add_vrect(x0=x_range[0], x1=x_range[1], y0=zona4_limit, y1=max_estimated*1.1,
                     fillcolor="#c0392b", opacity=0.05, layer="below", line_width=0)
        
        # Adicionar linha de frequência cardíaca
        fig.add_trace(go.Scatter(
            x=df_hr['time_min'] if 'time_min' in df_hr.columns else range(len(df_hr)),
            y=df_hr['hr'],
            mode='lines',
            name='Frequência Cardíaca',
            line=dict(color='#FF6B6B', width=2.5),
            fill='tozeroy',
            fillcolor='rgba(255, 107, 107, 0.3)',
            hovertemplate='<b>Tempo:</b> %{x:.1f} min<br><b>FC:</b> %{y:.0f} bpm<extra></extra>'
        ))
        
        # Adicionar linhas de referência
        fig.add_hline(y=avg_hr, line_dash="dash", line_color="blue", 
                     annotation_text=f"Média: {avg_hr:.0f} bpm", 
                     annotation_position="right",
                     annotation=dict(font=dict(size=11)))
        fig.add_hline(y=max_hr, line_dash="dot", line_color="red",
                     annotation_text=f"Máx: {max_hr:.0f} bpm",
                     annotation_position="right",
                     annotation=dict(font=dict(size=11)))
        
        hr_pad = max((max_hr - min_hr) * 0.05, 2)

        fig.update_layout(
            title='<b>❤️ Frequência Cardíaca Durante a Atividade</b><br><sub>Zonas: Azul=Recuperação | Verde=Leve | Laranja=Moderada | Vermelho=Intenso</sub>',
            xaxis_title='Tempo (minutos)',
            yaxis_title='Frequência Cardíaca (bpm)',
            hovermode='x unified',
            height=450,
            template='plotly_white',
            showlegend=True,
            yaxis=dict(range=[max(0, min_hr - hr_pad), max_hr + hr_pad])
        )
        
        return fig
    
    except Exception as e:
        st.warning(f"⚠️ Erro ao criar gráfico de FC: {e}")
        return None

# ============================================
# INICIALIZAR SESSION STATE
# ============================================

if 'garmin_authenticated' not in st.session_state:
    st.session_state.garmin_authenticated = False

if 'garmin_client' not in st.session_state:
    st.session_state.garmin_client = None

if 'garmin_data' not in st.session_state:
    st.session_state.garmin_data = pd.DataFrame()

# ============================================
# SIDEBAR - AUTENTICAÇÃO
# ============================================

st.sidebar.title("🔐 Garmin Connect")

if not st.session_state.garmin_authenticated:
    st.sidebar.warning("⚠️ Não autenticado")
    
    with st.sidebar.form("login_form"):
        email = st.text_input("📧 Email Garmin")
        password = st.text_input("🔒 Senha Garmin", type="password")
        submit = st.form_submit_button("🔗 Conectar ao Garmin")
        
        if submit:
            if email and password:
                with st.spinner("🔄 Conectando ao Garmin..."):
                    authenticate_garmin(email, password)
            else:
                st.error("❌ Preencha email e senha")
else:
    st.sidebar.success("✅ Conectado ao Garmin")
    
    if st.sidebar.button("🔓 Desconectar", use_container_width=True):
        st.session_state.garmin_authenticated = False
        st.session_state.garmin_client = None
        st.session_state.garmin_data = pd.DataFrame()
        st.rerun()

# ============================================
# SIDEBAR - FILTROS E SINCRONIZAÇÃO
# ============================================

if st.session_state.garmin_authenticated:
    st.sidebar.divider()
    st.sidebar.title("📌 Navegação")
    pagina = st.sidebar.radio(
        "",
        ["📈 Dashboard", "🔍 Detalhamento"],
        label_visibility="collapsed"
    )
    st.sidebar.divider()
    st.sidebar.title("⚙️ Filtros e Sincronização")
    
    # Botão de sincronização
    col_sync1, col_sync2 = st.sidebar.columns(2)
    with col_sync1:
        if st.button("🔄 Sincronizar", use_container_width=True):
            with st.spinner("📡 Sincronizando com Garmin..."):
                df = get_activities_from_garmin()
                if len(df) > 0:
                    st.rerun()
    
    with col_sync2:
        if st.button("🗑️ Limpar", use_container_width=True):
            st.session_state.garmin_data = pd.DataFrame()
            st.rerun()
    
    # Carregar dados se ainda não foram carregados
    if len(st.session_state.garmin_data) == 0:
        with st.spinner("📡 Carregando atividades do Garmin..."):
            df = get_activities_from_garmin()
    else:
        df = st.session_state.garmin_data.copy()
    
    if len(df) > 0:
        # Normalizar tipos de atividade
        df['type'] = df['type'].apply(map_activity_type)
        
        # Período
        st.sidebar.subheader("📅 Período")
        col_date1, col_date2 = st.sidebar.columns(2)
        with col_date1:
            start_date = st.date_input("De", df['date'].min())
        with col_date2:
            end_date = st.date_input("Até", df['date'].max())
        
        # Tipo de atividade
        st.sidebar.subheader("🏷️ Tipo")
        activity_types = df[df['type'] != 'other']['type'].unique().tolist()
        activity_type = st.sidebar.multiselect(
            "Selecione",
            activity_types,
            default=activity_types,
            format_func=lambda x: {"running": "🏃 Corrida", "cycling": "🚴 Ciclismo", "strength_training": "💪 Musculação"}.get(x, x)
        )
        
        # Filtrar dados
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        df_filtered = df[(df['type'].isin(activity_type)) & (df['date'] >= start_date) & (df['date'] <= end_date)]
        
        # ============================================
        # HEADER
        # ============================================
        
        st.title("🏃 Dashboard de Atividades Garmin")
        st.markdown(f"**Sincronizado em:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        st.markdown(f"**Período:** {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')} | **Total:** {len(df_filtered)} atividades")
        
        # ============================================
        # KPIs PRINCIPAIS
        # ============================================
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("📊 Total Atividades", len(df_filtered))
        
        with col2:
            total_kcal = df_filtered['calories'].sum()
            st.metric("🔥 Calorias Queimadas", f"{total_kcal:,.0f}", "kcal")
        
        with col3:
            total_distance = df_filtered[df_filtered['type'] != 'strength_training']['distance_km'].sum()
            st.metric("📍 Distância Total", f"{total_distance:.1f}", "km")
        
        with col4:
            total_time = df_filtered['duration_min'].sum()
            st.metric("⏱️ Tempo Total", f"{total_time/60:.1f}", "horas")
        
        with col5:
            avg_hr = df_filtered[df_filtered['avg_hr'] > 0]['avg_hr'].mean()
            st.metric("❤️ FC Média", f"{avg_hr:.0f}", "bpm" if avg_hr > 0 else "—")
        
        st.divider()
        
        # ============================================
        # PÁGINAS
        # ============================================
        
        if pagina == "🔍 Detalhamento":
            st.title("🔍 Detalhamento da Atividade")
            
            df_sorted = df_filtered.sort_values('date', ascending=False)
            
            if len(df_sorted) == 0:
                st.info("Nenhuma atividade encontrada para o período selecionado.")
            else:
                col_select1, col_select2, col_select3 = st.columns([1, 2, 1])
                with col_select2:
                    selected_activity = st.selectbox(
                        "Selecione uma atividade:",
                        range(len(df_sorted)),
                        format_func=lambda i: f"{df_sorted.iloc[i]['date'].strftime('%d/%m/%Y')} - {df_sorted.iloc[i]['name']}"
                    )
                
                selected = df_sorted.iloc[selected_activity]
                
                st.markdown("---")
                
                type_colors = {'running': '🏃‍♂️', 'cycling': '🚴‍♂️', 'strength_training': '💪'}
                type_names = {'running': 'Corrida', 'cycling': 'Ciclismo', 'strength_training': 'Musculação'}
                
                st.markdown(f"## {type_colors.get(selected['type'], '📌')} {selected['name']}")
                st.markdown(f"**Data:** {selected['date'].strftime('%d de %B de %Y')} | **Tipo:** {type_names.get(selected['type'], 'Desconhecido')}")
                st.markdown("---")
                
                # ---- MÉTRICAS ----
                if selected['type'] == 'running':
                    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                    with metric_col1:
                        st.metric("📍 Distância", f"{selected['distance_km']:.2f} km",
                                 delta=f"{(selected['distance_km'] / df[df['type']=='running']['distance_km'].mean()):.1%} da média" if len(df[df['type']=='running']) > 0 else None)
                    with metric_col2:
                        minutes = int(selected['duration_min'])
                        seconds = int((selected['duration_min'] % 1) * 60)
                        ritmo = (selected['duration_min'] / selected['distance_km']) if selected['distance_km'] > 0 else 0
                        st.metric("⏱️ Duração", f"{minutes} min {seconds}s", delta=f"Ritmo: {ritmo:.2f} min/km")
                    with metric_col3:
                        st.metric("❤️ FC Média", f"{selected['avg_hr']:.0f} bpm", delta=f"Máx: {selected['max_hr']:.0f} bpm")
                    with metric_col4:
                        st.metric("🔥 Calorias", f"{selected['calories']:.0f} kcal", delta=f"Passos: {int(selected['steps'])}")
                    col_extra1, col_extra2 = st.columns(2)
                    with col_extra1:
                        st.info(f"**Elevação:** {selected['elevation_gain']:.0f} m de ganho")
                    with col_extra2:
                        st.info(f"**Passos:** {int(selected['steps'])} passos")
                
                elif selected['type'] == 'cycling':
                    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                    with metric_col1:
                        st.metric("📍 Distância", f"{selected['distance_km']:.2f} km",
                                 delta=f"{(selected['distance_km'] / df[df['type']=='cycling']['distance_km'].mean()):.1%} da média" if len(df[df['type']=='cycling']) > 0 else None)
                    with metric_col2:
                        minutes = int(selected['duration_min'])
                        seconds = int((selected['duration_min'] % 1) * 60)
                        velocidade = (selected['distance_km'] / (selected['duration_min'] / 60)) if selected['duration_min'] > 0 else 0
                        st.metric("⏱️ Duração", f"{minutes} min {seconds}s", delta=f"Velocidade: {velocidade:.1f} km/h")
                    with metric_col3:
                        st.metric("❤️ FC Média", f"{selected['avg_hr']:.0f} bpm", delta=f"Máx: {selected['max_hr']:.0f} bpm")
                    with metric_col4:
                        st.metric("🔥 Calorias", f"{selected['calories']:.0f} kcal", delta=f"Elevação: {selected['elevation_gain']:.0f} m")
                    col_extra1, col_extra2 = st.columns(2)
                    with col_extra1:
                        st.info(f"**Ganho de Elevação:** {selected['elevation_gain']:.0f} m")
                    with col_extra2:
                        velocidade = (selected['distance_km'] / (selected['duration_min'] / 60)) if selected['duration_min'] > 0 else 0
                        st.info(f"**Velocidade Média:** {velocidade:.1f} km/h")
                
                else:  # strength_training
                    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                    with metric_col1:
                        minutes = int(selected['duration_min'])
                        seconds = int((selected['duration_min'] % 1) * 60)
                        st.metric("⏱️ Duração", f"{minutes} min {seconds}s",
                                 delta=f"{(selected['duration_min'] / df[df['type']=='strength_training']['duration_min'].mean()):.1%} da média" if len(df[df['type']=='strength_training']) > 0 else None)
                    with metric_col2:
                        st.metric("❤️ FC Média", f"{selected['avg_hr']:.0f} bpm", delta=f"Máx: {selected['max_hr']:.0f} bpm")
                    with metric_col3:
                        intensidade = (selected['calories'] / (selected['duration_min'] / 60)) if selected['duration_min'] > 0 else 0
                        st.metric("🔥 Calorias", f"{selected['calories']:.0f} kcal", delta=f"Intensidade: {intensidade:.1f} kcal/h")
                    with metric_col4:
                        intensidade = (selected['calories'] / (selected['duration_min'] / 60)) if selected['duration_min'] > 0 else 0
                        st.metric("📊 Intensidade", f"{intensidade:.1f} kcal/h", delta="Alta" if intensidade > 5 else "Média")
                
                st.markdown("---")

                # ---- ABAS DE DETALHE (corrida) ----
                if selected['type'] == 'running' and st.session_state.get('garmin_client'):
                    tab_resumo, tab_graficos = st.tabs(["📋 Estatísticas", "📈 Gráficos"])

                    with tab_resumo:
                        with st.spinner("📡 Carregando resumo..."):
                            summary = get_activity_summary(selected['id'], st.session_state.garmin_client)
                        render_activity_summary(summary, selected)

                    with tab_graficos:
                        with st.spinner("📡 Carregando métricas detalhadas..."):
                            metrics_df = get_activity_all_metrics(selected['id'], st.session_state.garmin_client)

                        if metrics_df is not None:
                            # Efeito de Treino (summary, shown as cards)
                            aerobic_te   = selected.get('aerobicTrainingEffect', selected.get('training_effect', None))
                            anaerobic_te = selected.get('anaerobicTrainingEffect', None)
                            if aerobic_te or anaerobic_te:
                                st.subheader("🎯 Efeito do Treino")
                                c1, c2 = st.columns(2)
                                with c1:
                                    st.metric("💚 Aeróbico", f"{aerobic_te:.1f}" if aerobic_te else "—")
                                with c2:
                                    st.metric("🔴 Anaeróbico", f"{anaerobic_te:.1f}" if anaerobic_te else "—")
    
                            x_key = 'dist_km' if 'dist_km' in metrics_df.columns else 'time_min'
    
                            # ---- Ritmo ----
                            pace_key = next((k for k in ('directSpeed', 'speed') if k in metrics_df.columns), None)
                            if pace_key:
                                st.subheader("⏱️ Ritmo")
                                fig_pace = _create_metric_chart(
                                    metrics_df, pace_key, 'Ritmo', 'min/km', '#f39c12',
                                    x_key=x_key, fill=True, invert_y=True,
                                    hoverformat='.2f',
                                    transform_fn=lambda v: round(1000 / (v * 60), 2) if v > 0 else None
                                )
                                if fig_pace:
                                    st.plotly_chart(fig_pace, use_container_width=True)
    
                            # ---- Frequência Cardíaca ----
                            hr_key = next((k for k in ('directHeartRate', 'heartRate') if k in metrics_df.columns), None)
                            if hr_key:
                                st.subheader("❤️ Frequência Cardíaca")
                                fig_hr2 = _create_metric_chart(
                                    metrics_df, hr_key, 'Frequência Cardíaca', 'bpm', '#e74c3c',
                                    x_key=x_key, fill=True, hoverformat='.0f'
                                )
                                if fig_hr2:
                                    st.plotly_chart(fig_hr2, use_container_width=True)
    
                                # Zonas FC
                                hr_vals = pd.to_numeric(metrics_df[hr_key], errors='coerce').dropna()
                                if len(hr_vals) > 0:
                                    max_est = 200
                                    z1 = (hr_vals < max_est * 0.50).sum()
                                    z2 = ((hr_vals >= max_est * 0.50) & (hr_vals < max_est * 0.60)).sum()
                                    z3 = ((hr_vals >= max_est * 0.60) & (hr_vals < max_est * 0.70)).sum()
                                    z4 = ((hr_vals >= max_est * 0.70) & (hr_vals < max_est * 0.85)).sum()
                                    z5 = (hr_vals >= max_est * 0.85).sum()
                                    total_s = len(hr_vals)
                                    st.subheader("⚡ Tempo em Zonas de FC")
                                    col_z1, col_z2, col_z3, col_z4, col_z5 = st.columns(5)
                                    def _fmt_zone(n, tot, label):
                                        pct = n / tot * 100
                                        mins = n * 2 / 60
                                        return f"**{label}**\n\n{pct:.0f}% ({mins:.0f} min)"
                                    with col_z1: st.info(_fmt_zone(z1, total_s, "🔵 Z1 Recuperação"))
                                    with col_z2: st.info(_fmt_zone(z2, total_s, "🟢 Z2 Leve"))
                                    with col_z3: st.info(_fmt_zone(z3, total_s, "🟡 Z3 Moderada"))
                                    with col_z4: st.info(_fmt_zone(z4, total_s, "🟠 Z4 Limiar"))
                                    with col_z5: st.info(_fmt_zone(z5, total_s, "🔴 Z5 Máximo"))
    
                            # ---- Elevação ----
                            elev_key = next((k for k in ('directElevation', 'directAltitude', 'elevation') if k in metrics_df.columns), None)
                            if elev_key:
                                st.subheader("⛰️ Elevação")
                                fig_elev = _create_metric_chart(
                                    metrics_df, elev_key, 'Elevação', 'm', '#27ae60',
                                    x_key=x_key, fill=True, hoverformat='.0f'
                                )
                                if fig_elev:
                                    st.plotly_chart(fig_elev, use_container_width=True)
    
                            # ---- Potência ----
                            pwr_key = next((k for k in ('directPower', 'directRunPower', 'runPower') if k in metrics_df.columns), None)
                            if pwr_key:
                                st.subheader("⚡ Potência")
                                fig_pwr = _create_metric_chart(
                                    metrics_df, pwr_key, 'Potência', 'W', '#9b59b6',
                                    x_key=x_key, fill=True, hoverformat='.0f'
                                )
                                if fig_pwr:
                                    st.plotly_chart(fig_pwr, use_container_width=True)
    
                            # ---- Cadência ----
                            cad_key = next((k for k in ('directRunCadence', 'runCadence', 'directBikeCadence') if k in metrics_df.columns), None)
                            if cad_key:
                                st.subheader("🦵 Cadência")
                                fig_cad = _create_metric_chart(
                                    metrics_df, cad_key, 'Cadência', 'spm', '#3498db',
                                    x_key=x_key, fill=False, hoverformat='.0f'
                                )
                                if fig_cad:
                                    st.plotly_chart(fig_cad, use_container_width=True)
    
                            # ---- Comprimento da Passada ----
                            stride_key = next((k for k in ('directStrideLength', 'strideLength') if k in metrics_df.columns), None)
                            if stride_key:
                                st.subheader("👟 Comprimento da Passada")
                                fig_stride = _create_metric_chart(
                                    metrics_df, stride_key, 'Comprimento da Passada', 'm', '#1abc9c',
                                    x_key=x_key, fill=False, hoverformat='.2f'
                                )
                                if fig_stride:
                                    st.plotly_chart(fig_stride, use_container_width=True)
    
                            # ---- Proporção Vertical ----
                            vr_key = next((k for k in ('directVerticalRatio', 'verticalRatio') if k in metrics_df.columns), None)
                            if vr_key:
                                st.subheader("📐 Proporção Vertical")
                                fig_vr = _create_metric_chart(
                                    metrics_df, vr_key, 'Proporção Vertical', '%', '#e67e22',
                                    x_key=x_key, fill=False, hoverformat='.1f'
                                )
                                if fig_vr:
                                    st.plotly_chart(fig_vr, use_container_width=True)
    
                            # ---- Oscilação Vertical ----
                            vo_key = next((k for k in ('directVerticalOscillation', 'verticalOscillation') if k in metrics_df.columns), None)
                            if vo_key:
                                st.subheader("📊 Oscilação Vertical")
                                fig_vo = _create_metric_chart(
                                    metrics_df, vo_key, 'Oscilação Vertical', 'mm', '#e74c3c',
                                    x_key=x_key, fill=False, hoverformat='.1f'
                                )
                                if fig_vo:
                                    st.plotly_chart(fig_vo, use_container_width=True)
    
                            # ---- Tempo de Contato com o Solo ----
                            gct_key = next((k for k in ('directGroundContactTime', 'groundContactTime') if k in metrics_df.columns), None)
                            if gct_key:
                                st.subheader("🦶 Tempo de Contato c/ Solo")
                                fig_gct = _create_metric_chart(
                                    metrics_df, gct_key, 'Tempo Contato Solo', 'ms', '#c0392b',
                                    x_key=x_key, fill=False, hoverformat='.0f'
                                )
                                if fig_gct:
                                    st.plotly_chart(fig_gct, use_container_width=True)
    
                            # ---- Temperatura ----
                            temp_key = next((k for k in ('directAirTemperature', 'airTemperature') if k in metrics_df.columns), None)
                            if temp_key:
                                st.subheader("🌡️ Temperatura")
                                fig_temp = _create_metric_chart(
                                    metrics_df, temp_key, 'Temperatura', '°C', '#95a5a6',
                                    x_key=x_key, fill=False, hoverformat='.1f'
                                )
                                if fig_temp:
                                    st.plotly_chart(fig_temp, use_container_width=True)
    
                        else:
                            st.info("ℹ️ Métricas detalhadas não disponíveis para esta atividade.")
                            # Fallback: mostrar apenas resumo de FC
                            col_hr1, col_hr2, col_hr3 = st.columns(3)
                            with col_hr1: st.metric("❤️ FC Média", f"{selected['avg_hr']:.0f} bpm")
                            with col_hr2: st.metric("📈 FC Máxima", f"{selected['max_hr']:.0f} bpm")
                            with col_hr3: st.metric("📉 FC Mínima", "—")
    
                else:
                    # ---- FREQUÊNCIA CARDÍACA (não-corrida ou sem cliente) ----
                    st.subheader("❤️ Frequência Cardíaca")
                    hr_data = None
                    if st.session_state.get('garmin_client'):
                        with st.spinner("📡 Carregando dados de frequência cardíaca..."):
                            hr_data = get_activity_hr_details(selected['id'], st.session_state.garmin_client)

                    if hr_data:
                        fig_hr = create_hr_graph(hr_data, selected['duration_min'])
                        if fig_hr:
                            st.plotly_chart(fig_hr, use_container_width=True)
                            df_hr = pd.DataFrame(hr_data)
                            if 'hr' in df_hr.columns:
                                avg_hr_data = df_hr['hr'].mean()
                                max_hr_data = df_hr['hr'].max()
                                min_hr_data = df_hr['hr'].min()
                                max_estimated = 200
                                zona1 = ((df_hr['hr'] < max_estimated * 0.5).sum() / len(df_hr)) * 100
                                zona2 = (((df_hr['hr'] >= max_estimated * 0.5) & (df_hr['hr'] < max_estimated * 0.6)).sum() / len(df_hr)) * 100
                                zona3 = (((df_hr['hr'] >= max_estimated * 0.6) & (df_hr['hr'] < max_estimated * 0.7)).sum() / len(df_hr)) * 100
                                zona4 = (((df_hr['hr'] >= max_estimated * 0.7) & (df_hr['hr'] < max_estimated * 0.85)).sum() / len(df_hr)) * 100
                                zona5 = ((df_hr['hr'] >= max_estimated * 0.85).sum() / len(df_hr)) * 100
                                st.subheader("⚡ Distribuição de Intensidade")
                                col_z1, col_z2, col_z3, col_z4, col_z5 = st.columns(5)
                                with col_z1: st.metric("🔵 Recuperação", f"{zona1:.0f}%")
                                with col_z2: st.metric("🟢 Leve", f"{zona2:.0f}%")
                                with col_z3: st.metric("🟠 Moderada", f"{zona3:.0f}%")
                                with col_z4: st.metric("🔴 Intenso", f"{zona4:.0f}%")
                                with col_z5: st.metric("⚫ Máximo", f"{zona5:.0f}%")
                                col_hr_stats1, col_hr_stats2 = st.columns(2)
                                with col_hr_stats1:
                                    st.info(f"""
                                    **Estatísticas de FC:**
                                    - **FC Mínima:** {min_hr_data:.0f} bpm
                                    - **FC Média:** {avg_hr_data:.0f} bpm
                                    - **FC Máxima:** {max_hr_data:.0f} bpm
                                    - **Amplitude:** {max_hr_data - min_hr_data:.0f} bpm
                                    """)
                                with col_hr_stats2:
                                    st.info(f"""
                                    **Zonas de Treino:**
                                    - 🔵 Recuperação: <{max_estimated*0.5:.0f} bpm
                                    - 🟢 Leve: {max_estimated*0.5:.0f}-{max_estimated*0.6:.0f} bpm
                                    - 🟠 Moderada: {max_estimated*0.6:.0f}-{max_estimated*0.7:.0f} bpm
                                    - 🔴 Intenso: {max_estimated*0.7:.0f}-{max_estimated*0.85:.0f} bpm
                                    - ⚫ Máximo: >{max_estimated*0.85:.0f} bpm
                                    """)
                        else:
                            col_hr1, col_hr2, col_hr3 = st.columns(3)
                            with col_hr1: st.metric("❤️ FC Média", f"{selected['avg_hr']:.0f} bpm")
                            with col_hr2: st.metric("📈 FC Máxima", f"{selected['max_hr']:.0f} bpm")
                            with col_hr3: st.metric("📉 FC Mínima", f"{selected['avg_hr']*0.7:.0f} bpm")
                    else:
                        st.info("ℹ️ Dados detalhados de frequência cardíaca não disponíveis. Exibindo resumo:")
                        col_hr1, col_hr2, col_hr3 = st.columns(3)
                        with col_hr1: st.metric("❤️ FC Média", f"{selected['avg_hr']:.0f} bpm")
                        with col_hr2: st.metric("📈 FC Máxima", f"{selected['max_hr']:.0f} bpm")
                        with col_hr3:
                            est_min_hr = max(selected['avg_hr'] * 0.65, 40)
                            st.metric("📉 FC Estimada (mín)", f"{est_min_hr:.0f} bpm")
        
        else:  # pagina == "📈 Dashboard"
            tab1, tab2, tab3, tab4, tab5, tab_fitness = st.tabs(["📈 Resumo", "🏃 Corridas", "🚴 Ciclismo", "💪 Musculação", "📊 Análises", "🏋️ Fitness"])
        
            with tab1:
                # Distribuição de atividades
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Distribuição por Tipo")
                    dist_data = df_filtered.groupby('type').size()
                    fig_dist = px.pie(
                        values=dist_data.values,
                        names=['🏃 Corrida', '🚴 Ciclismo', '💪 Musculação'],
                        color_discrete_sequence=['#FF6B6B', '#4ECDC4', '#45B7D1']
                    )
                    st.plotly_chart(fig_dist, use_container_width=True)
                
                with col2:
                    st.subheader("Calorias por Tipo")
                    cal_by_type = df_filtered.groupby('type')['calories'].sum()
                    fig_cal = go.Figure(data=[
                        go.Bar(
                            x=['🏃 Corrida', '🚴 Ciclismo', '💪 Musculação'],
                            y=cal_by_type.values,
                            marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1'],
                            text=cal_by_type.values,
                            textposition='auto'
                        )
                    ])
                    fig_cal.update_layout(showlegend=False, height=400)
                    st.plotly_chart(fig_cal, use_container_width=True)
                
                # Timeline de atividades
                st.subheader("Timeline de Atividades")
                df_sorted = df_filtered.sort_values('date')
                fig_timeline = px.bar(
                    df_sorted,
                    x='date',
                    y='calories',
                    color='type',
                    color_discrete_map={'running': '#FF6B6B', 'cycling': '#4ECDC4', 'strength_training': '#45B7D1'},
                    labels={'date': 'Data', 'calories': 'Calorias'},
                    height=400
                )
                st.plotly_chart(fig_timeline, use_container_width=True)
            
            with tab2:
                st.subheader("🏃 Análise de Corridas")
                running_df = df[df['type'] == 'running'].sort_values('date', ascending=False)
                
                if len(running_df) > 0:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total de Corridas", len(running_df))
                    with col2:
                        st.metric("Distância Média", f"{running_df['distance_km'].mean():.2f} km")
                    with col3:
                        ritmo_medio = (running_df['duration_min'] / running_df['distance_km']).mean()
                        st.metric("Ritmo Médio", f"{ritmo_medio:.2f} min/km")
                    with col4:
                        st.metric("Calorias Totais", f"{running_df['calories'].sum():.0f}")
                    
                    # Gráfico de distância por corrida
                    fig_dist = px.bar(
                        running_df,
                        x='date',
                        y='distance_km',
                        color='distance_km',
                        color_continuous_scale='Viridis',
                        title='Distância por Corrida',
                        labels={'distance_km': 'Distância (km)', 'date': 'Data'}
                    )
                    st.plotly_chart(fig_dist, use_container_width=True)
                    
                    # Tabela de corridas
                    st.subheader("Detalhes das Corridas")
                    display_cols = running_df[['date', 'name', 'distance_km', 'duration_min', 'avg_hr', 'max_hr', 'calories']].copy()
                    display_cols['date'] = display_cols['date'].dt.strftime('%d/%m/%Y')
                    display_cols['distance_km'] = display_cols['distance_km'].apply(lambda x: f"{x:.2f} km")
                    display_cols['duration_min'] = display_cols['duration_min'].apply(lambda x: f"{x:.0f} min")
                    display_cols['avg_hr'] = display_cols['avg_hr'].apply(lambda x: f"{x:.0f} bpm")
                    display_cols['max_hr'] = display_cols['max_hr'].apply(lambda x: f"{x:.0f} bpm")
                    display_cols['calories'] = display_cols['calories'].apply(lambda x: f"{x:.0f} kcal")
                    
                    display_cols.columns = ['Data', 'Atividade', 'Distância', 'Duração', 'FC Média', 'FC Máx', 'Calorias']
                    st.dataframe(display_cols, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhuma corrida encontrada para o período selecionado")
            
            with tab3:
                st.subheader("🚴 Análise de Ciclismo")
                cycling_df = df[df['type'] == 'cycling'].sort_values('date', ascending=False)
                
                if len(cycling_df) > 0:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total de Passeios", len(cycling_df))
                    with col2:
                        st.metric("Distância Média", f"{cycling_df['distance_km'].mean():.2f} km")
                    with col3:
                        st.metric("Elevação Total", f"{cycling_df['elevation_gain'].sum():.0f} m")
                    with col4:
                        st.metric("Calorias Totais", f"{cycling_df['calories'].sum():.0f}")
                    
                    # Gráfico de distância vs elevação
                    fig_scatter = px.scatter(
                        cycling_df,
                        x='distance_km',
                        y='elevation_gain',
                        size='calories',
                        color='avg_hr',
                        color_continuous_scale='RdYlGn_r',
                        title='Distância vs Elevação (tamanho = calorias)',
                        labels={'distance_km': 'Distância (km)', 'elevation_gain': 'Elevação (m)', 'avg_hr': 'FC Média'}
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)
                    
                    # Tabela de passeios
                    st.subheader("Detalhes dos Passeios")
                    display_cols = cycling_df[['date', 'name', 'distance_km', 'duration_min', 'elevation_gain', 'avg_hr', 'calories']].copy()
                    display_cols['date'] = display_cols['date'].dt.strftime('%d/%m/%Y')
                    display_cols['distance_km'] = display_cols['distance_km'].apply(lambda x: f"{x:.2f} km")
                    display_cols['duration_min'] = display_cols['duration_min'].apply(lambda x: f"{x:.0f} min")
                    display_cols['elevation_gain'] = display_cols['elevation_gain'].apply(lambda x: f"{x:.0f} m")
                    display_cols['avg_hr'] = display_cols['avg_hr'].apply(lambda x: f"{x:.0f} bpm")
                    display_cols['calories'] = display_cols['calories'].apply(lambda x: f"{x:.0f} kcal")
                    
                    display_cols.columns = ['Data', 'Atividade', 'Distância', 'Duração', 'Elevação', 'FC Média', 'Calorias']
                    st.dataframe(display_cols, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhum passeio de ciclismo encontrado para o período selecionado")
            
            with tab4:
                st.subheader("💪 Análise de Musculação")
                strength_df = df[df['type'] == 'strength_training'].sort_values('date', ascending=False)
                
                if len(strength_df) > 0:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total de Sessões", len(strength_df))
                    with col2:
                        st.metric("Duração Média", f"{strength_df['duration_min'].mean():.0f} min")
                    with col3:
                        st.metric("FC Média", f"{strength_df['avg_hr'].mean():.0f} bpm")
                    with col4:
                        st.metric("Calorias Totais", f"{strength_df['calories'].sum():.0f}")
                    
                    # Gráfico de calorias por sessão
                    fig_strength = px.bar(
                        strength_df,
                        x='date',
                        y='calories',
                        color='duration_min',
                        color_continuous_scale='Blues',
                        title='Calorias por Sessão',
                        labels={'calories': 'Calorias', 'date': 'Data', 'duration_min': 'Duração (min)'}
                    )
                    st.plotly_chart(fig_strength, use_container_width=True)
                    
                    # Tabela de sessões
                    st.subheader("Detalhes das Sessões")
                    display_cols = strength_df[['date', 'name', 'duration_min', 'avg_hr', 'max_hr', 'calories']].copy()
                    display_cols['date'] = display_cols['date'].dt.strftime('%d/%m/%Y')
                    display_cols['duration_min'] = display_cols['duration_min'].apply(lambda x: f"{x:.0f} min")
                    display_cols['avg_hr'] = display_cols['avg_hr'].apply(lambda x: f"{x:.0f} bpm")
                    display_cols['max_hr'] = display_cols['max_hr'].apply(lambda x: f"{x:.0f} bpm")
                    display_cols['calories'] = display_cols['calories'].apply(lambda x: f"{x:.0f} kcal")
                    
                    display_cols.columns = ['Data', 'Atividade', 'Duração', 'FC Média', 'FC Máx', 'Calorias']
                    st.dataframe(display_cols, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhuma sessão de musculação encontrada para o período selecionado")
            
            with tab5:
                st.subheader("📊 Análises Avançadas")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Frequência Cardíaca por Tipo")
                    hr_by_type = df_filtered[df_filtered['avg_hr'] > 0].groupby('type')['avg_hr'].mean()
                    fig_hr = go.Figure(data=[
                        go.Bar(
                            x=['🏃 Corrida', '🚴 Ciclismo', '💪 Musculação'],
                            y=hr_by_type.values,
                            marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1'],
                            text=[f"{x:.0f} bpm" for x in hr_by_type.values],
                            textposition='auto'
                        )
                    ])
                    fig_hr.update_layout(showlegend=False, height=400)
                    st.plotly_chart(fig_hr, use_container_width=True)
                
                with col2:
                    st.subheader("Duração Média por Tipo")
                    duration_by_type = df_filtered.groupby('type')['duration_min'].mean()
                    fig_duration = go.Figure(data=[
                        go.Bar(
                            x=['🏃 Corrida', '🚴 Ciclismo', '💪 Musculação'],
                            y=duration_by_type.values,
                            marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1'],
                            text=[f"{x:.0f} min" for x in duration_by_type.values],
                            textposition='auto'
                        )
                    ])
                    fig_duration.update_layout(showlegend=False, height=400)
                    st.plotly_chart(fig_duration, use_container_width=True)
                
                # Correlação entre métricas
                st.subheader("Correlação: Distância vs Calorias")
                dist_cal_df = df_filtered[df_filtered['distance_km'] > 0].copy()
                if len(dist_cal_df) > 0:
                    fig_corr = px.scatter(
                        dist_cal_df,
                        x='distance_km',
                        y='calories',
                        color='type',
                        size='duration_min',
                        color_discrete_map={'running': '#FF6B6B', 'cycling': '#4ECDC4'},
                        title='Relação entre Distância e Calorias',
                        labels={'distance_km': 'Distância (km)', 'calories': 'Calorias', 'type': 'Tipo'},
                        height=400
                    )
                    st.plotly_chart(fig_corr, use_container_width=True)
                
                # Sumário
                st.subheader("📋 Sumário")
                summary_col1, summary_col2, summary_col3 = st.columns(3)
                
                with summary_col1:
                    cycling_df = df[df['type'] == 'cycling']
                    if len(cycling_df) > 0:
                        max_cycling = cycling_df['distance_km'].max()
                    else:
                        max_cycling = 0
                    
                    running_df = df[df['type'] == 'running']
                    if len(running_df) > 0:
                        max_running = running_df['distance_km'].max()
                    else:
                        max_running = 0
                    
                    st.info(f"""
                    **Maiores Distâncias:**
                    - Ciclismo: {max_cycling:.2f} km
                    - Corrida: {max_running:.2f} km
                    """)
                
                with summary_col2:
                    st.success(f"""
                    **Calorias Queimadas:**
                    - 🏃 Corridas: {df[df['type']=='running']['calories'].sum():.0f} kcal
                    - 🚴 Ciclismo: {df[df['type']=='cycling']['calories'].sum():.0f} kcal
                    - 💪 Musculação: {df[df['type']=='strength_training']['calories'].sum():.0f} kcal
                    """)
                
                with summary_col3:
                    st.warning(f"""
                    **Consistência:**
                    - Total de atividades: {len(df)}
                    - Dias ativos: {df['date'].nunique()}
                    - Média: {len(df)/max(df['date'].nunique(), 1):.1f} ativ./dia
                    """)

            with tab_fitness:
                st.subheader("🏋️ Performance Management Chart (PMC)")
                st.markdown(
                    "Modelo baseado no **intervals.icu**: "
                    "**CTL** (Condicionamento, EWMA 42 dias) | "
                    "**ATL** (Fadiga, EWMA 7 dias) | "
                    "**TSB** (Estado Físico = CTL − ATL)"
                )

                pmc_df = calculate_pmc(df)

                if pmc_df.empty:
                    st.info("ℹ️ Dados insuficientes para calcular o PMC.")
                else:
                    fig_pmc = create_pmc_chart(pmc_df)
                    if fig_pmc:
                        st.plotly_chart(fig_pmc, use_container_width=True)

                    fig_tsb_hist = create_tsb_histogram(pmc_df)
                    if fig_tsb_hist:
                        st.plotly_chart(fig_tsb_hist, use_container_width=True)

                    # Valores mais recentes
                    latest = pmc_df.iloc[-1]
                    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
                    with col_f1:
                        st.metric("💙 Condicionamento (CTL)", f"{latest['ctl']:.1f}")
                    with col_f2:
                        st.metric("💜 Fadiga (ATL)", f"{latest['atl']:.1f}")
                    with col_f3:
                        tsb = latest['tsb']
                        delta_color = "normal"
                        if tsb > 5:
                            estado = "Descansado"
                        elif tsb > -10:
                            estado = "Mantendo"
                        elif tsb > -30:
                            estado = "Evoluindo"
                        else:
                            estado = "Alto Risco"
                        st.metric("🩶 Estado Físico (TSB)", f"{tsb:.1f}", delta=estado)
                    with col_f4:
                        # Trimp dos últimos 7 dias
                        pmc_7d = pmc_df[pmc_df['date'] >= pmc_df['date'].max() - pd.Timedelta(days=6)]
                        trimp_7d = pmc_7d['trimp'].sum() if 'trimp' in pmc_7d.columns else 0
                        st.metric("📅 Carga últimos 7 dias", f"{trimp_7d:.0f} TRIMP")

                    st.divider()

                    # Legenda de zonas
                    st.markdown("**Zonas de Estado Físico (TSB):**")
                    zone_col1, zone_col2, zone_col3, zone_col4, zone_col5 = st.columns(5)
                    with zone_col1:
                        st.info("🔵 **Descansado**\nTSB > 25")
                    with zone_col2:
                        st.success("🟢 **Adaptando**\n5 < TSB ≤ 25")
                    with zone_col3:
                        st.markdown("⬜ **Mantendo**\n−10 < TSB ≤ 5")
                    with zone_col4:
                        st.success("🟩 **Evoluindo**\n−30 < TSB ≤ −10")
                    with zone_col5:
                        st.error("🔴 **Alto Risco**\nTSB ≤ −30")

        st.divider()
        st.markdown("---")
        st.markdown("📊 Dashboard criado com Streamlit + Garmin Connect | Conexão em tempo real")

else:
    st.info("👈 Faça login com suas credenciais do Garmin Connect na barra lateral")
