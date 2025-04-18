import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
from io import StringIO
import os
from html.parser import HTMLParser

st.set_page_config(page_title="NSE Stock Analyzer", layout="wide")
st.title("📊 NSE Stock Analyzer with Std Dev & Volume Alerts")

GITHUB_REPO_URL = "https://github.com/Finpro-Sam/stock_analyser"
RAW_BASE_URL = "https://raw.githubusercontent.com/Finpro-Sam/stock_analyser/main/"

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr in attrs:
                if attr[0] == 'href' and attr[1].endswith('.csv'):
                    self.links.append(attr[1].split('/')[-1])

def list_csv_files_from_github():
    response = requests.get(GITHUB_REPO_URL)
    parser = LinkParser()
    parser.feed(response.text)
    return list(set(parser.links))

@st.cache_data

def load_all_csvs_from_github():
    filenames = list_csv_files_from_github()
    all_data = []
    for filename in filenames:
        raw_url = RAW_BASE_URL + filename
        file_response = requests.get(raw_url)
        if file_response.status_code == 200:
            df = pd.read_csv(StringIO(file_response.text))
            df.columns = df.columns.str.strip()
            df.rename(columns={
                'TradDt': 'Date',
                'ISIN': 'ISIN',
                'TckrSymb': 'Ticker',
                'ClsPric': 'Price',
                'TtlTradgVol': 'Volume'
            }, inplace=True)
            df['Date'] = pd.to_datetime(df['Date'])
            all_data.append(df)
    return pd.concat(all_data, ignore_index=True)

try:
    df = load_all_csvs_from_github()

    # Date Filter
    st.subheader("📆 Date Range Filter")
    min_date, max_date = df['Date'].min(), df['Date'].max()
    start_date, end_date = st.date_input("Select date range", [min_date, max_date], min_value=min_date, max_value=max_date)
    df = df[(df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))]

    # Settings
    st.sidebar.header("⚙️ Settings")
    std_threshold = st.sidebar.slider("Standard Deviation Threshold", 1.0, 5.0, 2.0)
    vol_multiplier = st.sidebar.slider("Volume Spike Multiplier", 1.0, 10.0, 3.0)

    # Group Analysis
    buzzing_isins = set()
    alert_df = []
    volume_df = []
    analysis_frames = {}

    for isin, group in df.groupby('ISIN'):
        group = group.sort_values('Date')
        price_std = group['Price'].std()
        price_mean = group['Price'].mean()
        vol_mean = group['Volume'].mean()

        group['Upper_Band'] = price_mean + std_threshold * price_std
        group['Lower_Band'] = price_mean - std_threshold * price_std

        group['Price_Alert'] = abs(group['Price'] - price_mean) > (std_threshold * price_std)
        group['Volume_Spike'] = group['Volume'] > (vol_multiplier * vol_mean)

        if group['Price_Alert'].any():
            buzzing_isins.add(isin)

        alert_df.append(group[group['Price_Alert']])
        volume_df.append(group[group['Volume_Spike']])
        analysis_frames[isin] = group

    alert_df = pd.concat(alert_df) if alert_df else pd.DataFrame()
    volume_df = pd.concat(volume_df) if volume_df else pd.DataFrame()

    isin_map = df[['ISIN', 'Ticker']].drop_duplicates().set_index('ISIN')['Ticker'].to_dict()

    # === Stock Selection ===
    st.subheader("🔍 Stock Visualizer")
    selected_ticker = st.selectbox("Select Stock to Visualize", sorted(df['Ticker'].unique()))
    selected_isin = df[df['Ticker'] == selected_ticker]['ISIN'].iloc[0]
    selected_df = analysis_frames[selected_isin]

    # === Price Chart ===
    st.markdown("### Price vs Std Dev Bands")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=selected_df['Date'], y=selected_df['Price'], mode='lines+markers', name='Price'))
    fig.add_trace(go.Scatter(x=selected_df['Date'], y=selected_df['Upper_Band'], line=dict(dash='dash'), name='Upper Band'))
    fig.add_trace(go.Scatter(x=selected_df['Date'], y=selected_df['Lower_Band'], line=dict(dash='dash'), name='Lower Band'))
    st.plotly_chart(fig, use_container_width=True)

    # === Volume Histogram ===
    st.markdown("### Volume Histogram")
    st.plotly_chart(px.histogram(selected_df, x='Date', y='Volume', nbins=30, title="Volume Distribution"), use_container_width=True)

    # === Alert Tables ===
    st.subheader("🚨 Alerts Summary")
    col1, col2, col3 = st.columns(3)

    with col1:
        with st.expander(f"📍 Buzzing Stocks ({len(buzzing_isins)})"):
            buzz_data = [{'Ticker': isin_map[i], 'ISIN': i} for i in sorted(buzzing_isins)]
            st.dataframe(pd.DataFrame(buzz_data))

    with col2:
        with st.expander(f"🔥 Price Alerts ({len(alert_df)})"):
            if not alert_df.empty:
                alert_df['Ticker'] = alert_df['ISIN'].map(isin_map)
                st.dataframe(alert_df[['Date', 'Ticker', 'Price']])

    with col3:
        with st.expander(f"📊 Volume Spikes ({len(volume_df)})"):
            if not volume_df.empty:
                volume_df['Ticker'] = volume_df['ISIN'].map(isin_map)
                st.dataframe(volume_df[['Date', 'Ticker', 'Volume']])

    # Download
    st.subheader("⬇️ Download Filtered Data")
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv, "filtered_data.csv", "text/csv")

except Exception as e:
    st.error(f"❌ Error: {e}")
