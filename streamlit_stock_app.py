import pandas as pd
import plotly.graph_objs as go
import streamlit as st
import re
from io import StringIO

st.set_page_config(layout="wide", page_title="📈 Stock Analyzer")

st.title("📊 Stock Analyzer (with Std Dev & Volume Spike Alerts)")

# === File Upload ===
uploaded_files = st.file_uploader("Upload one or more CSV files", type="csv", accept_multiple_files=True)

if not uploaded_files:
    st.info("👆 Please upload CSV files to get started.")
    st.stop()

price_df = pd.DataFrame()
volume_df = pd.DataFrame()

# === Process Uploaded Files ===
for file in uploaded_files:
    try:
        filename = file.name
        match = re.search(r'_(\d{8})_', filename)
        if not match:
            st.warning(f"❌ Skipping: Could not find date in filename `{filename}`")
            continue

        raw_date = match.group(1)
        date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"  # YYYY-MM-DD

        df = pd.read_csv(file)

        if 'TckrSymb' not in df.columns or 'ClsPric' not in df.columns or 'TtlTradgVol' not in df.columns:
            st.warning(f"❌ Skipping file: `{filename}` is missing required columns.")
            continue

        df.set_index('TckrSymb', inplace=True)
        price_df[date] = df['ClsPric']
        volume_df[date] = df['TtlTradgVol']

    except Exception as e:
        st.error(f"Error processing file `{file.name}`: {e}")

if price_df.empty or volume_df.empty:
    st.error("🚫 No valid data could be loaded. Please upload correct CSV files.")
    st.stop()

# === Calculations ===
price_df['price_std'] = price_df.std(axis=1)
price_df['mean_price'] = price_df.drop(columns=['price_std']).mean(axis=1)
volume_df['volume_std'] = volume_df.std(axis=1)

# === Helper Functions ===
def stocks_crossing_2nd_std():
    if price_df.shape[1] < 3:
        return []
    latest_date = price_df.columns[-3]  # latest date (before std/mean)
    current_price = price_df[latest_date]
    mean = price_df['mean_price']
    std = price_df['price_std']
    return price_df[(current_price < (mean - 2 * std))].index.tolist()

def high_volume_spikes():
    if volume_df.shape[1] < 8:
        return []
    volume_cols = volume_df.columns[:-1]  # all except volume_std
    last_day = volume_cols[-1]
    last_7_avg = volume_df[volume_cols[-7:]].mean(axis=1)
    return volume_df[volume_df[last_day] > last_7_avg].index.tolist()

def get_buzzing_stocks():
    std_stocks = stocks_crossing_2nd_std()
    vol_stocks = high_volume_spikes()
    return list(set(std_stocks).union(set(std_stocks).intersection(set(vol_stocks))))

def plot_stock_chart(stock_name):
    stock_prices = price_df.loc[stock_name].drop(['price_std', 'mean_price']).sort_index().astype(float)
    mean = price_df.loc[stock_name, 'mean_price']
    std = price_df.loc[stock_name, 'price_std']

    fig = go.Figure()

    fig.add_trace(go.Scatter(x=stock_prices.index, y=stock_prices.values,
                             mode='lines+markers', name='Price', line=dict(color='royalblue')))

    for i, sigma in enumerate([1, 2], start=1):
        fig.add_trace(go.Scatter(x=stock_prices.index, y=[mean + sigma * std]*len(stock_prices),
                                 mode='lines', name=f'+{i}σ', line=dict(color='green', dash='dot')))
        fig.add_trace(go.Scatter(x=stock_prices.index, y=[mean - sigma * std]*len(stock_prices),
                                 mode='lines', name=f'-{i}σ', line=dict(color='red', dash='dot')))

    fig.add_trace(go.Scatter(x=stock_prices.index, y=[mean]*len(stock_prices),
                             mode='lines', name='Mean', line=dict(color='orange', dash='dash')))

    fig.update_layout(title=f"{stock_name} Price Chart with Standard Deviations", height=500)
    return fig

# === Layout ===
st.subheader("🔍 Select a Stock")
selected_stock = st.selectbox("Choose a stock", price_df.index.tolist())

if selected_stock:
    st.plotly_chart(plot_stock_chart(selected_stock), use_container_width=True)

# === Lists ===
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("📉 Below -2σ")
    below_std = stocks_crossing_2nd_std()
    st.write(below_std if below_std else "No major drops")

with col2:
    st.subheader("🔥 Volume Spikes")
    spikes = high_volume_spikes()
    st.write(spikes if spikes else "No spikes")

with col3:
    st.subheader("🚀 Buzzing Stocks")
    buzzing = get_buzzing_stocks()
    st.write(buzzing if buzzing else "No buzzing stocks")
