import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import time
import re
import pandas as pd

# Configurer la page en mode plein écran / TV
st.set_page_config(
    page_title="Live Atelier",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- INITIALISATION DE SUPABASE ---
# Idéalement, utilisez st.secrets pour la production, ou mettez-les ici pour le test
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# --- FONCTION DE FORMATAGE DES ARTICLES ---
def formatter_article(designation):
    if designation is None or pd.isna(designation):
        return "Vide"
        
    des_clean = str(designation).strip()
    
    if des_clean in ["", "---", "None", "null", "Inconnu / Aucun"]:
        return "Vide"

    match = re.match(r"(\d+)\s*mm\s+(.+)", des_clean, re.IGNORECASE)
    
    if match:
        largeur = match.group(1)
        couleur = match.group(2).strip().lower()
        
        mapping_mots = {
            "gris": "Gr", "noir": "Nr", "blanc": "Blc", "bleu": "Bl",
            "ajouré": "Aj", "ajoure": "Aj", "plein bleu bb": "PlBl", "plein bleu": "PlBl"
        }
        
        if couleur in mapping_mots:
            return f"{mapping_mots[couleur]}/{largeur}"
            
        for mot, abr in mapping_mots.items():
            if mot in couleur:
                return f"{abr}/{largeur}"
                
        return f"{couleur[:3].capitalize()}/{largeur}"
        
    return des_clean

# --- CHARGEMENT DES DONNÉES DEPUIS SUPABASE ---
def get_supabase_data():
    try:
        supabase = get_supabase_client()
        # On récupère toutes les lignes triées par l'ID de la machine
        response = supabase.table("live_dashboard_snapshot").select("*").order("machine_id").execute()
        
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        print(f"Erreur de lecture Supabase: {e}")
        return pd.DataFrame()

# --- INJECTION CSS ---
st.markdown("""
    <style>
        .stApp { background-color: #0e1117; color: white; }
        [data-testid="stHeader"] { display: none; }
        
        /* --- AJOUT : Masquage complet du menu Streamlit et du Footer --- */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header { visibility: hidden; }
        
        .block-container { 
            padding-top: 1rem !important; 
            padding-bottom: 0rem !important; 
        }
        @keyframes blinker { 50% { opacity: 0.3; } }
        .card-container {
            border-radius: 12px;
            padding: 12px;
            text-align: center;
            margin-bottom: 15px;
            border: 1px solid #333;
        }
        .card-ON  { background-color: #064e3b; border-color: #059669; }
        .card-OFF { background-color: #7f1d1d; border-color: #dc2626; animation: blinker 2s linear infinite; }
        .card-NC  { background-color: #1f2937; border-color: #4b5563; opacity: 0.7; }
        .machine-name { font-size: 1.5rem; font-weight: bold; margin-bottom: 2px; }
        .taux-value { font-size: 2.8rem; font-weight: 800; margin: 2px 0; }
        .stats-row { font-size: 0.9rem; color: #9ca3af; display: flex; justify-content: space-around; margin-bottom: 5px; }
        .bandes-container {
            background-color: rgba(0, 0, 0, 0.25);
            border-radius: 6px;
            padding: 4px;
            margin-top: 8px;
            font-size: 0.85rem;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .bande-line {
            display: flex;
            justify-content: space-between;
            padding: 2px 5px;
            border-bottom: 1px dashed rgba(255,255,255,0.1);
        }
        .bande-line:last-child { border-bottom: none; }
        .bande-label { color: #9ca3af; font-weight: normal; }
        .bande-val { font-size: 1.2rem; font-weight: bold; color: #f3f4f6; }
    </style>
""", unsafe_allow_html=True)

# Zone dynamique de rafraîchissement
placeholder = st.empty()

while True:
    now = datetime.now()
    df = get_supabase_data()

    with placeholder.container():
        if df.empty:
            st.error("⚠️ Aucune donnée disponible sur le Cloud Supabase. Vérifiez le service de synchronisation local.")
        else:
            # Récupération des colonnes (les noms correspondent aux colonnes créées dans Supabase)
            equipe = df['equipe_en_cours'].iloc[0] if 'equipe_en_cours' in df.columns else "Inconnue"
            
            # Calcul du taux moyen (en excluant les machines Non Connectées 'NC')
            if 'statut' in df.columns and 'taux_exploit_machine' in df.columns:
                df_filtré = df[df['statut'] != 'NC']
                taux_moy = df_filtré['taux_exploit_machine'].mean() if not df_filtré.empty else 0.0
            else:
                taux_moy = 0.0

            # --- EN-TÊTE DU TABLEAU DE BORD ---
            h1, h2, h3 = st.columns([2, 1, 1])
            with h1:
                st.markdown(f"<h1 style='color:#28a745; margin:0;'>🏭 ÉQUIPE {equipe} </h1>", unsafe_allow_html=True)
            with h2:
                st.markdown(f"<div style='text-align:center;'><p style='margin:0;color:#808495;'>TAUX ATELIER</p><h2 style='margin:0;'>{taux_moy:.1f}%</h2></div>", unsafe_allow_html=True)
            with h3:
                st.markdown(f"<div style='text-align:right;'><p style='margin:0;color:#808495;'>MISE À JOUR</p><h2 style='margin:0;'>{now.strftime('%H:%M:%S')}</h2></div>", unsafe_allow_html=True)

            st.markdown("---")

            # --- GRILLE DES 30 MACHINES (6 COLONNES) ---
            cols = st.columns(6)
            status_labels = {1: "ON", 0: "OFF", -1: "NC"}

            for index, row in df.iterrows():
                with cols[index % 6]:
                    # Gestion des types et des noms de colonnes provenant de Supabase
                    status_val = int(row.get('statut')) if row.get('statut') is not None else -1
                    status_text = status_labels.get(status_val, "NC")
                    
                    txt_b1 = formatter_article(row.get('de1'))
                    txt_b2 = formatter_article(row.get('de2'))
                    
                    chrono = int(row.get('chrono_minutes')) if row.get('chrono_minutes') is not None else 0
                    
                    # Le score venant de C# a déjà été divisé ou traité si nécessaire
                    score = float(row.get('score_equipe')) if row.get('score_equipe') is not None else 0.0
                    taux = float(row.get('taux_exploit_machine')) if row.get('taux_exploit_machine') is not None else 0.0
                    machine_nom = str(row.get('machine_nom', 'M-?'))

                    html_card = f"""
<div class="card-container card-{status_text}">
<div class="machine-name">{machine_nom}</div>
<div class="taux-value">{taux:.1f}%</div>
<div class="stats-row">
<span>⏱️ {chrono} min</span>
<span>📦 {score:.1f} m</span>
</div>
<div style="font-size:0.8rem; font-weight:bold; letter-spacing:1px; margin-bottom:5px;">
ÉTAT : <span style="font-size:0.95rem;">{status_text}</span>
</div>
<div class="bandes-container">
<div class="bande-line">
<span class="bande-label">B1:</span>
<span class="bande-val">{txt_b1}</span>
</div>
<div class="bande-line">
<span class="bande-label">B2:</span>
<span class="bande-val">{txt_b2}</span>
</div>
</div>
</div>
""".strip()

                    st.markdown(html_card, unsafe_allow_html=True)

    # Pause de 15 secondes avant la prochaine lecture sur le Cloud
    time.sleep(15)