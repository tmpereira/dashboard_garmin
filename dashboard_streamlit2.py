import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
from garminconnect import Garmin
import logging
import math

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
    .zone-card {
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 8px;
        font-weight: 500;
    }
    .test-banner {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        border: 1px solid #e94560;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# FUNÇÕES DE AUTENTICAÇÃO E CONEXÃO GARMIN
# ============================================

@st.cache_resource
def init_garmin_session():
    return None

def authenticate_garmin(email, password):
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
    local = activity.get('startTimeLocal')
    if local:
        try:
            return pd.to_datetime(local)
        except Exception:
            pass
    gmt = activity.get('startTimeGMT')
    if gmt:
        try:
            return pd.to_datetime(gmt)
        except Exception:
            pass
    ts = activity.get('startTimeInSeconds')
    if ts and ts > 0:
        try:
            return pd.to_datetime(ts, unit='s')
        except Exception:
            pass
    return pd.NaT


def get_activities_from_garmin(days=30):
    try:
        if not st.session_state.get('garmin_client'):
            st.error("❌ Não conectado ao Garmin. Faça login primeiro.")
            return pd.DataFrame()
        
        client = st.session_state.garmin_client
        activities = client.get_activities(0, 500)
        
        data = []
        # Debug: logar chaves da primeira atividade para entender a estrutura
        if activities:
            first_keys = list(activities[0].keys())
            logging.info(f"Chaves da primeira atividade: {first_keys}")
            # Buscar qualquer campo que contenha 'hr' ou 'heart'
            hr_keys = [k for k in first_keys if 'hr' in k.lower() or 'heart' in k.lower()]
            logging.info(f"Campos de FC encontrados: {hr_keys}")
        
        for activity in activities:
            try:
                distance_km = activity.get('distance', 0) / 1000 if activity.get('distance') else 0
                duration_min = activity.get('duration', 0) / 60 if activity.get('duration') else 0
                
                # FC: tentar múltiplos campos possíveis
                avg_hr = (
                    activity.get('averageHR') or
                    activity.get('avgHr') or
                    activity.get('averageHeartRateInBeatsPerMinute') or
                    activity.get('avgHeartRate') or
                    0
                )
                max_hr = (
                    activity.get('maxHR') or
                    activity.get('maxHr') or
                    activity.get('maxHeartRateInBeatsPerMinute') or
                    activity.get('maxHeartRate') or
                    0
                )
                
                data.append({
                    'id': activity.get('activityId'),
                    'name': activity.get('activityName', 'Sem nome'),
                    'type': activity.get('activityType', {}).get('typeKey', 'unknown'),
                    'date': _parse_activity_date(activity),
                    'distance_km': distance_km,
                    'duration_min': duration_min,
                    'calories': activity.get('calories', 0),
                    'avg_hr': avg_hr,
                    'max_hr': max_hr,
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
            df = df.dropna(subset=['date'])
            
            # Debug: mostrar status dos campos de FC
            hr_count = (pd.to_numeric(df['avg_hr'], errors='coerce') > 0).sum()
            logging.info(f"Atividades com FC > 0: {hr_count}/{len(df)}")
            if hr_count == 0 and activities:
                # Logar raw data da primeira atividade para diagnóstico
                first = activities[0]
                hr_related = {k: v for k, v in first.items() if 'hr' in k.lower() or 'heart' in k.lower() or 'HR' in k}
                logging.info(f"Campos HR raw da primeira atividade: {hr_related}")
                st.sidebar.warning(f"⚠️ Debug FC: 0/{len(df)} atividades com FC. Campos HR encontrados: {list(hr_related.keys())}")
            
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

# ============================================
# FUNÇÕES PMC
# ============================================

def calculate_pmc(df):
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df['date_only'] = df['date'].dt.normalize()

    fc_max_ref = 190.0
    type_factor = {'running': 1.0, 'cycling': 0.85, 'strength_training': 0.65, 'other': 0.5}

    def trimp(row):
        avg_hr = row['avg_hr'] if row['avg_hr'] > 0 else fc_max_ref * 0.7
        hr_ratio = min(avg_hr / fc_max_ref, 1.0)
        factor = type_factor.get(row['type'], 0.7)
        return row['duration_min'] * hr_ratio * factor

    df['trimp'] = df.apply(trimp, axis=1)

    daily = df.groupby('date_only')['trimp'].sum().reset_index()
    daily.columns = ['date', 'trimp']

    date_range = pd.date_range(daily['date'].min(), daily['date'].max(), freq='D')
    daily = daily.set_index('date').reindex(date_range, fill_value=0).reset_index()
    daily.columns = ['date', 'trimp']

    ctl_alpha = 2 / (42 + 1)
    atl_alpha = 2 / (7 + 1)

    ctl_list, atl_list, tsb_list = [], [], []
    ctl, atl = 0.0, 0.0
    for _, row in daily.iterrows():
        tsb_list.append(ctl - atl)
        ctl = ctl + ctl_alpha * (row['trimp'] - ctl)
        atl = atl + atl_alpha * (row['trimp'] - atl)
        ctl_list.append(ctl)
        atl_list.append(atl)

    daily['ctl'] = ctl_list
    daily['atl'] = atl_list
    daily['tsb'] = tsb_list

    return daily


def create_pmc_chart(pmc_df):
    if pmc_df.empty:
        return None

    fig = go.Figure()

    fig.add_hrect(y0=-100, y1=-30, fillcolor="red",   opacity=0.1, line_width=0, annotation_text="Alto Risco")
    fig.add_hrect(y0=-30,  y1=-10, fillcolor="green", opacity=0.1, line_width=0, annotation_text="Evoluindo")
    fig.add_hrect(y0=-10,  y1=5,   fillcolor="gray",  opacity=0.1, line_width=0, annotation_text="Manutenção")

    fig.add_trace(go.Scatter(
        x=pmc_df['date'], y=pmc_df['tsb'],
        fill='tozeroy',
        name='Estado Físico (TSB)',
        line=dict(color='lightgray', width=1),
        opacity=0.5
    ))

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
    if pmc_df.empty:
        return None

    df60 = pmc_df[pmc_df['date'] >= pmc_df['date'].max() - pd.Timedelta(days=59)].copy()

    def tsb_color(v):
        if v > 5:    return '#3498db'
        if v > -10:  return '#95a5a6'
        if v > -30:  return '#2ecc71'
        return '#e74c3c'

    colors = [tsb_color(v) for v in df60['tsb']]

    fig = go.Figure()

    fig.add_hrect(y0=-100, y1=-30, fillcolor='red',   opacity=0.1, line_width=0)
    fig.add_hrect(y0=-30,  y1=-10, fillcolor='green', opacity=0.1, line_width=0)
    fig.add_hrect(y0=-10,  y1=5,   fillcolor='gray',  opacity=0.1, line_width=0)

    fig.add_trace(go.Bar(
        x=df60['date'],
        y=df60['tsb'],
        marker_color=colors,
        name='TSB diário',
        showlegend=False,
        hovertemplate='<b>%{x|%d/%m/%Y}</b><br>TSB: %{y:.1f}<extra></extra>'
    ))

    fig.add_hline(y=0, line_color='white', line_width=1, line_dash='dash')

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


# ============================================
# NOVAS FUNÇÕES - ZONAS & PACE
# ============================================

def find_last_test_activity(df):
    """
    Busca a atividade mais recente cujo nome começa com [teste] (case-insensitive).
    Retorna a linha do DataFrame ou None.
    """
    if df.empty:
        return None
    
    mask = df['name'].str.lower().str.contains(r'\[teste\]', regex=True, na=False)
    test_df = df[mask].sort_values('date', ascending=False)
    
    if test_df.empty:
        return None
    
    return test_df.iloc[0]


def pace_to_seconds(pace_min_km):
    """Converte pace em min/km para segundos/km"""
    return pace_min_km * 60


def seconds_to_pace_str(seconds_per_km):
    """Converte segundos/km para string 'M:SS /km'"""
    if seconds_per_km <= 0:
        return "—"
    m = int(seconds_per_km // 60)
    s = int(seconds_per_km % 60)
    return f"{m}:{s:02d} /km"


def calculate_vo2max_from_1km(duration_seconds, distance_m=1000):
    """
    Estima VO2max a partir do tempo no 1km usando a fórmula de Daniels/Jones.
    vVO2max ≈ velocidade máxima sustentável por ~6-8 min.
    Para 1km: ajustamos pela fração do VO2max utilizada (~0.97).
    """
    if duration_seconds <= 0:
        return None
    
    speed_ms = distance_m / duration_seconds  # m/s
    speed_m_min = speed_ms * 60              # m/min
    
    # Custo de O2 da corrida (fórmula ACSM): VO2 = 0.2*v + 0.9*v*grade + 3.5
    # Para corrida plana: VO2max_utilizado = 0.2 * speed_m_min + 3.5
    vo2_used = 0.2 * speed_m_min + 3.5
    
    # No 1km (~4-6 min) usa-se ~97% do VO2max
    fraction_vo2max = 0.97
    vo2max = vo2_used / fraction_vo2max
    
    return round(vo2max, 1)


def calculate_training_zones(duration_1km_seconds, max_hr=None):
    """
    Calcula as zonas de treino baseadas no tempo do 1km.
    Retorna lista de dicionários com info de cada zona.
    
    Baseado no modelo de Jack Daniels (VDOT) adaptado:
    - vVO2max = velocidade do 1km (aprox.)
    - Z1 Recuperação:    55-65% vVO2max
    - Z2 Base Aeróbica:  65-75% vVO2max  
    - Z3 Tempo/Limiar:   83-88% vVO2max
    - Z4 Intervalado:    95-100% vVO2max
    - Z5 Repetições:     105-115% vVO2max
    """
    if duration_1km_seconds <= 0:
        return []
    
    # Pace base (segundos/km)
    base_pace_sec = duration_1km_seconds  # pace do 1km = seg/km
    
    # Velocidade base em m/s
    base_speed = 1000 / duration_1km_seconds
    
    # VO2max estimado
    vo2max = calculate_vo2max_from_1km(duration_1km_seconds)
    
    # FC por zona (se tiver FCmax real, usa; senão estima)
    if max_hr and max_hr > 0:
        fcmax = max_hr
    else:
        fcmax = 195  # estimativa conservadora para corredores ativos
    
    zones = [
        {
            'zona': 'Z1',
            'nome': 'Recuperação',
            'emoji': '🔵',
            'cor': '#3498db',
            'bg': 'rgba(52,152,219,0.15)',
            'pct_min': 0.55,
            'pct_max': 0.65,
            'fc_pct_min': 0.50,
            'fc_pct_max': 0.60,
            'descricao': 'Corrida muito leve, conversação fácil',
            'uso': 'Recuperação ativa, aquecimento, desaquecimento',
            'exemplo': '20-40 min contínuos no dia seguinte a treino intenso',
        },
        {
            'zona': 'Z2',
            'nome': 'Base Aeróbica',
            'emoji': '🟢',
            'cor': '#2ecc71',
            'bg': 'rgba(46,204,113,0.15)',
            'pct_min': 0.65,
            'pct_max': 0.75,
            'fc_pct_min': 0.60,
            'fc_pct_max': 0.70,
            'descricao': 'Corrida confortável, consegue falar frases curtas',
            'uso': 'Volume base, longas, fundação aeróbica',
            'exemplo': '45-90 min (treino mais importante da semana)',
        },
        {
            'zona': 'Z3',
            'nome': 'Limiar / Tempo',
            'emoji': '🟡',
            'cor': '#f39c12',
            'bg': 'rgba(243,156,18,0.15)',
            'pct_min': 0.83,
            'pct_max': 0.88,
            'fc_pct_min': 0.78,
            'fc_pct_max': 0.85,
            'descricao': 'Desconfortável mas controlado, fala palavras isoladas',
            'uso': 'Aumentar limiar anaeróbico, corridas Tempo',
            'exemplo': '20-40 min contínuos ou 2×15 min c/ 3 min descanso',
        },
        {
            'zona': 'Z4',
            'nome': 'Intervalado (VO₂max)',
            'emoji': '🟠',
            'cor': '#e67e22',
            'bg': 'rgba(230,126,34,0.15)',
            'pct_min': 0.95,
            'pct_max': 1.00,
            'fc_pct_min': 0.88,
            'fc_pct_max': 0.95,
            'descricao': 'Muito intenso, difícil manter conversa',
            'uso': 'Desenvolver VO₂max, potência aeróbica',
            'exemplo': '5×1000m ou 6×800m c/ descanso igual ao esforço',
        },
        {
            'zona': 'Z5',
            'nome': 'Máximo / Repetições',
            'emoji': '🔴',
            'cor': '#e74c3c',
            'bg': 'rgba(231,76,60,0.15)',
            'pct_min': 1.05,
            'pct_max': 1.15,
            'fc_pct_min': 0.95,
            'fc_pct_max': 1.00,
            'descricao': 'Sprint, impossível manter por mais de 1-2 min',
            'uso': 'Velocidade pura, neuromusculação',
            'exemplo': '10×200m ou 6×300m c/ descanso longo (3-5 min)',
        },
    ]
    
    for z in zones:
        # Pace: zona mais lenta = % menor da velocidade → pace MAIOR (mais lento)
        # Para Z1 (55-65% da velocidade do 1km):
        #   velocidade_zona = base_speed * pct
        #   pace_zona = 1000 / velocidade_zona
        speed_min = base_speed * z['pct_min']  # m/s mais lento da zona
        speed_max = base_speed * z['pct_max']  # m/s mais rápido da zona
        
        pace_min_sec = 1000 / speed_max  # pace mais rápido (velocidade maior)
        pace_max_sec = 1000 / speed_min  # pace mais lento (velocidade menor)
        
        z['pace_min_str'] = seconds_to_pace_str(pace_min_sec)
        z['pace_max_str'] = seconds_to_pace_str(pace_max_sec)
        z['pace_alvo_str'] = f"{z['pace_min_str']} – {z['pace_max_str']}"
        
        z['fc_min'] = int(fcmax * z['fc_pct_min'])
        z['fc_max'] = int(fcmax * z['fc_pct_max'])
        z['fc_str'] = f"{z['fc_min']} – {z['fc_max']} bpm"
        
        # Guardar velocidade em km/h para referência
        z['vel_min_kmh'] = round(speed_min * 3.6, 1)
        z['vel_max_kmh'] = round(speed_max * 3.6, 1)
    
    return zones, vo2max


def classify_run_in_zone(avg_pace_sec_per_km, zones):
    """
    Dado um pace médio (seg/km), retorna qual zona a corrida está.
    """
    if not zones or avg_pace_sec_per_km <= 0:
        return None
    
    for z in reversed(zones):  # do mais lento para o mais rápido
        speed_ms = 1000 / avg_pace_sec_per_km
        base_speed_ref = 1000 / zones[3]['pace_min_str']  # referência Z4
        # Verificar se o pace cai dentro da faixa da zona
        pace_min_sec = float('inf')
        pace_max_sec = float('inf')
        
        try:
            parts_min = z['pace_min_str'].replace(' /km', '').split(':')
            pace_min_sec = int(parts_min[0]) * 60 + int(parts_min[1])
            parts_max = z['pace_max_str'].replace(' /km', '').split(':')
            pace_max_sec = int(parts_max[0]) * 60 + int(parts_max[1])
        except:
            continue
        
        if pace_min_sec <= avg_pace_sec_per_km <= pace_max_sec:
            return z
    
    return None


def analyze_recent_runs_by_zone(df, zones, test_pace_sec):
    """
    Analisa corridas recentes e classifica por zona baseado no pace médio.
    """
    if df.empty or not zones:
        return pd.DataFrame()
    
    running_df = df[df['type'] == 'running'].copy()
    if running_df.empty:
        return pd.DataFrame()
    
    # Calcular pace médio de cada corrida
    running_df = running_df[
        (running_df['distance_km'] > 0) & (running_df['duration_min'] > 0)
    ].copy()
    
    running_df['pace_sec_km'] = (running_df['duration_min'] * 60) / running_df['distance_km']
    
    # Classificar zona
    def get_zone_name(pace_sec):
        for z in zones:
            try:
                parts_min = z['pace_min_str'].replace(' /km', '').split(':')
                pace_min_sec = int(parts_min[0]) * 60 + int(parts_min[1])
                parts_max = z['pace_max_str'].replace(' /km', '').split(':')
                pace_max_sec = int(parts_max[0]) * 60 + int(parts_max[1])
                if pace_min_sec <= pace_sec <= pace_max_sec:
                    return f"{z['emoji']} {z['nome']}"
            except:
                continue
        if pace_sec > 0:
            # Verificar se é mais lento que Z1 ou mais rápido que Z5
            try:
                z1_max = zones[0]['pace_max_str'].replace(' /km', '').split(':')
                z1_max_sec = int(z1_max[0]) * 60 + int(z1_max[1])
                if pace_sec > z1_max_sec:
                    return "🚶 Abaixo Z1"
                z5_min = zones[4]['pace_min_str'].replace(' /km', '').split(':')
                z5_min_sec = int(z5_min[0]) * 60 + int(z5_min[1])
                if pace_sec < z5_min_sec:
                    return "⚡ Acima Z5"
            except:
                pass
        return "❓ Não classificado"
    
    running_df['zona_treino'] = running_df['pace_sec_km'].apply(get_zone_name)
    running_df['pace_str'] = running_df['pace_sec_km'].apply(seconds_to_pace_str)
    
    return running_df[['date', 'name', 'distance_km', 'duration_min', 'pace_str', 'zona_treino', 'avg_hr']].copy()


def create_zone_distribution_chart(zone_analysis_df):
    """Gráfico de pizza mostrando distribuição de treinos por zona"""
    if zone_analysis_df.empty:
        return None
    
    zone_counts = zone_analysis_df['zona_treino'].value_counts()
    
    colors_map = {
        '🔵 Recuperação': '#3498db',
        '🟢 Base Aeróbica': '#2ecc71',
        '🟡 Limiar / Tempo': '#f39c12',
        '🟠 Intervalado (VO₂max)': '#e67e22',
        '🔴 Máximo / Repetições': '#e74c3c',
        '🚶 Abaixo Z1': '#95a5a6',
        '⚡ Acima Z5': '#8e44ad',
    }
    
    colors = [colors_map.get(z, '#bdc3c7') for z in zone_counts.index]
    
    fig = go.Figure(data=[go.Pie(
        labels=zone_counts.index,
        values=zone_counts.values,
        marker_colors=colors,
        hole=0.4,
        textinfo='label+percent',
        hovertemplate='<b>%{label}</b><br>%{value} corridas (%{percent})<extra></extra>'
    )])
    
    fig.update_layout(
        title='<b>📊 Distribuição de Corridas por Zona</b><br><sub>Baseado no pace médio de cada corrida</sub>',
        template='plotly_dark',
        height=400,
        showlegend=False,
    )
    
    return fig


def create_pace_evolution_chart(df, zones):
    """Gráfico de evolução do pace ao longo do tempo com faixas de zona"""
    running_df = df[df['type'] == 'running'].copy()
    if running_df.empty or not zones:
        return None
    
    running_df = running_df[
        (running_df['distance_km'] > 0.5) & (running_df['duration_min'] > 0)
    ].copy()
    running_df['pace_sec_km'] = (running_df['duration_min'] * 60) / running_df['distance_km']
    running_df = running_df.sort_values('date')
    
    fig = go.Figure()
    
    # Adicionar faixas de zona como áreas horizontais
    zone_colors = ['#3498db', '#2ecc71', '#f39c12', '#e67e22', '#e74c3c']
    for i, z in enumerate(zones):
        try:
            parts_min = z['pace_min_str'].replace(' /km', '').split(':')
            pace_min_sec = int(parts_min[0]) * 60 + int(parts_min[1])
            parts_max = z['pace_max_str'].replace(' /km', '').split(':')
            pace_max_sec = int(parts_max[0]) * 60 + int(parts_max[1])
            
            fig.add_hrect(
                y0=pace_min_sec, y1=pace_max_sec,
                fillcolor=zone_colors[i], opacity=0.12, line_width=0,
                annotation_text=f"{z['emoji']} {z['zona']}",
                annotation_position="left",
                annotation=dict(font=dict(size=10))
            )
        except:
            continue
    
    # Linha de pace
    fig.add_trace(go.Scatter(
        x=running_df['date'],
        y=running_df['pace_sec_km'],
        mode='lines+markers',
        name='Pace médio',
        line=dict(color='white', width=2),
        marker=dict(size=6, color='white'),
        hovertemplate='<b>%{x|%d/%m/%Y}</b><br>Pace: %{customdata}<extra></extra>',
        customdata=[seconds_to_pace_str(p) for p in running_df['pace_sec_km']]
    ))
    
    # Média móvel 7 corridas
    if len(running_df) >= 3:
        running_df['pace_ma'] = running_df['pace_sec_km'].rolling(min(7, len(running_df)), min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=running_df['date'],
            y=running_df['pace_ma'],
            mode='lines',
            name='Tendência (7 corridas)',
            line=dict(color='#f39c12', width=3, dash='dash'),
            hovertemplate='<b>Tendência</b><br>%{x|%d/%m/%Y}<br>Pace: %{customdata}<extra></extra>',
            customdata=[seconds_to_pace_str(p) for p in running_df['pace_ma']]
        ))
    
    # Inverter eixo Y (pace menor = mais rápido = cima)
    all_paces = running_df['pace_sec_km'].dropna()
    y_min = all_paces.min() * 0.95
    y_max = all_paces.max() * 1.05
    
    # Customizar ticks do eixo Y para mostrar pace
    tick_vals = list(range(int(y_min // 30) * 30, int(y_max // 30 + 2) * 30, 30))
    tick_text = [seconds_to_pace_str(v) for v in tick_vals]
    
    fig.update_layout(
        title='<b>📈 Evolução do Pace ao Longo do Tempo</b><br><sub>Com faixas de zona baseadas no seu teste</sub>',
        xaxis_title='Data',
        yaxis_title='Pace (min/km)',
        yaxis=dict(
            range=[y_max, y_min],  # invertido
            tickvals=tick_vals,
            ticktext=tick_text,
        ),
        template='plotly_dark',
        height=500,
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
    )
    
    return fig


# ============================================
# NOVAS FUNÇÕES - VO2MAX TREND
# ============================================

@st.cache_data(ttl=3600)
def get_vo2max_trend(_client, weeks=24):
    """Busca tendência de VO2max do Garmin"""
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(weeks=weeks)).strftime('%Y-%m-%d')
        data = _client.get_vo2max_trend(start_date, end_date)
        return data
    except Exception as e:
        return None


def create_vo2max_chart(vo2max_data):
    """Cria gráfico de evolução do VO2max"""
    if not vo2max_data:
        return None
    
    try:
        records = []
        if isinstance(vo2max_data, list):
            for item in vo2max_data:
                if isinstance(item, dict):
                    date = item.get('calendarDate') or item.get('date')
                    val = item.get('vo2MaxPreciseValue') or item.get('vo2Max') or item.get('value')
                    if date and val:
                        records.append({'date': pd.to_datetime(date), 'vo2max': float(val)})
        
        if not records:
            return None
        
        df_vo2 = pd.DataFrame(records).sort_values('date')
        
        fig = go.Figure()
        
        # Faixas de classificação (homens 30-39 anos como referência)
        classifications = [
            (0, 35, '#e74c3c', 'Fraco'),
            (35, 42, '#e67e22', 'Razoável'),
            (42, 48, '#f39c12', 'Bom'),
            (48, 55, '#2ecc71', 'Excelente'),
            (55, 80, '#3498db', 'Superior'),
        ]
        
        for v_min, v_max, color, label in classifications:
            fig.add_hrect(
                y0=v_min, y1=v_max,
                fillcolor=color, opacity=0.1, line_width=0,
                annotation_text=label,
                annotation_position="right",
                annotation=dict(font=dict(size=10))
            )
        
        fig.add_trace(go.Scatter(
            x=df_vo2['date'],
            y=df_vo2['vo2max'],
            mode='lines+markers',
            name='VO₂max',
            line=dict(color='#3498db', width=3),
            marker=dict(size=7, color='#3498db'),
            fill='tozeroy',
            fillcolor='rgba(52,152,219,0.15)',
            hovertemplate='<b>%{x|%d/%m/%Y}</b><br>VO₂max: %{y:.1f} ml/kg/min<extra></extra>'
        ))
        
        # Anotação do valor mais recente
        latest = df_vo2.iloc[-1]
        fig.add_annotation(
            x=latest['date'], y=latest['vo2max'],
            text=f"<b>{latest['vo2max']:.1f}</b>",
            showarrow=True, arrowhead=2,
            font=dict(size=14, color='white'),
            bgcolor='#3498db', bordercolor='white',
            borderwidth=1
        )
        
        fig.update_layout(
            title='<b>📈 Evolução do VO₂max</b><br><sub>Estimativa Garmin ao longo do tempo</sub>',
            xaxis_title='Data',
            yaxis_title='VO₂max (ml/kg/min)',
            template='plotly_dark',
            height=420,
            hovermode='x unified',
        )
        
        return fig
    except Exception:
        return None


# ============================================
# NOVAS FUNÇÕES - EFICIÊNCIA DE CORRIDA
# ============================================

def calculate_running_economy(df):
    """
    Calcula índice de eficiência de corrida mensal:
    Efficiency Factor (EF) = velocidade_m_min / FC_média
    Quanto maior o EF, mais eficiente (mais rápido com menos FC).
    """
    running_df = df[df['type'] == 'running'].copy()
    if running_df.empty:
        return pd.DataFrame()

    # Garantir tipos numéricos
    running_df['distance_km'] = pd.to_numeric(running_df['distance_km'], errors='coerce').fillna(0)
    running_df['duration_min'] = pd.to_numeric(running_df['duration_min'], errors='coerce').fillna(0)
    running_df['avg_hr'] = pd.to_numeric(running_df['avg_hr'], errors='coerce').fillna(0)

    running_df = running_df[
        (running_df['distance_km'] > 0.5) &
        (running_df['duration_min'] > 0) &
        (running_df['avg_hr'] > 50)   # FC mínima razoável
    ].copy()

    if running_df.empty:
        return pd.DataFrame()
    
    # Velocidade em m/min
    running_df['speed_m_min'] = (running_df['distance_km'] * 1000) / running_df['duration_min']
    
    # Efficiency Factor = velocidade / FC média
    running_df['ef'] = running_df['speed_m_min'] / running_df['avg_hr']
    
    # Agrupar por mês
    running_df['month'] = running_df['date'].dt.to_period('M')
    monthly = running_df.groupby('month').agg(
        ef_mean=('ef', 'mean'),
        n_runs=('ef', 'count'),
        avg_hr=('avg_hr', 'mean'),
        avg_distance=('distance_km', 'mean')
    ).reset_index()
    
    monthly['month_dt'] = monthly['month'].dt.to_timestamp()
    
    return monthly


def create_running_economy_chart(economy_df):
    """Gráfico de eficiência de corrida ao longo dos meses"""
    if economy_df.empty:
        return None
    
    fig = go.Figure()
    
    # EF mensal como barras
    fig.add_trace(go.Bar(
        x=economy_df['month_dt'],
        y=economy_df['ef_mean'],
        name='Efficiency Factor',
        marker_color='#1abc9c',
        opacity=0.8,
        hovertemplate='<b>%{x|%b/%Y}</b><br>EF: %{y:.3f}<br>%{customdata} corridas<extra></extra>',
        customdata=economy_df['n_runs']
    ))
    
    # Linha de tendência
    if len(economy_df) >= 3:
        economy_df['ef_trend'] = economy_df['ef_mean'].rolling(3, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=economy_df['month_dt'],
            y=economy_df['ef_trend'],
            mode='lines',
            name='Tendência (3 meses)',
            line=dict(color='#e74c3c', width=3, dash='dash'),
        ))
    
    fig.update_layout(
        title='<b>🏃 Índice de Eficiência de Corrida (EF)</b><br>'
              '<sub>EF = Velocidade ÷ FC Média — quanto maior, mais eficiente</sub>',
        xaxis_title='Mês',
        yaxis_title='Efficiency Factor',
        template='plotly_dark',
        height=380,
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
    )
    
    return fig


# ============================================
# NOVAS FUNÇÕES - CORRELAÇÃO SONO × DESEMPENHO
# ============================================

@st.cache_data(ttl=3600)
def get_sleep_data_range(_client, days=60):
    """Busca dados de sono dos últimos N dias"""
    try:
        records = []
        end = datetime.now()
        for i in range(days):
            date = (end - timedelta(days=i)).strftime('%Y-%m-%d')
            try:
                sleep = _client.get_sleep_data(date)
                if sleep and isinstance(sleep, dict):
                    daily = sleep.get('dailySleepDTO', sleep)
                    duration_sec = daily.get('sleepTimeSeconds') or daily.get('totalSleepSeconds', 0)
                    score = daily.get('sleepScores', {})
                    overall = score.get('overall', {}).get('value') if isinstance(score, dict) else None
                    
                    if duration_sec and duration_sec > 0:
                        records.append({
                            'date': pd.to_datetime(date),
                            'sleep_hours': duration_sec / 3600,
                            'sleep_score': overall,
                        })
            except Exception:
                continue
        
        if records:
            return pd.DataFrame(records)
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def create_sleep_performance_chart(sleep_df, running_df):
    """
    Correlaciona qualidade do sono do dia anterior com o pace do dia seguinte.
    """
    if sleep_df.empty or running_df.empty:
        return None
    
    try:
        running_df = running_df[
            (running_df['distance_km'] > 1) & (running_df['duration_min'] > 0)
        ].copy()
        running_df['pace_sec_km'] = (running_df['duration_min'] * 60) / running_df['distance_km']
        running_df['date_only'] = running_df['date'].dt.normalize()
        
        sleep_df['date_next'] = sleep_df['date'] + pd.Timedelta(days=1)
        
        merged = pd.merge(
            running_df[['date_only', 'pace_sec_km', 'distance_km', 'avg_hr', 'name']],
            sleep_df[['date_next', 'sleep_hours', 'sleep_score']],
            left_on='date_only',
            right_on='date_next',
            how='inner'
        )
        
        if merged.empty or len(merged) < 4:
            return None
        
        merged['pace_min_km'] = merged['pace_sec_km'] / 60
        
        fig = go.Figure()
        
        # Scatter: horas de sono vs pace
        scatter_color = merged['sleep_score'] if merged['sleep_score'].notna().sum() > 3 else merged['sleep_hours']
        
        fig.add_trace(go.Scatter(
            x=merged['sleep_hours'],
            y=merged['pace_min_km'],
            mode='markers',
            marker=dict(
                size=merged['distance_km'].clip(3, 20),
                color=scatter_color,
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title='Score sono' if merged['sleep_score'].notna().sum() > 3 else 'Horas sono'),
                line=dict(color='white', width=0.5)
            ),
            text=merged['name'],
            hovertemplate='<b>%{text}</b><br>Sono: %{x:.1f}h<br>Pace: %{y:.2f} min/km<extra></extra>',
            name='Corridas'
        ))
        
        # Linha de tendência (regressão linear simples)
        if len(merged) >= 4:
            x = merged['sleep_hours'].values
            y = merged['pace_min_km'].values
            n = len(x)
            slope = (n * (x * y).sum() - x.sum() * y.sum()) / (n * (x**2).sum() - x.sum()**2)
            intercept = (y.sum() - slope * x.sum()) / n
            
            x_line = [x.min(), x.max()]
            y_line = [slope * xi + intercept for xi in x_line]
            
            fig.add_trace(go.Scatter(
                x=x_line, y=y_line,
                mode='lines',
                name='Tendência',
                line=dict(color='#e74c3c', width=2, dash='dash'),
            ))
            
            trend_text = "🟢 Mais sono → Pace melhor" if slope < 0 else "🔴 Mais sono → Pace pior (ruído ou dados insuficientes)"
        else:
            trend_text = ""
        
        fig.update_layout(
            title=f'<b>🛌 Sono do Dia Anterior vs Pace da Corrida</b><br><sub>{trend_text}</sub>',
            xaxis_title='Horas de Sono (noite anterior)',
            yaxis_title='Pace médio (min/km — menor = mais rápido)',
            yaxis=dict(autorange='reversed'),
            template='plotly_dark',
            height=450,
            hovermode='closest',
        )
        
        return fig, merged
    except Exception as e:
        return None


# ============================================
# FUNÇÕES ORIGINAIS DE DETALHE DE ATIVIDADE
# ============================================

@st.cache_data(ttl=3600)
def get_activity_hr_details(activity_id, _client):
    if not activity_id:
        return None
    try:
        activity_details = _client.get_activity_details(activity_id)
        if not activity_details:
            return None
        
        hr_data = []
        metric_descriptors = activity_details.get('metricDescriptors', [])
        detail_metrics = activity_details.get('activityDetailMetrics', [])
        
        if metric_descriptors and detail_metrics:
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
                    
                    if time_index is not None and len(metrics) > time_index and metrics[time_index] is not None:
                        ts = metrics[time_index]
                    else:
                        ts = entry.get('startTimeInSeconds')
                    
                    if ts is not None:
                        if start_time is None:
                            start_time = ts
                        time_sec = ts - start_time
                    else:
                        time_sec = i * 2
                    
                    hr_data.append({'time': time_sec, 'hr': float(hr_value)})
        
        return hr_data if hr_data else None
    
    except Exception as e:
        st.warning(f"⚠️ Erro ao buscar dados de FC: {e}")
        return None


@st.cache_data(ttl=3600)
def get_activity_all_metrics(activity_id, _client):
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

        for dk in ('directDistance', 'sumDistance', 'distance'):
            if dk in df.columns:
                df['dist_km'] = pd.to_numeric(df[dk], errors='coerce') / 1000
                break

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
    if not summary:
        st.info("ℹ️ Resumo detalhado não disponível para esta atividade.")
        return

    s = summary.get('summaryDTO', summary)

    def v(key, default=None):
        val = s.get(key, default)
        return val if val not in (None, 0, 0.0, '') else default

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

    total_dur   = s.get('duration')
    moving_dur  = s.get('movingDuration')
    elapsed_dur = s.get('elapsedDuration')
    time_rows = ""
    if total_dur:   time_rows += _row("Tempo total", _fmt_time(total_dur))
    if moving_dur:  time_rows += _row("Tempo em movimento", _fmt_time(moving_dur))
    if elapsed_dur: time_rows += _row("Tempo transcorrido", _fmt_time(elapsed_dur))

    rw_rows = ""
    splits = summary.get('splitSummaries', [])
    run_dur  = next((sp.get('duration', 0) for sp in splits if sp.get('splitType') == 'RWD_RUN'),  None)
    walk_dur = next((sp.get('duration', 0) for sp in splits if sp.get('splitType') == 'RWD_WALK'), None)
    if run_dur:  rw_rows += _row("Tempo de corrida", _fmt_time(run_dur))
    if walk_dur: rw_rows += _row("Tempo da caminhada", _fmt_time(walk_dur))

    avg_hr = s.get('averageHR') or selected.get('avg_hr')
    max_hr = s.get('maxHR') or selected.get('max_hr')
    hr_rows = ""
    if avg_hr: hr_rows += _row("Frequência cardíaca média", f"{avg_hr:.0f} bpm")
    if max_hr: hr_rows += _row("Frequência cardíaca máxima", f"{max_hr:.0f} bpm")

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

    avg_pwr = s.get('averagePower')
    max_pwr = s.get('maxPower')
    pwr_rows = ""
    if avg_pwr: pwr_rows += _row("Potência média", f"{avg_pwr:.0f} W")
    if max_pwr: pwr_rows += _row("Energia máxima", f"{max_pwr:.0f} W")

    avg_cad  = s.get('averageRunCadence')
    max_cad  = s.get('maxRunCadence')
    stride   = s.get('strideLength')
    vert_rat = s.get('verticalRatio')
    vert_osc = s.get('verticalOscillation')
    gct      = s.get('groundContactTime')
    dyn_rows = ""
    if avg_cad:  dyn_rows += _row("Cadência corrida média", f"{avg_cad:.0f} epm")
    if max_cad:  dyn_rows += _row("Cadência corrida máx.", f"{max_cad:.0f} epm")
    if stride:   dyn_rows += _row("Compr. médio dos passos", f"{stride / 100:.2f} m")
    if vert_rat: dyn_rows += _row("Propor. de média vertical", f"{vert_rat:.1f}%")
    if vert_osc: dyn_rows += _row("Oscilação vertical média", f"{vert_osc:.1f} cm")
    if gct:      dyn_rows += _row("Tpo méd. contato com solo", f"{gct:.0f} ms")

    asc   = s.get('elevationGain') or selected.get('elevation_gain')
    desc  = s.get('elevationLoss') or selected.get('elevation_loss')
    e_min = s.get('minElevation')
    e_max = s.get('maxElevation')
    elev_rows = ""
    if asc:   elev_rows += _row("Subida total", f"{float(asc):.0f} m")
    if desc:  elev_rows += _row("Descida total", f"{float(desc):.0f} m")
    if e_min: elev_rows += _row("Elevação mínima", f"{e_min:.0f} m")
    if e_max: elev_rows += _row("Elevação máxima", f"{e_max:.0f} m")

    rest_cal = s.get('bmrCalories')
    act_cal  = s.get('calories', 0) - (rest_cal or 0) if s.get('calories') else None
    tot_cal  = s.get('calories') or selected.get('calories')
    sweat    = s.get('waterEstimated')
    nut_rows = ""
    if rest_cal:                nut_rows += _row("Calorias em repouso", f"{rest_cal:.0f}")
    if act_cal and act_cal > 0: nut_rows += _row("Calorias ativas", f"{act_cal:.0f}")
    if tot_cal:                 nut_rows += _row("Total de calorias queimadas", f"{float(tot_cal):.0f}")
    if sweat:                   nut_rows += _row("Perda de suor estimada", f"{sweat:.0f} ml")

    avg_tmp = s.get('averageTemperature')
    min_tmp = s.get('minTemperature')
    max_tmp = s.get('maxTemperature')
    tmp_rows = ""
    if avg_tmp: tmp_rows += _row("Temperatura média", f"{avg_tmp:.0f}°C")
    if min_tmp: tmp_rows += _row("Temperatura mínima", f"{min_tmp:.0f}°C")
    if max_tmp: tmp_rows += _row("Temperatura máxima", f"{max_tmp:.0f}°C")

    mod_int  = s.get('moderateIntensityMinutes')
    high_int = s.get('vigorousIntensityMinutes')
    tot_int  = (mod_int or 0) + (high_int or 0) or None
    int_rows = ""
    if mod_int:  int_rows += _row("Moderado", f"{mod_int} min")
    if high_int: int_rows += _row("Alta", f"{high_int} min")
    if tot_int:  int_rows += _row("Total", f"{tot_int} min")

    bb_impact = s.get('differenceBodyBattery')
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
    if not hr_data or len(hr_data) == 0:
        return None
    
    try:
        df_hr = pd.DataFrame(hr_data)
        
        if 'time' in df_hr.columns:
            if pd.api.types.is_numeric_dtype(df_hr['time']):
                df_hr['time_min'] = df_hr['time'] / 60
            else:
                try:
                    df_hr['time'] = pd.to_datetime(df_hr['time'])
                    df_hr['time_min'] = (df_hr['time'] - df_hr['time'].iloc[0]).dt.total_seconds() / 60
                except:
                    df_hr['time_min'] = range(len(df_hr))
        
        avg_hr = df_hr['hr'].mean()
        max_hr = df_hr['hr'].max()
        min_hr = df_hr['hr'].min()
        
        fig = go.Figure()
        
        max_estimated = 200
        zona1_limit = max_estimated * 0.5
        zona2_limit = max_estimated * 0.6
        zona3_limit = max_estimated * 0.7
        zona4_limit = max_estimated * 0.85
        
        x_range = [df_hr['time_min'].min(), df_hr['time_min'].max()]
        
        fig.add_vrect(x0=x_range[0], x1=x_range[1], y0=0, y1=zona1_limit,
                     fillcolor="#3498db", opacity=0.05, layer="below", line_width=0)
        fig.add_vrect(x0=x_range[0], x1=x_range[1], y0=zona1_limit, y1=zona2_limit,
                     fillcolor="#2ecc71", opacity=0.05, layer="below", line_width=0)
        fig.add_vrect(x0=x_range[0], x1=x_range[1], y0=zona2_limit, y1=zona3_limit,
                     fillcolor="#f39c12", opacity=0.05, layer="below", line_width=0)
        fig.add_vrect(x0=x_range[0], x1=x_range[1], y0=zona3_limit, y1=zona4_limit,
                     fillcolor="#e74c3c", opacity=0.05, layer="below", line_width=0)
        fig.add_vrect(x0=x_range[0], x1=x_range[1], y0=zona4_limit, y1=max_estimated*1.1,
                     fillcolor="#c0392b", opacity=0.05, layer="below", line_width=0)
        
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
        [
            "📈 Resumo",
            "🏃 Atividades",
            "📊 Análises",
            "🏋️ Fitness (PMC)",
            "🎯 Zonas & Pace",
            "🔬 Performance",
            "🔍 Detalhamento",
        ],
        label_visibility="collapsed"
    )

    st.sidebar.divider()
    st.sidebar.title("⚙️ Filtros e Sincronização")
    
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
    
    if len(st.session_state.garmin_data) == 0:
        with st.spinner("📡 Carregando atividades do Garmin..."):
            df = get_activities_from_garmin()
    else:
        df = st.session_state.garmin_data.copy()
    
    if len(df) > 0:
        df['type'] = df['type'].apply(map_activity_type)
        
        st.sidebar.subheader("📅 Período")
        col_date1, col_date2 = st.sidebar.columns(2)
        with col_date1:
            start_date = st.date_input("De", df['date'].min())
        with col_date2:
            end_date = st.date_input("Até", df['date'].max())
        
        st.sidebar.subheader("🏷️ Tipo")
        activity_types = df[df['type'] != 'other']['type'].unique().tolist()
        activity_type = st.sidebar.multiselect(
            "Selecione",
            activity_types,
            default=activity_types,
            format_func=lambda x: {"running": "🏃 Corrida", "cycling": "🚴 Ciclismo", "strength_training": "💪 Musculação"}.get(x, x)
        )
        
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
                
                else:
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
    
                            hr_key = next((k for k in ('directHeartRate', 'heartRate') if k in metrics_df.columns), None)
                            if hr_key:
                                st.subheader("❤️ Frequência Cardíaca")
                                fig_hr2 = _create_metric_chart(
                                    metrics_df, hr_key, 'Frequência Cardíaca', 'bpm', '#e74c3c',
                                    x_key=x_key, fill=True, hoverformat='.0f'
                                )
                                if fig_hr2:
                                    st.plotly_chart(fig_hr2, use_container_width=True)
    
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
    
                            elev_key = next((k for k in ('directElevation', 'directAltitude', 'elevation') if k in metrics_df.columns), None)
                            if elev_key:
                                st.subheader("⛰️ Elevação")
                                fig_elev = _create_metric_chart(
                                    metrics_df, elev_key, 'Elevação', 'm', '#27ae60',
                                    x_key=x_key, fill=True, hoverformat='.0f'
                                )
                                if fig_elev:
                                    st.plotly_chart(fig_elev, use_container_width=True)
    
                            pwr_key = next((k for k in ('directPower', 'directRunPower', 'runPower') if k in metrics_df.columns), None)
                            if pwr_key:
                                st.subheader("⚡ Potência")
                                fig_pwr = _create_metric_chart(
                                    metrics_df, pwr_key, 'Potência', 'W', '#9b59b6',
                                    x_key=x_key, fill=True, hoverformat='.0f'
                                )
                                if fig_pwr:
                                    st.plotly_chart(fig_pwr, use_container_width=True)
    
                            cad_key = next((k for k in ('directRunCadence', 'runCadence', 'directBikeCadence') if k in metrics_df.columns), None)
                            if cad_key:
                                st.subheader("🦵 Cadência")
                                fig_cad = _create_metric_chart(
                                    metrics_df, cad_key, 'Cadência', 'spm', '#3498db',
                                    x_key=x_key, fill=False, hoverformat='.0f'
                                )
                                if fig_cad:
                                    st.plotly_chart(fig_cad, use_container_width=True)
    
                            stride_key = next((k for k in ('directStrideLength', 'strideLength') if k in metrics_df.columns), None)
                            if stride_key:
                                st.subheader("👟 Comprimento da Passada")
                                fig_stride = _create_metric_chart(
                                    metrics_df, stride_key, 'Comprimento da Passada', 'm', '#1abc9c',
                                    x_key=x_key, fill=False, hoverformat='.2f'
                                )
                                if fig_stride:
                                    st.plotly_chart(fig_stride, use_container_width=True)
    
                            vr_key = next((k for k in ('directVerticalRatio', 'verticalRatio') if k in metrics_df.columns), None)
                            if vr_key:
                                st.subheader("📐 Proporção Vertical")
                                fig_vr = _create_metric_chart(
                                    metrics_df, vr_key, 'Proporção Vertical', '%', '#e67e22',
                                    x_key=x_key, fill=False, hoverformat='.1f'
                                )
                                if fig_vr:
                                    st.plotly_chart(fig_vr, use_container_width=True)
    
                            vo_key = next((k for k in ('directVerticalOscillation', 'verticalOscillation') if k in metrics_df.columns), None)
                            if vo_key:
                                st.subheader("📊 Oscilação Vertical")
                                fig_vo = _create_metric_chart(
                                    metrics_df, vo_key, 'Oscilação Vertical', 'mm', '#e74c3c',
                                    x_key=x_key, fill=False, hoverformat='.1f'
                                )
                                if fig_vo:
                                    st.plotly_chart(fig_vo, use_container_width=True)
    
                            gct_key = next((k for k in ('directGroundContactTime', 'groundContactTime') if k in metrics_df.columns), None)
                            if gct_key:
                                st.subheader("🦶 Tempo de Contato c/ Solo")
                                fig_gct = _create_metric_chart(
                                    metrics_df, gct_key, 'Tempo Contato Solo', 'ms', '#c0392b',
                                    x_key=x_key, fill=False, hoverformat='.0f'
                                )
                                if fig_gct:
                                    st.plotly_chart(fig_gct, use_container_width=True)
    
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
                            col_hr1, col_hr2, col_hr3 = st.columns(3)
                            with col_hr1: st.metric("❤️ FC Média", f"{selected['avg_hr']:.0f} bpm")
                            with col_hr2: st.metric("📈 FC Máxima", f"{selected['max_hr']:.0f} bpm")
                            with col_hr3: st.metric("📉 FC Mínima", "—")
    
                else:
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
        
        else:  # Dashboard
            if pagina == "📈 Resumo":
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Distribuição por Tipo")
                    dist_data = df_filtered.groupby('type').size()
                    type_labels = {'running': '🏃 Corrida', 'cycling': '🚴 Ciclismo', 'strength_training': '💪 Musculação', 'other': '⚙️ Outro'}
                    fig_dist = px.pie(
                        values=dist_data.values,
                        names=[type_labels.get(t, t) for t in dist_data.index],
                        color_discrete_sequence=['#FF6B6B', '#4ECDC4', '#45B7D1', '#95a5a6']
                    )
                    st.plotly_chart(fig_dist, use_container_width=True)
                
                with col2:
                    st.subheader("Calorias por Tipo")
                    cal_by_type = df_filtered.groupby('type')['calories'].sum()
                    fig_cal = go.Figure(data=[
                        go.Bar(
                            x=[type_labels.get(t, t) for t in cal_by_type.index],
                            y=cal_by_type.values,
                            marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#95a5a6'][:len(cal_by_type)],
                            text=cal_by_type.values,
                            textposition='auto'
                        )
                    ])
                    fig_cal.update_layout(showlegend=False, height=400)
                    st.plotly_chart(fig_cal, use_container_width=True)
                
                st.subheader("Timeline de Atividades")
                df_sorted_timeline = df_filtered.sort_values('date')
                fig_timeline = px.bar(
                    df_sorted_timeline,
                    x='date',
                    y='calories',
                    color='type',
                    color_discrete_map={'running': '#FF6B6B', 'cycling': '#4ECDC4', 'strength_training': '#45B7D1'},
                    labels={'date': 'Data', 'calories': 'Calorias'},
                    height=400
                )
                st.plotly_chart(fig_timeline, use_container_width=True)
            
            elif pagina == "🏃 Atividades":
                tab_cor, tab_cic, tab_mus = st.tabs(["🏃 Corridas", "🚴 Ciclismo", "💪 Musculação"])

                with tab_cor:
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

                with tab_cic:
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

                with tab_mus:
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
            
            elif pagina == "📊 Análises":
                st.subheader("📊 Análises Avançadas")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Frequência Cardíaca por Tipo")
                    hr_by_type = df_filtered[df_filtered['avg_hr'] > 0].groupby('type')['avg_hr'].mean()
                    fig_hr = go.Figure(data=[
                        go.Bar(
                            x=[type_labels.get(t, t) for t in hr_by_type.index],
                            y=hr_by_type.values,
                            marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1'][:len(hr_by_type)],
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
                            x=[type_labels.get(t, t) for t in duration_by_type.index],
                            y=duration_by_type.values,
                            marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1'][:len(duration_by_type)],
                            text=[f"{x:.0f} min" for x in duration_by_type.values],
                            textposition='auto'
                        )
                    ])
                    fig_duration.update_layout(showlegend=False, height=400)
                    st.plotly_chart(fig_duration, use_container_width=True)
                
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
                
                st.subheader("📋 Sumário")
                summary_col1, summary_col2, summary_col3 = st.columns(3)
                
                with summary_col1:
                    cycling_df_s = df[df['type'] == 'cycling']
                    max_cycling = cycling_df_s['distance_km'].max() if len(cycling_df_s) > 0 else 0
                    running_df_s = df[df['type'] == 'running']
                    max_running = running_df_s['distance_km'].max() if len(running_df_s) > 0 else 0
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

            elif pagina == "🏋️ Fitness (PMC)":
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

                    latest = pmc_df.iloc[-1]
                    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
                    with col_f1:
                        st.metric("💙 Condicionamento (CTL)", f"{latest['ctl']:.1f}")
                    with col_f2:
                        st.metric("💜 Fadiga (ATL)", f"{latest['atl']:.1f}")
                    with col_f3:
                        tsb = latest['tsb']
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
                        pmc_7d = pmc_df[pmc_df['date'] >= pmc_df['date'].max() - pd.Timedelta(days=6)]
                        trimp_7d = pmc_7d['trimp'].sum() if 'trimp' in pmc_7d.columns else 0
                        st.metric("📅 Carga últimos 7 dias", f"{trimp_7d:.0f} TRIMP")

                    st.divider()

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

            # ============================================
            # ABA ZONAS & PACE — NOVA
            # ============================================
            
            elif pagina == "🎯 Zonas & Pace":
                st.subheader("🎯 Zonas de Treino & Pace")
                st.markdown(
                    "O dashboard busca automaticamente a atividade mais recente com **`[teste]`** no nome. "
                    "Salve seu teste de 1km no Garmin com esse prefixo (ex: *[teste] 1km rápido*)."
                )
                
                # Buscar teste mais recente
                test_activity = find_last_test_activity(df)
                
                if test_activity is None:
                    st.warning(
                        "⚠️ Nenhuma atividade com `[teste]` encontrada no histórico.\n\n"
                        "**Como fazer:** Corra 1km no máximo esforço e salve no Garmin com o nome começando em `[teste]`, "
                        "ex: `[teste] 1km maio`."
                    )
                    st.stop()
                
                # Verificar validade
                days_since_test = (datetime.now() - test_activity['date']).days
                test_duration_sec = test_activity['duration_min'] * 60
                test_distance_km = test_activity['distance_km']
                
                # Banner do teste
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);
                            border:1px solid #e94560;border-radius:12px;padding:20px;margin-bottom:20px">
                    <h3 style="color:#e94560;margin:0 0 8px 0">📍 Último Teste Encontrado</h3>
                    <p style="color:#eee;margin:4px 0"><b>Nome:</b> {test_activity['name']}</p>
                    <p style="color:#eee;margin:4px 0"><b>Data:</b> {test_activity['date'].strftime('%d/%m/%Y')} 
                       &nbsp;|&nbsp; <b>Há:</b> {days_since_test} dias</p>
                    <p style="color:#eee;margin:4px 0"><b>Distância:</b> {test_distance_km:.2f} km 
                       &nbsp;|&nbsp; <b>Tempo:</b> {seconds_to_pace_str(test_duration_sec).replace(' /km','')} 
                       &nbsp;|&nbsp; <b>FC máx:</b> {test_activity['max_hr']:.0f} bpm</p>
                </div>
                """, unsafe_allow_html=True)
                
                if days_since_test > 30:
                    st.warning(f"⚠️ Teste com **{days_since_test} dias** — resultados podem estar desatualizados. Considere refazer o teste.")
                else:
                    st.success(f"✅ Teste recente ({days_since_test} dias) — zonas confiáveis.")
                
                # Verificar se distância é próxima de 1km
                if test_distance_km < 0.8 or test_distance_km > 1.5:
                    st.warning(f"⚠️ Distância do teste ({test_distance_km:.2f} km) difere muito de 1km. Os cálculos serão ajustados proporcionalmente.")
                
                # Calcular pace por km do teste (normalizado para 1km)
                pace_1km_sec = test_duration_sec / test_distance_km  # seg/km
                
                # Calcular zonas
                result = calculate_training_zones(pace_1km_sec, test_activity['max_hr'])
                if not result:
                    st.error("Erro ao calcular zonas. Verifique os dados do teste.")
                    st.stop()
                
                zones, vo2max_est = result
                
                # Métricas do teste
                st.subheader("📊 Resultados do Teste")
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("⏱️ Pace no 1km", seconds_to_pace_str(pace_1km_sec))
                with m2:
                    st.metric("❤️ FC Máx no Teste", f"{test_activity['max_hr']:.0f} bpm")
                with m3:
                    if vo2max_est:
                        st.metric("🫁 VO₂max Estimado", f"{vo2max_est:.1f} ml/kg/min")
                with m4:
                    # Classificar VO2max
                    if vo2max_est:
                        if vo2max_est >= 55:   classe = "Superior 🏆"
                        elif vo2max_est >= 48: classe = "Excelente ⭐"
                        elif vo2max_est >= 42: classe = "Bom 👍"
                        elif vo2max_est >= 35: classe = "Razoável 📈"
                        else:                  classe = "Iniciante 🌱"
                        st.metric("🏅 Classificação", classe)
                
                st.divider()
                
                # Tabela de zonas
                st.subheader("🗂️ Tabela de Zonas de Treino")
                
                for z in zones:
                    with st.expander(f"{z['emoji']} **{z['zona']} — {z['nome']}** &nbsp;&nbsp; Pace: `{z['pace_alvo_str']}` &nbsp;&nbsp; FC: `{z['fc_str']}`", expanded=False):
                        col_a, col_b = st.columns([1, 2])
                        with col_a:
                            st.markdown(f"""
                            | Métrica | Valor |
                            |---------|-------|
                            | Pace mínimo | `{z['pace_min_str']}` |
                            | Pace máximo | `{z['pace_max_str']}` |
                            | Velocidade | {z['vel_min_kmh']} – {z['vel_max_kmh']} km/h |
                            | FC alvo | {z['fc_str']} |
                            """)
                        with col_b:
                            st.markdown(f"""
                            **📝 Sensação:** {z['descricao']}
                            
                            **🎯 Para que serve:** {z['uso']}
                            
                            **📋 Exemplo de treino:** {z['exemplo']}
                            """)
                
                st.divider()
                
                # Distribuição das corridas por zona
                st.subheader("📈 Como Você Está Treinando?")
                
                zone_analysis = analyze_recent_runs_by_zone(df, zones, pace_1km_sec)
                
                if not zone_analysis.empty:
                    col_pie, col_table = st.columns([1, 2])
                    
                    with col_pie:
                        fig_zone_dist = create_zone_distribution_chart(zone_analysis)
                        if fig_zone_dist:
                            st.plotly_chart(fig_zone_dist, use_container_width=True)
                    
                    with col_table:
                        st.markdown("**Corridas recentes classificadas por zona:**")
                        display_zone = zone_analysis.copy()
                        display_zone['date'] = pd.to_datetime(display_zone['date']).dt.strftime('%d/%m/%Y')
                        display_zone['distance_km'] = display_zone['distance_km'].apply(lambda x: f"{x:.2f} km")
                        display_zone['duration_min'] = display_zone['duration_min'].apply(lambda x: f"{x:.0f} min")
                        display_zone['avg_hr'] = display_zone['avg_hr'].apply(lambda x: f"{x:.0f} bpm" if x > 0 else "—")
                        display_zone.columns = ['Data', 'Nome', 'Distância', 'Duração', 'Pace Médio', 'Zona', 'FC Média']
                        st.dataframe(display_zone.head(20), use_container_width=True, hide_index=True)
                
                st.divider()
                
                # Evolução do pace com faixas de zona
                st.subheader("📈 Evolução do Pace com Zonas")
                fig_pace_evo = create_pace_evolution_chart(df, zones)
                if fig_pace_evo:
                    st.plotly_chart(fig_pace_evo, use_container_width=True)
                else:
                    st.info("ℹ️ Dados insuficientes de corridas para mostrar evolução.")
                
                st.divider()
                
                # Guia de treino semanal sugerido
                st.subheader("📅 Sugestão de Semana de Treino")
                st.markdown("Baseado no modelo **80/20** (80% volume em Z1-Z2, 20% em Z3-Z5):")
                
                week_col1, week_col2 = st.columns(2)
                z1 = zones[0]
                z2 = zones[1]
                z3 = zones[2]
                z4 = zones[3]
                z5 = zones[4]
                
                with week_col1:
                    st.info(f"""
                    **Segunda — Recuperação ({z1['emoji']} Z1)**
                    - 20-30 min em {z1['pace_alvo_str']}
                    - FC: {z1['fc_str']}
                    - _Fácil, conversação livre_
                    
                    **Quarta — Base Aeróbica ({z2['emoji']} Z2)**
                    - 40-60 min em {z2['pace_alvo_str']}
                    - FC: {z2['fc_str']}
                    - _Esforço confortável_
                    
                    **Sexta — Intervalado ({z4['emoji']} Z4)**
                    - 5×1000m em {z4['pace_alvo_str']}
                    - Descanso: 2-3 min entre repetições
                    - _Intenso mas controlado_
                    """)
                
                with week_col2:
                    st.success(f"""
                    **Terça — Descanso ou Musculação** 💪
                    - Recuperação ativa
                    
                    **Quinta — Tempo ({z3['emoji']} Z3)**
                    - 20-30 min em {z3['pace_alvo_str']}
                    - FC: {z3['fc_str']}
                    - _Desconfortável mas sustentável_
                    
                    **Sábado — Longa ({z2['emoji']} Z2)**
                    - 60-90 min em {z2['pace_alvo_str']}
                    - FC: {z2['fc_str']}
                    - _Conversa possível, levemente cansativo_
                    
                    **Domingo — Descanso total** 🛌
                    """)

            # ============================================
            # ABA PERFORMANCE — NOVA
            # ============================================

            elif pagina == "🔬 Performance":
                st.subheader("🔬 Análise de Performance Avançada")
                
                perf_tab1, perf_tab2, perf_tab3 = st.tabs([
                    "📈 VO₂max Trend",
                    "🏃 Eficiência de Corrida",
                    "🛌 Sono × Desempenho"
                ])
                
                with perf_tab1:
                    st.markdown("**Evolução do VO₂max estimado pelo Garmin ao longo do tempo.**")
                    
                    if st.session_state.get('garmin_client'):
                        with st.spinner("📡 Buscando dados de VO₂max..."):
                            vo2max_data = get_vo2max_trend(st.session_state.garmin_client, weeks=52)
                        
                        fig_vo2 = create_vo2max_chart(vo2max_data)
                        if fig_vo2:
                            st.plotly_chart(fig_vo2, use_container_width=True)
                            
                            # Tabela de classificação por gênero/idade
                            st.subheader("📊 Tabela de Referência VO₂max")
                            col_ref1, col_ref2 = st.columns(2)
                            with col_ref1:
                                st.markdown("""
                                **Homens (30-39 anos):**
                                | Classificação | VO₂max |
                                |---|---|
                                | Superior | ≥ 52 |
                                | Excelente | 47-51 |
                                | Bom | 42-46 |
                                | Razoável | 37-41 |
                                | Fraco | < 37 |
                                """)
                            with col_ref2:
                                st.markdown("""
                                **Mulheres (30-39 anos):**
                                | Classificação | VO₂max |
                                |---|---|
                                | Superior | ≥ 45 |
                                | Excelente | 41-44 |
                                | Bom | 36-40 |
                                | Razoável | 31-35 |
                                | Fraco | < 31 |
                                """)
                        else:
                            st.info("ℹ️ Dados de VO₂max não disponíveis na API ou dispositivo não suporta esta métrica.")
                            
                            # Alternativa: calcular pelo teste
                            test_activity = find_last_test_activity(df)
                            if test_activity is not None:
                                pace_sec = (test_activity['duration_min'] * 60) / test_activity['distance_km']
                                vo2_calc = calculate_vo2max_from_1km(pace_sec)
                                if vo2_calc:
                                    st.metric("🫁 VO₂max Estimado pelo Teste de 1km", f"{vo2_calc:.1f} ml/kg/min")
                    else:
                        st.warning("⚠️ Cliente Garmin não disponível.")
                
                with perf_tab2:
                    st.markdown("""
                    **Efficiency Factor (EF)** = Velocidade média ÷ FC média.
                    
                    Quanto maior o EF, mais eficiente você é: vai mais rápido com o mesmo esforço cardíaco.
                    Uma tendência de **EF crescente** indica melhora real da capacidade aeróbica.
                    """)
                    
                    economy_df = calculate_running_economy(df)
                    
                    if not economy_df.empty:
                        fig_economy = create_running_economy_chart(economy_df)
                        if fig_economy:
                            st.plotly_chart(fig_economy, use_container_width=True)
                        
                        # Métricas de eficiência
                        if len(economy_df) >= 2:
                            first_ef = economy_df.iloc[0]['ef_mean']
                            last_ef = economy_df.iloc[-1]['ef_mean']
                            delta_ef = ((last_ef - first_ef) / first_ef) * 100
                            
                            col_e1, col_e2, col_e3 = st.columns(3)
                            with col_e1:
                                st.metric("EF Atual (último mês)", f"{last_ef:.3f}")
                            with col_e2:
                                st.metric("EF Inicial", f"{first_ef:.3f}")
                            with col_e3:
                                st.metric("Evolução", f"{delta_ef:+.1f}%",
                                         delta="Melhorando ✅" if delta_ef > 0 else "Queda ⚠️")
                        
                        # Tabela mensal
                        st.subheader("📋 Histórico Mensal de Eficiência")
                        display_eco = economy_df.copy()
                        display_eco['month_dt'] = display_eco['month_dt'].dt.strftime('%b/%Y')
                        display_eco['ef_mean'] = display_eco['ef_mean'].apply(lambda x: f"{x:.3f}")
                        display_eco['avg_hr'] = display_eco['avg_hr'].apply(lambda x: f"{x:.0f} bpm")
                        display_eco['avg_distance'] = display_eco['avg_distance'].apply(lambda x: f"{x:.1f} km")
                        display_eco = display_eco[['month_dt', 'ef_mean', 'n_runs', 'avg_hr', 'avg_distance']]
                        display_eco.columns = ['Mês', 'Efficiency Factor', 'Nº Corridas', 'FC Média', 'Distância Média']
                        st.dataframe(display_eco, use_container_width=True, hide_index=True)
                    else:
                        # Diagnóstico: mostrar o que tem nas corridas
                        running_debug = df[df['type'] == 'running'].copy()
                        total_runs = len(running_debug)
                        runs_com_hr = (pd.to_numeric(running_debug['avg_hr'], errors='coerce') > 50).sum()
                        runs_com_dist = (pd.to_numeric(running_debug['distance_km'], errors='coerce') > 0.5).sum()
                        
                        st.warning(f"""
                        ⚠️ **Dados insuficientes para Efficiency Factor**
                        
                        Diagnóstico do seu histórico:
                        - Total de corridas: **{total_runs}**
                        - Corridas com FC registrada (> 50 bpm): **{runs_com_hr}**
                        - Corridas com distância > 0.5km: **{runs_com_dist}**
                        
                        Para calcular o EF são necessárias corridas com **FC média registrada**.
                        Verifique se o monitor cardíaco estava ativado durante as atividades.
                        """)
                
                with perf_tab3:
                    st.markdown("""
                    Correlação entre a **qualidade do sono da noite anterior** e o **pace da corrida do dia seguinte**.
                    
                    Dados de sono são buscados diretamente do Garmin Connect (requer Garmin 165 com rastreamento de sono ativado).
                    """)
                    
                    if st.session_state.get('garmin_client'):
                        with st.spinner("📡 Buscando dados de sono (últimos 60 dias)..."):
                            sleep_df = get_sleep_data_range(st.session_state.garmin_client, days=60)
                        
                        running_df_perf = df[df['type'] == 'running'].copy()
                        
                        if not sleep_df.empty and not running_df_perf.empty:
                            result_sleep = create_sleep_performance_chart(sleep_df, running_df_perf)
                            
                            if result_sleep:
                                fig_sleep, merged_df = result_sleep
                                st.plotly_chart(fig_sleep, use_container_width=True)
                                
                                # Estatísticas de sono
                                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                                with col_s1:
                                    st.metric("😴 Sono Médio", f"{sleep_df['sleep_hours'].mean():.1f}h")
                                with col_s2:
                                    st.metric("📉 Mínimo", f"{sleep_df['sleep_hours'].min():.1f}h")
                                with col_s3:
                                    st.metric("📈 Máximo", f"{sleep_df['sleep_hours'].max():.1f}h")
                                with col_s4:
                                    noites_ruins = (sleep_df['sleep_hours'] < 6).sum()
                                    st.metric("⚠️ Noites < 6h", f"{noites_ruins}")
                                
                                # Insight automático
                                if len(merged_df) >= 5:
                                    x = merged_df['sleep_hours'].values
                                    # pace_sec_km já está no merged_df (vem do merge)
                                    y = merged_df['pace_sec_km'].values
                                    n = len(x)
                                    slope = (n * (x * y).sum() - x.sum() * y.sum()) / (n * (x**2).sum() - x.sum()**2)
                                    
                                    if slope < -5:
                                        st.success("✅ **Insight:** Há uma correlação clara — mais horas de sono resultam em pace significativamente melhor nos seus treinos.")
                                    elif slope < 0:
                                        st.info("ℹ️ **Insight:** Tendência leve de melhora no pace com mais sono, mas a correlação não é forte.")
                                    else:
                                        st.warning("⚠️ **Insight:** Os dados não mostram correlação clara entre sono e pace no seu histórico.")
                            else:
                                st.info("ℹ️ Dados insuficientes para correlacionar sono e performance (mínimo 4 corridas com sono no dia anterior).")
                        else:
                            if sleep_df.empty:
                                st.warning("⚠️ Nenhum dado de sono encontrado. Verifique se o rastreamento de sono está ativo no Garmin 165.")
                            else:
                                st.info("ℹ️ Nenhuma corrida encontrada para correlacionar com o sono.")
                    else:
                        st.warning("⚠️ Cliente Garmin não disponível.")

        st.divider()
        st.markdown("---")
        st.markdown("📊 Dashboard criado com Streamlit + Garmin Connect | Conexão em tempo real")

else:
    st.info("👈 Faça login com suas credenciais do Garmin Connect na barra lateral")
