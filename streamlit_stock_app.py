import pandas as pd
import plotly.graph_objs as go
import glob
import os
import re
import streamlit as st

# === CONFIGURATION ===
FOLDER_PATH = r'D:\Trading Statistics\automatic data'

# === Streamlit App ===
st.set_page_config(layout="wide")
st.title("\U0001F4C8 Stock Price Analyzer")

# === Load and Merge Data ===
def load_data():
    csv_files = glob.glob(os.path.join(FOLDER_PATH, '*.csv'))
    price_df = pd.DataFrame()
    volume_df = pd.DataFrame()

    for file in csv_files:
        try:
            match = re.search(r'_(\d{8})_', os.path.basename(file))
            if not match:
                continue

            raw_date = match.group(1)
            date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
            df = pd.read_csv(file)

            if 'TckrSymb' not in df.columns or 'ClsPric' not in df.columns or 'TtlTradgVol' not in df.columns:
                continue

            df.set_index('TckrSymb', inplace=True)
            price_df[date] = df['ClsPric']
            volume_df[date] = df['TtlTradgVol']

        except Exception as e:
            print(f"Error: {e}")

    price_df['price_std'] = price_df.std(axis=1)
    price_df['mean_price'] = price_df.drop(columns=['price_std']).mean(axis=1)
    volume_df['volume_std'] = volume_df.std(axis=1)

    return price_df, volume_df

# === Plotting Function ===
def plot_stock(stock_name, price_df):
    stock_prices = price_df.loc[stock_name].drop(['price_std', 'mean_price']).sort_index().astype(float)
    mean = price_df.loc[stock_name, 'mean_price']
    std = price_df.loc[stock_name, 'price_std']

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=stock_prices.index, y=stock_prices.values, mode='lines+markers', name='Price'))
    for i, sigma in enumerate([1, 2], start=1):
        fig.add_trace(go.Scatter(x=stock_prices.index, y=[mean + sigma * std] * len(stock_prices),
                                 mode='lines', name=f'+{i}σ', line=dict(dash='dot')))
        fig.add_trace(go.Scatter(x=stock_prices.index, y=[mean - sigma * std] * len(stock_prices),
                                 mode='lines', name=f'-{i}σ', line=dict(dash='dot')))
    fig.add_trace(go.Scatter(x=stock_prices.index, y=[mean] * len(stock_prices), mode='lines', name='Mean', line=dict(dash='dash')))

    fig.update_layout(title=f"Price Chart for {stock_name}", xaxis_title='Date', yaxis_title='Price', template='plotly_white')
    return fig

# === Stock Screeners ===
def stocks_crossing_2nd_std(price_df):
    latest_date = price_df.columns[-3]
    mean = price_df['mean_price']
    std = price_df['price_std']
    current_price = price_df[latest_date]
    return price_df[current_price < (mean - 2 * std)].index.tolist()

def high_volume_spikes(volume_df):
    volume_cols = volume_df.columns[:-1]
    last_day = volume_cols[-1]
    last_7_avg = volume_df[volume_cols[-7:]].mean(axis=1)
    return volume_df[volume_df[last_day] > last_7_avg].index.tolist()

def get_buzzing_stocks(price_df, volume_df):
    std_symbols = stocks_crossing_2nd_std(price_df)
    vol_symbols = high_volume_spikes(volume_df)
    return list(set(std_symbols).union(set(std_symbols).intersection(set(vol_symbols))))

# === Run App ===
price_df, volume_df = load_data()

stock_list = price_df.index.tolist()
selected_stock = st.selectbox("Select a stock:", stock_list)

if selected_stock:
    fig = plot_stock(selected_stock, price_df)
    st.plotly_chart(fig, use_container_width=True)

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("📉 Below -2σ")
    for s in stocks_crossing_2nd_std(price_df):
        st.write(s)

with col2:
    st.subheader("🔥 Volume Spikes")
    for s in high_volume_spikes(volume_df):
        st.write(s)

with col3:
    st.subheader("🚀 Buzzing Stocks")
    for s in get_buzzing_stocks(price_df, volume_df):
        st.write(s)
