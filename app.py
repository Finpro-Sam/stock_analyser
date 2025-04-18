import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
from io import StringIO

st.set_page_config(page_title="📈 NSE Stock Analyzer", layout="wide")

# GitHub access
GITHUB_API_URL = "https://api.github.com/repos/Finpro-Sam/stock_analyser/contents/"
RAW_BASE_URL = "https://raw.githubusercontent.com/Finpro-Sam/stock_analyser/main/"

# Load all CSVs from GitHub
@st.cache_data(show_spinner=False)
def load_all_csvs_from_github():
    try:
        response = requests.get(GITHUB_API_URL)
        response.raise_for_status()
        contents = response.json()
        csv_files = [f['name'] for f in contents if f['name'].endswith('.csv')]

        data = []
        for filename in csv_files:
            raw_url = RAW_BASE_URL + filename
            file_content = requests.get(raw_url).text
            df = pd.read_csv(StringIO(file_content))
            df.columns = df.columns.str.strip()
            df.rename(columns={
                'TradDt': 'Date',
                'ISIN': 'ISIN',
                'TckrSymb': 'Ticker',
                'ClsPric': 'Price',
                'TtlTradgVol': 'Volume'
            }, inplace=True)
            df = df[['Date', 'ISIN', 'Ticker', 'Price', 'Volume']]
            df.dropna(subset=['Date', 'Price', 'Volume'], inplace=True)
            df['Date'] = pd.to_datetime(df['Date'])
            data.append(df)

        if not data:
            raise ValueError("No CSV files loaded.")
        return pd.concat(data, ignore_index=True)

    except Exception as e:
        st.error(f"❌ Error loading data: {e}")
        return pd.DataFrame()

# Load data
df = load_all_csvs_from_github()
if df.empty:
    st.stop()

# Sidebar settings
st.sidebar.header("⚙️ Settings")
std_threshold = st.sidebar.slider("Std Dev Threshold", 1.0, 4.0, 2.0)
vol_multiplier = st.sidebar.slider("Volume Spike x Avg", 1.0, 10.0, 3.0)

# Date filter
st.subheader("📆 Date Range Filter")
min_date, max_date = df['Date'].min(), df['Date'].max()
start_date, end_date = st.date_input("Select Date Range", [min_date, max_date])
df = df[(df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))]

# Analysis
buzzing = set()
alerts_price = []
alerts_volume = []
analysis_data = {}

for isin, group in df.groupby('ISIN'):
    group = group.sort_values('Date')
    mean_price = group['Price'].mean()
    std_price = group['Price'].std()
    mean_vol = group['Volume'].mean()

    group['Upper_Band'] = mean_price + std_threshold * std_price
    group['Lower_Band'] = mean_price - std_threshold * std_price
    group['Price_Alert'] = (group['Price'] > group['Upper_Band']) | (group['Price'] < group['Lower_Band'])
    group['Volume_Spike'] = group['Volume'] > vol_multiplier * mean_vol

    if group['Price_Alert'].any():
        buzzing.add(isin)
    if group['Price_Alert'].any():
        alerts_price.append(group[group['Price_Alert']])
    if group['Volume_Spike'].any():
        alerts_volume.append(group[group['Volume_Spike']])
    analysis_data[isin] = group

alerts_price_df = pd.concat(alerts_price) if alerts_price else pd.DataFrame()
alerts_volume_df = pd.concat(alerts_volume) if alerts_volume else pd.DataFrame()
isin_map = df[['ISIN', 'Ticker']].drop_duplicates().set_index('ISIN')['Ticker'].to_dict()

# UI: Select stock to visualize
st.subheader("📊 Stock Chart Viewer")
tickers_sorted = sorted(df['Ticker'].unique())
selected_ticker = st.selectbox("Select a Ticker", tickers_sorted)
selected_isin = df[df['Ticker'] == selected_ticker]['ISIN'].iloc[0]
selected_df = analysis_data[selected_isin]

# Plot Price with Bands
st.markdown("### Price and Std Dev Bands")
fig = go.Figure()
fig.add_trace(go.Scatter(x=selected_df['Date'], y=selected_df['Price'], mode='lines+markers', name='Price'))
fig.add_trace(go.Scatter(x=selected_df['Date'], y=selected_df['Upper_Band'], mode='lines', name='Upper Band'))
fig.add_trace(go.Scatter(x=selected_df['Date'], y=selected_df['Lower_Band'], mode='lines', name='Lower Band'))
st.plotly_chart(fig, use_container_width=True)

# Volume Histogram
st.markdown("### Volume Histogram")
st.plotly_chart(px.histogram(selected_df, x='Date', y='Volume', nbins=30), use_container_width=True)

# Alerts Summary
st.subheader("🚨 Alerts Summary")
col1, col2, col3 = st.columns(3)

with col1:
    with st.expander(f"📌 Buzzing Stocks ({len(buzzing)})"):
        st.dataframe(pd.DataFrame([{'Ticker': isin_map[i], 'ISIN': i} for i in buzzing]))

with col2:
    with st.expander(f"⚠️ Price Alerts ({len(alerts_price_df)})"):
        if not alerts_price_df.empty:
            alerts_price_df['Ticker'] = alerts_price_df['ISIN'].map(isin_map)
            st.dataframe(alerts_price_df[['Date', 'Ticker', 'Price']])

with col3:
    with st.expander(f"📈 Volume Spikes ({len(alerts_volume_df)})"):
        if not alerts_volume_df.empty:
            alerts_volume_df['Ticker'] = alerts_volume_df['ISIN'].map(isin_map)
            st.dataframe(alerts_volume_df[['Date', 'Ticker', 'Volume']])

# Download filtered data
st.subheader("⬇️ Download Filtered Dataset")
st.download_button("Download CSV", df.to_csv(index=False).encode(), "filtered_data.csv")
