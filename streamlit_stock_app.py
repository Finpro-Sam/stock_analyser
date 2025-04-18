import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Stock Analyzer", layout="wide")
st.title("📈 NSE Bhavcopy Analyzer with Alerts")

# === File Upload ===
uploaded_file = st.file_uploader("Upload NSE BhavCopy CSV", type=["csv"])

@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    return df

if uploaded_file:
    df = load_data(uploaded_file)

    # === Required Columns ===
    required_columns = {'TradDt', 'ISIN', 'TckrSymb', 'ClsPric', 'TtlTradgVol'}
    if not required_columns.issubset(df.columns):
        st.warning(f"Missing columns: {required_columns - set(df.columns)}")
        st.stop()

    # === Convert Date ===
    df['TradDt'] = pd.to_datetime(df['TradDt'])

    # === Preview ===
    with st.expander("🔍 Preview Uploaded Data"):
        st.dataframe(df.head())

    # === Date Range Filter ===
    st.subheader("📆 Date Filter")
    min_date, max_date = df['TradDt'].min(), df['TradDt'].max()
    start_date, end_date = st.date_input("Select date range", [min_date, max_date], min_value=min_date, max_value=max_date)
    df = df[(df['TradDt'] >= pd.to_datetime(start_date)) & (df['TradDt'] <= pd.to_datetime(end_date))]

    # === Alert Thresholds ===
    st.subheader("⚙️ Alert Settings")
    std_threshold = st.slider("Standard Deviation Threshold", 1.0, 5.0, 2.0)
    volume_multiplier = st.slider("Volume Spike Multiplier", 1.0, 10.0, 3.0)

    # === Group and Analyze by ISIN ===
    alert_df = []
    volume_df = []
    buzzing_isins = set()

    for isin, group in df.groupby('ISIN'):
        group = group.sort_values('TradDt')
        price_std = group['ClsPric'].std()
        price_mean = group['ClsPric'].mean()
        vol_mean = group['TtlTradgVol'].mean()

        group['Price_Alert'] = abs(group['ClsPric'] - price_mean) > (std_threshold * price_std)
        group['Volume_Spike'] = group['TtlTradgVol'] > (volume_multiplier * vol_mean)

        if group['Price_Alert'].any():
            buzzing_isins.add(isin)

        alert_df.append(group[group['Price_Alert']])
        volume_df.append(group[group['Volume_Spike']])

    alert_df = pd.concat(alert_df) if alert_df else pd.DataFrame()
    volume_df = pd.concat(volume_df) if volume_df else pd.DataFrame()

    # === Helper: ISIN to Ticker Map ===
    isin_map = df[['ISIN', 'TckrSymb']].drop_duplicates().set_index('ISIN')['TckrSymb'].to_dict()

    # === Volume Chart ===
    st.subheader("📊 Volume Over Time")
    fig = px.bar(df, x='TradDt', y='TtlTradgVol', color='TckrSymb', title="Total Trading Volume by Date")
    st.plotly_chart(fig, use_container_width=True)

    # === Alert Display ===
    st.subheader("🚨 Alerts")

    col1, col2, col3 = st.columns(3)

    with col1:
        with st.expander(f"📍 Buzzing Stocks ({len(buzzing_isins)})"):
            if buzzing_isins:
                buzz_data = [{'Ticker': isin_map[i], 'ISIN': i} for i in sorted(buzzing_isins)]
                st.dataframe(pd.DataFrame(buzz_data))
            else:
                st.write("No buzzing stocks.")

    with col2:
        with st.expander(f"🔥 Price Alerts ({len(alert_df)})"):
            if not alert_df.empty:
                alert_df['Ticker'] = alert_df['ISIN'].map(isin_map)
                st.dataframe(alert_df[['TradDt', 'Ticker', 'ClsPric']])
            else:
                st.write("No price alerts triggered.")

    with col3:
        with st.expander(f"📊 Volume Spikes ({len(volume_df)})"):
            if not volume_df.empty:
                volume_df['Ticker'] = volume_df['ISIN'].map(isin_map)
                st.dataframe(volume_df[['TradDt', 'Ticker', 'TtlTradgVol']])
            else:
                st.write("No volume spikes detected.")

    # === Download Filtered Data ===
    st.subheader("⬇️ Download")
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Filtered Data", csv, "filtered_data.csv", "text/csv")
