import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import requests

# Yahoo Finance engellerini aşmak için sahte tarayıcı kimliği (User-Agent) oluşturuyoruz
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
})

st.set_page_config(page_title="Bilanço Radar V5", layout="wide")

st.title("🎯 Bilanço Radar ve Sinyal Paneli V5")
st.write("Analizli Bilanço Tarihleri ve Sürpriz Takip Paneli (Bypass Korumalı)")
st.caption("⚠️ Not: Yahoo Finance, BIST hisselerinin (.IS) bilanço beklentilerini ve tarihlerini çoğunlukla sunmaz. Bu alanlar BIST için 'Veri Yok' kalabilir.")

if 'secilen_hisseler' not in st.session_state:
    st.session_state.secilen_hisseler = ['NVDA', 'DELL', 'MU', 'AAPL', 'AMZN', 'CAT', 'TUPRS.IS']

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

# --- VERİ ÇEKME VE ANALİZ FONKSİYONU ---
@st.cache_data(ttl=1800)
def bilanco_verilerini_getir(sembol_listesi):
    veriler = []
    for sembol in sembol_listesi:
        # Session ekleyerek Yahoo'nun engellemesini aşıyoruz
        hisse = yf.Ticker(sembol, session=session)
        
        # 1. Güncel Fiyat (En güvenilir yöntem)
        guncel_fiyat = "Veri Yok"
        try:
            hist = hisse.history(period="5d")
            if not hist.empty:
                guncel_fiyat = round(hist['Close'].iloc[-1], 2)
        except:
            pass

        # Değişkenleri varsayılan olarak tanımlıyoruz
        son_tarih = "Veri Yok"
        sonraki_tarih = "Veri Yok"
        eps_beklenti = "Veri Yok"
        eps_gerceklesen = "Veri Yok"
        surpriz = "Veri Yok"

        # 2. Bilanço Tarihleri ve EPS (Hisse Başına Kar) Analizi
        try:
            ed = hisse.earnings_dates
            if ed is not None and not ed.empty:
                simdi = datetime.now(ed.index.tz) # Zaman dilimi uyuşmazlığını önlemek için
                
                # Geçmiş Bilançolar (Son Bilanço için)
                gecmis_bilancolar = ed[ed.index < simdi]
                if not gecmis_bilancolar.empty:
                    son_tarih = str(gecmis_bilancolar.index[0].date())
                    
                    # Veri Analizi: Beklenti vs Gerçekleşen
                    if 'EPS Estimate' in gecmis_bilancolar.columns:
                        b = gecmis_bilancolar['EPS Estimate'].iloc[0]
                        eps_beklenti = round(b, 2) if pd.notnull(b) else "Veri Yok"
                        
                    if 'Reported EPS' in gecmis_bilancolar.columns:
                        g = gecmis_bilancolar['Reported EPS'].iloc[0]
                        eps_gerceklesen = round(g, 2) if pd.notnull(g) else "Veri Yok"
                        
                    if 'Surprise(%)' in gecmis_bilancolar.columns:
                        s = gecmis_bilancolar['Surprise(%)'].iloc[0]
                        if pd.notnull(s):
                            surpriz = f"% {round(s * 100, 2)}"

                # Gelecek Bilançolar (Sonraki Bilanço için)
                gelecek_bilancolar = ed[ed.index >= simdi]
                if not gelecek_bilancolar.empty:
                    # En yakın gelecek tarihi almak için sıralıyoruz
                    gelecek_bilancolar = gelecek_bilancolar.sort_index()
                    sonraki_tarih = str(gelecek_bilancolar.index[0].date())
        except:
            pass

        veriler.append({
            "Hisse": sembol,
            "Güncel Fiyat": guncel_fiyat,
            "Son Bilanço": son_tarih,
            "Açıklanan EPS": eps_gerceklesen,
            "Beklenen EPS": eps_beklenti,
            "Sürpriz Analizi": surpriz,
            "Sonraki Bilanço": sonraki_tarih
        })
        
    return pd.DataFrame(veriler)

# --- ANA EKRAN TABLOSU ---
st.subheader("📊 Analizli Aktif Takip Listesi")

if not st.session_state.secilen_hisseler:
    st.info("Listede henüz hisse yok.")
else:
    with st.spinner('Piyasa verileri güncelleniyor, lütfen bekleyin...'):
        df = bilanco_verilerini_getir(st.session_state.secilen_hisseler)

    # Renklendirme mantığı (Sürpriz pozitifse yeşil, negatifse kırmızı)
    def renklendir(deger):
        if isinstance(deger, str) and '%' in deger:
            if '-' in deger:
                return 'color: #ff4b4b; font-weight: bold'
            else:
                return 'color: #00c04b; font-weight: bold'
        return ''

    st.dataframe(
        df.style.map(renklendir, subset=['Sürpriz Analizi']),
        use_container_width=True
    )
