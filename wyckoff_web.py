import streamlit as st
import ccxt
import pandas as pd
import time

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Wyckoff MTF Scanner", page_icon="📈", layout="wide")
st.title("📈 Wyckoff Prensibi & MTF Likidasyon Tarayıcı")
st.write("Binance Vadeli İşlemler piyasasını (4H Likidasyon + 30M/5M Market Kırılımı) tarar.")

# --- AYARLAR PANELİ (Web Sayfasının Solunda Durur) ---
st.sidebar.header("⚙️ Tarayıcı Ayarları")
LOOKBACK_PERIOD = st.sidebar.slider("Likidasyon Geriye Dönük Mum Sayısı", 10, 50, 20)
auto_refresh = st.sidebar.checkbox("Otomatik Yenileme (5 Dakika)", value=True)

# Bybit Vadeli İşlemler Bağlantısı
exchange = ccxt.bybit({'enableRateLimit': True, 'options': {'defaultType': 'linear'}})
def get_data(symbol, timeframe):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=50)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except:
        return None

def check_wyckoff_logic(df_htf, df_mtf, df_ltf):
    if df_htf is None or df_mtf is None or df_ltf is None or len(df_htf) < 25:
        return "Veri Eksik", "#4c525e"

    # 4H Likidasyon Kontrolü
    htf_close = df_htf['close'].iloc[-2]
    htf_low = df_htf['low'].iloc[-2]
    htf_high = df_htf['high'].iloc[-2]
    
    htf_highest_high = df_htf['high'].iloc[-(LOOKBACK_PERIOD+2):-2].max()
    htf_lowest_low = df_htf['low'].iloc[-(LOOKBACK_PERIOD+2):-2].min()
    
    spring_htf = (htf_low < htf_lowest_low) and (htf_close > htf_lowest_low)
    upthrust_htf = (htf_high > htf_highest_high) and (htf_close < htf_highest_high)

    # Kırılım Kontrolü (CHoCH)
    def is_structural_break(df, direction):
        recent_high = df['high'].iloc[-7:-2].max()
        recent_low = df['low'].iloc[-7:-2].min()
        current_close = df['close'].iloc[-2]
        
        if direction == "bullish" and current_close > recent_high: return True
        if direction == "bearish" and current_close < recent_low: return True
        return False

    mtf_break_bull = is_structural_break(df_mtf, "bullish")
    ltf_break_bull = is_structural_break(df_ltf, "bullish")
    mtf_break_bear = is_structural_break(df_mtf, "bearish")
    ltf_break_bear = is_structural_break(df_ltf, "bearish")

    # Sonuç ve Renk Eşleşmesi
    if spring_htf and (mtf_break_bull or ltf_break_bull):
        return "🚀 LONG HAZIR (Spring + MSB)", "#008000"
    elif upthrust_htf and (mtf_break_bear or ltf_break_bear):
        return "💥 SHORT HAZIR (Upthrust + MSB)", "#ff0000"
    elif spring_htf:
        return "⏳ Sadece 4H Likidasyon Alındı (Kırılım Bekleniyor)", "#00b300"
    elif upthrust_htf:
        return "⏳ Sadece 4H Upthrust Oluştu (Kırılım Bekleniyor)", "#cc0000"
    
    return "Fırsat Yok", "#131722"

# --- TARAMA BUTONU VE EKRAN TETİKLEME ---
if st.button("🔄 Piyasayı Şimdi Tara") or auto_refresh:
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Marketleri çek
    try:
        markets = exchange.load_markets()
        symbols = [symbol for symbol in markets if symbol.endswith('/USDT') and exchange.markets[symbol]['linear']]
    except Exception as e:
        st.error(f"Binance bağlantı hatası: {e}")
        symbols = []

    results = []
    total_symbols = len(symbols)

    # Döngü halinde tarama
    for idx, symbol in enumerate(symbols):
        clean_name = symbol.split('/')[0] + "USDT"
        status_text.text(f"Taranıyor: {clean_name} ({idx+1}/{total_symbols})")
        progress_bar.progress((idx + 1) / total_symbols)
        
        df_htf = get_data(symbol, '4h')
        df_mtf = get_data(symbol, '30m')
        df_ltf = get_data(symbol, '5m')
        
        status_str, bg_color = check_wyckoff_logic(df_htf, df_mtf, df_ltf)
        
        # Sadece ilginç durumları listeye ekle (Fırsat Yok olanları kalabalık yapmasın diye eliyoruz)
        if status_str != "Fırsat Yok" and status_str != "Veri Eksik":
            results.append({
                "Coin": clean_name,
                "Durum": status_str,
                "Renk": bg_color
            })
        time.sleep(0.05) # Hız limiti koruması

    status_text.text("✅ Tarama Tamamlandı!")
    progress_bar.empty()

    # --- SONUÇLARI TARAYICIDA GÖSTERME ---
    st.subheader("📋 İşlem Fırsatları Listesi")
    if len(results) == 0:
        st.info("Şu anda Wyckoff kurallarına uyan (İşleme hazır veya pusuya yatılacak) coin bulunamadı.")
    else:
        # Şık kartlar halinde ekrana basma
        for res in results:
            st.markdown(
                f"""
                <div style="background-color:{res['Renk']}; padding:15px; border-radius:10px; margin-bottom:10px;">
                    <h3 style="color:white; margin:0;">{res['Coin']} - {res['Durum']}</h3>
                </div>
                """, 
                unsafe_allow_index=True, # v6 streamlit html desteği
                unsafe_allow_html=True
            )

    # Otomatik yenileme döngüsü
    if auto_refresh:
        time.sleep(300)
        st.rerun()
