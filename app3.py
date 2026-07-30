import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Bilanço Radar V4", layout="wide")

st.title("🎯 Bilanço Radar ve Sinyal Paneli V4")
st.write("Dinamik Hisse Ekleme Özellikli Canlı Bilanço ve Sürpriz Takip Paneli")

# Oturum (Session State) listesi
if 'secilen_hisseler' not in st.session_state:
    st.session_state.secilen_hisseler = ['NVDA', 'DELL', 'MU', 'AAPL', 'AMZN', 'CAT', 'MSFT', 'TUPRS.IS', 'FROTO.IS']

# --- ARAYÜZDEN HİSSE EKLEME BÖLÜMÜ ---
st.sidebar.header("➕ Yeni Hisse Ekle")
yeni_hisse = st.sidebar.text_input("Hisse Sembolü (Ticker):", value="").upper().strip()

if st.sidebar.button("Listeye Ekle"):
    if yeni_hisse and yeni_hisse not in st.session_state.secilen_hisseler:
        st.session_state.secilen_hisseler.append(yeni_hisse)
        st.sidebar.success(f"{yeni_hisse} başarıyla eklendi!")
        st.rerun()
    elif yeni_hisse in st.session_state.secilen_hisseler:
        st.sidebar.warning("Bu hisse zaten listede var.")

st.sidebar.markdown("---")
kaldirilacak_hisse = st.sidebar.selectbox("Listeden Çıkarılacak Hisse:", options=["Seçiniz"] + st.session_state.secilen_hisseler)
if st.sidebar.button("Seçileni Kaldır") and kaldirilacak_hisse != "Seçiniz":
    st.session_state.secilen_hisseler.remove(kaldirilacak_hisse)
    st.sidebar.success(f"{kaldirilacak_hisse} listeden çıkarıldı!")
    st.rerun()

# --- VERİ ÇEKME FONKSİYONU (Geliştirilmiş & Hata Korumalı) ---
@st.cache_data(ttl=3600)
def bilanco_verilerini_getir(sembol_listesi):
    veriler = []
    for sembol in sembol_listesi:
        hisse = yf.Ticker(sembol)
        
        # 1. Güncel Fiyat (Geçmiş veriden veya info'dan güvenli çekim)
        guncel_fiyat = "Veri Yok"
        try:
            hist = hisse.history(period="1d")
            if not hist.empty:
                guncel_fiyat = round(hist['Close'].iloc[-1], 2)
            else:
                guncel_fiyat = round(hisse.info.get('currentPrice', hisse.info.get('regularMarketPrice', 0)), 2)
        except:
            pass

        # 2. Sonraki Bilanço Tarihi
        tarih = "Açıklanmadı / Veri Yok"
        try:
            cal = hisse.calendar
            if isinstance(cal, dict) and 'Earnings Date' in cal:
                earning_dates = cal['Earnings Date']
                if earning_dates:
                    tarih = str(earning_dates[0]).split()[0]
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                ham_tarih = cal.iloc[0, 0]
                if pd.notnull(ham_tarih):
                    tarih = str(ham_tarih).split()[0]
        except:
            pass
        
        if tarih == "Açıklanmadı / Veri Yok":
            try:
                # Alternatif olarak earnings_dates tablosundan gelecek tarihi bulmaya çalışalım
                ed = hisse.earnings_dates
                if ed is not None and not ed.empty:
                    gelecek_tarihler = ed[ed.index > datetime.now()]
                    if not gelecek_tarihler.empty:
                        tarih = str(gelecek_tarihler.index[0]).split()[0]
            except:
                pass

        # 3. Son Çeyrek Sürprizi
        surpriz = "Veri Yok"
        try:
            gecmis_bilancolar = hisse.earnings_dates
            if gecmis_bilancolar is not None and not gecmis_bilancolar.empty:
                gecmis_bilancolar = gecmis_bilancolar[gecmis_bilancolar.index < datetime.now()]
                if not gecmis_bilancolar.empty and 'Surprise(%)' in gecmis_bilancolar.columns:
                    son_surpriz = gecmis_bilancolar['Surprise(%)'].dropna().iloc[0]
                    if pd.notnull(son_surpriz):
                        surpriz = f"% {round(son_surpriz * 100, 2)}"
        except:
            pass

        veriler.append({
            "Hisse": sembol,
            "Sonraki Bilanço Tarihi": tarih,
            "Güncel Fiyat": guncel_fiyat,
            "Son Çeyrek Sürprizi": surpriz
        })
    return pd.DataFrame(veriler)

# --- ANA EKRAN TABLOSU ---
st.subheader("📊 Aktif Takip Listesi")

if not st.session_state.secilen_hisseler:
    st.info("Listede henüz hisse yok. Sol menüden ekleme yapabilirsiniz.")
else:
    with st.spinner('Piyasa verileri güncelleniyor...'):
        df = bilanco_verilerini_getir(st.session_state.secilen_hisseler)

    def renklendir(deger):
        if isinstance(deger, str) and '%' in deger:
            if '-' in deger:
                return 'color: red; font-weight: bold'
            else:
                return 'color: green; font-weight: bold'
        return ''

    st.dataframe(
        df.style.map(renklendir, subset=['Son Çeyrek Sürprizi']),
        use_container_width=True
    )
