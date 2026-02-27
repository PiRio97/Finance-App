import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from datetime import datetime
import calendar

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Finance Manager 2026", layout="wide")

def to_excel(recap, spese, entrate, log):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        recap.to_excel(writer, sheet_name='RECAP', index=False)
        spese.to_excel(writer, sheet_name='SPESE', index=False)
        entrate.to_excel(writer, sheet_name='ENTRATE', index=False)
        log.to_excel(writer, sheet_name='Log_Dati', index=False)
    return output.getvalue()

st.sidebar.header("📂 Dashboard Leonardo")
uploaded_file = st.sidebar.file_uploader("Carica RECAPspese.xlsx", type=["xlsx"])

if uploaded_file:
    # 1. Caricamento e Pulizia
    recap = pd.read_excel(uploaded_file, sheet_name='RECAP').fillna(0)
    spese = pd.read_excel(uploaded_file, sheet_name='SPESE').fillna(0)
    entrate = pd.read_excel(uploaded_file, sheet_name='ENTRATE').fillna(0)
    log = pd.read_excel(uploaded_file, sheet_name='Log_Dati').fillna("")

    # 2. Correzione Formati
    for df in [recap, spese, entrate]:
        df['ANNO'] = pd.to_numeric(df['ANNO'], errors='coerce').fillna(0).astype(int)
        df['MESE'] = df['MESE'].astype(str).str.lower().str.strip()

    # Sidebar: Filtri
    anni_disp = sorted(recap['ANNO'].unique().tolist(), reverse=True)
    anno_sel = st.sidebar.selectbox("Anno", anni_disp)
    mesi_disp = recap[recap['ANNO'] == anno_sel]['MESE'].tolist()
    mese_sel = st.sidebar.selectbox("Mese", mesi_disp)

    # Indici
    idx_r = recap[(recap['ANNO'] == anno_sel) & (recap['MESE'] == mese_sel)].index[0]
    idx_s = spese[(spese['ANNO'] == anno_sel) & (spese['MESE'] == mese_sel)].index[0]
    idx_e = entrate[(entrate['ANNO'] == anno_sel) & (entrate['MESE'] == mese_sel)].index[0]

    # --- HEADER CON TASTI + E - ---
    st.title(f"Resoconto {mese_sel.capitalize()} {anno_sel}")
    
    col_p1, col_p2, _ = st.columns([1, 1, 4])
    
    # POPUP ENTRATE (+)
    with col_p1:
        with st.popover("➕ Entrata", use_container_width=True):
            with st.form("form_entrate"):
                e_desc = st.text_input("Descrizione Entrata")
                e_imp = st.number_input("Importo (€)", min_value=0.0, step=0.01)
                if st.form_submit_button("Registra"):
                    recap.at[idx_r, 'ENTRATE'] += e_imp
                    entrate.at[idx_e, 'TOTALE'] += e_imp
                    recap.at[idx_r, 'RISPARMIATI'] = recap.at[idx_r, 'ENTRATE'] - recap.at[idx_r, 'USCITE']
                    val_p = entrate.at[idx_e-1, 'SALDO'] if idx_e > 0 else 0
                    entrate.at[idx_e, 'SALDO'] = val_p + recap.at[idx_r, 'ENTRATE'] - recap.at[idx_r, 'USCITE']
                    st.rerun()

    # POPUP USCITE (-)
    cat_cols = [c for c in spese.columns if c not in ['MESE', 'ANNO', 'TOTALE', 'DEBITO']]
    with col_p2:
        with st.popover("➖ Uscita", use_container_width=True):
            with st.form("form_uscite"):
                u_desc = st.text_input("Descrizione Uscita")
                u_imp = st.number_input("Importo (€)", min_value=0.0, step=0.01)
                u_cat = st.selectbox("Categoria", cat_cols)
                if st.form_submit_button("Registra"):
                    spese.at[idx_s, u_cat] += u_imp
                    spese.at[idx_s, 'TOTALE'] += u_imp
                    recap.at[idx_r, 'USCITE'] += u_imp
                    recap.at[idx_r, 'RISPARMIATI'] = recap.at[idx_r, 'ENTRATE'] - recap.at[idx_r, 'USCITE']
                    val_p = entrate.at[idx_e-1, 'SALDO'] if idx_e > 0 else 0
                    entrate.at[idx_e, 'SALDO'] = val_p + recap.at[idx_r, 'ENTRATE'] - recap.at[idx_r, 'USCITE']
                    # Logica Debiti se la categoria contiene "Debito"
                    if "debito" in u_cat.lower():
                        st.info(f"Pagamento registrato per il debito: {u_cat}")
                    st.rerun()

    # --- KPI ---
    st.divider()
    ck1, ck2, ck3, ck4 = st.columns(4)
    ck1.metric("Entrate", f"€ {recap.at[idx_r, 'ENTRATE']:,.2f}")
    ck2.metric("Uscite", f"€ {recap.at[idx_r, 'USCITE']:,.2f}")
    ck3.metric("Risparmio", f"€ {recap.at[idx_r, 'RISPARMIATI']:,.2f}")
    ck4.metric("Saldo Finale", f"€ {entrate.at[idx_e, 'SALDO']:,.2f}")

    # --- TABS (FIXED ERROR) ---
    t1, t2, t3 = st.tabs(["📊 Analisi Mensile", "🎯 Monitoraggio Debiti", "📈 Timeframe Storico"])

    with t1:
        st.subheader(f"Dettaglio Spese {mese_sel}")
        d_p = spese.loc[idx_s, cat_cols]
        df_p = d_p[d_p > 0].reset_index()
        df_p.columns = ['Categoria', 'Valore']
        if not df_p.empty:
            st.plotly_chart(px.pie(df_p, values='Valore', names='Categoria', hole=0.4), use_container_width=True)

    with t2:
        st.subheader("Stato di Avanzamento Debiti")
        deb_cols = [c for c in cat_cols if "debito" in c.lower()]
        
        if deb_cols:
            # Creazione dataframe per grafico debiti
            debiti_list = []
            for d in deb_cols:
                pagato = spese[d].sum()
                # Cerchiamo se esiste una riga nel log che definisce il "Totale Debito" 
                # Per ora usiamo un target ipotetico (o potresti aggiungerlo in una colonna dedicata)
                target = 1000 # Esempio: dovresti avere una tabella target
                debiti_list.append({"Nome": d, "Pagato": pagato, "Rimanente": max(0, target - pagato)})
            
            df_deb = pd.DataFrame(debiti_list)
            st.plotly_chart(px.bar(df_deb, x="Nome", y=["Pagato"], title="Totale pagato per ogni debito"), use_container_width=True)
            st.table(df_deb)
        else:
            st.info("Nessuna categoria con la parola 'Debito' trovata.")

    with t3:
        st.subheader("Analisi Storica")
        df_time = recap[['ANNO', 'MESE', 'ENTRATE', 'USCITE']].merge(spese, on=['ANNO', 'MESE'])
        df_time['Data'] = df_time['MESE'] + " " + df_time['ANNO'].astype(str)
        
        # Selettore Timeframe
        opzioni = df_time['Data'].tolist()
        if opzioni:
            start, end = st.select_slider("Timeframe", options=opzioni, value=(opzioni[0], opzioni[-1]))
            voci = st.multiselect("Filtra voci", ['ENTRATE', 'USCITE'] + cat_cols, default=['ENTRATE', 'USCITE'])
            
            # Filtraggio grafico
            df_plot = df_time.iloc[opzioni.index(start):opzioni.index(end)+1]
            st.plotly_chart(px.line(df_plot, x='Data', y=voci, markers=True), use_container_width=True)

    st.sidebar.divider()
    st.sidebar.download_button("📥 Scarica Excel", to_excel(recap, spese, entrate, log), "RECAP_Aggiornato.xlsx")

else:
    st.info("Carica il file Excel per iniziare.")