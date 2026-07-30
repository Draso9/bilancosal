import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import requests

# Yahoo Finance engellerini aşmak için gelişmiş kimlik
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
})

st.set_page_config(page_title="Bilanço Radar V6", layout="wide")

st.title("🎯 Bilanço Radar ve Sinyal Paneli V6")
st.write("IP Engellerini Aşan Çift Yönlü Veri Çekme Motoru")

if 'secilen_hisseler' not in st.session_state:
    st.session_state.secilen_hisseler = ['NVDA', 'DELL', 'MU', 'AAPL', 'AMZN', 'CAT', 'MSFT', 'TUPRS.IS']

# --- ARAYÜZDEN HİSSE EKLEME ---
st.sidebar.header("➕ Yeni Hisse Ekle")
yeni_hisse = st.sidebar.text_input("Hisse Sembolü (Ticker):", value="").upper().strip()

if st.sidebar.button("Listeye Ekle"):
    if yeni_hisse and yeni_hisse not in st.session_state.secilen_hisseler:
        st.session_state.secilen_hisseler.append(yeni_hisse)
        st.sidebar.success(f"{yeni_hisse} eklendi!")
        st.rerun()
    elif yeni_hisse in st.session_state.secilen_hisseler:
        st.sidebar.warning("Hisse zaten listede.")

st.sidebar.markdown("---")
kaldirilacak_hisse = st.sidebar.selectbox("Çıkarılacak Hisse:", options=["Seçiniz"] + st.session_state.secilen_hisseler)
if st.sidebar.button("Seçileni Kaldır") and kaldirilacak_hisse != "Seçiniz":
    st.session_state.secilen_hisseler.remove(kaldirilacak_hisse)
    st.sidebar.success(f"{kaldirilacak_hisse} çıkarıldı!")
    st.rerun()

# --- VERİ ÇEKME FONKSİYONU (Çift Yönlü Kurtarma Mekanizmalı) ---
@st.cache_data(ttl=1800)
def bilanco_verilerini_getir(sembol_listesi):
    veriler = []
    for sembol in sembol_listesi:
        hisse = yf.Ticker(sembol, session=session)
        
        # Varsayılan değerler
        guncel_fiyat = "Veri Yok"
        sonraki_tarih = "Veri Yok"
        eps_beklenti = "Veri Yok"
        eps_gerceklesen = "Veri Yok"
        surpriz = "Veri Yok"

        # 1. GÜNCEL FİYAT (Önce history, hata verirse info)
        try:
            hist = hisse.history(period="5d")
            if not hist.empty:
                guncel_fiyat = round(hist['Close'].iloc[-1], 2)
            else:
                info = hisse.info
                guncel_fiyat = round(info.get('currentPrice', info.get('regularMarketPrice', 0)), 2)
                if guncel_fiyat == 0: guncel_fiyat = "Veri Yok"
        except:
            pass

        # 2. BİLANÇO TARİHİ VE EPS (Önce takvim/info, sonra detaylı analiz)
        try:
            info = hisse.info
            
            # Info sözlüğünden temel verileri kurtarmaya çalış
            if 'earningsQuarterlyGrowth' in info:
                surpriz = f"% {round(info.get('earningsQuarterlyGrowth', 0) * 100, 2)}"
                
            # Takvimden sonraki tarihi bul
            cal = hisse.calendar
            if isinstance(cal, dict) and 'Earnings Date' in cal:
                if cal['Earnings Date']:
                    sonraki_tarih = str(cal['Earnings Date'][0].date())
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                sonraki_tarih = str(cal.iloc[0, 0].date()) if pd.notnull(cal.iloc[0, 0]) else "Veri Yok"
                
        except:
            pass

        # 3. DETAYLI SÜRPRİZ ANALİZİ (Ana fonksiyon engelliyse burası atlanır, info'daki veriler kalır)
        try:
            ed = hisse.earnings_dates
            if ed is not None and not ed.empty:
                simdi = datetime.now(ed.index.tz)
                gecmis_bilancolar = ed[ed.index < simdi]
                
                if not gecmis_bilancolar.empty:
                    if 'EPS Estimate' in gecmis_bilancolar.columns:
                        b = gecmis_bilancolar['EPS Estimate'].iloc[0]
                        eps_beklenti = round(b, 2) if pd.notnull(b) else eps_beklenti
                        
                    if 'Reported EPS' in gecmis_bilancolar.columns:
                        g = gecmis_bilancolar['Reported EPS'].iloc[0]
                        eps_gerceklesen = round(g, 2) if pd.notnull(g) else eps_gerceklesen
                        
                    if 'Surprise(%)' in gecmis_bilancolar.columns:
                        s = gecmis_bilancolar['Surprise(%)'].iloc[0]
                        if pd.notnull(s):
                            surpriz = f"% {round(s * 100, 2)}"
                            
                gelecek_bilancolar = ed[ed.index >= simdi]
                if not gelecek_bilancolar.empty:
                    sonraki_tarih = str(gelecek_bilancolar.sort_index().index[0].date())
        except:
            pass

        veriler.append({
            "Hisse": sembol,
            "Güncel Fiyat": guncel_fiyat,
            "Sonraki Bilanço": sonraki_tarih,
            "Açıklanan EPS": eps_gerceklesen,
            "Beklenen EPS": eps_beklenti,
            "Büyüme / Sürpriz": surpriz,
        })
        
    return pd.DataFrame(veriler)

# --- ANA EKRAN TABLOSU ---
st.subheader("📊 Gelişmiş Takip Listesi")

if not st.session_state.secilen_hisseler:
    st.info("Listede henüz hisse yok.")
else:
    with st.spinner('Piyasa verileri çekiliyor...'):
        df = bilanco_verilerini_getir(st.session_state.secilen_hisseler)

    def renklendir(deger):
        if isinstance(deger, str) and '%' in deger:
            if '-' in deger:
                return 'color: #ff4b4b; font-weight: bold'
            else:
                return 'color: #00c04b; font-weight: bold'
        return ''

    st.dataframe(
        df.style.map(renklendir, subset=['Büyüme / Sürpriz']),
        use_container_width=True
    )
