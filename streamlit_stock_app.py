import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Stock Analyzer", layout="wide")
st.title("📈 Stock Analyzer with Alerts")

# === File Upload ===
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    return df

if uploaded_file:
    df = load_data(uploaded_file)
    
    # === Validate Columns ===
    required_columns = {'Date', 'Stock', 'Price', 'Volume'}
    if not required_columns.issubset(df.columns):
        st.warning(f"Missing columns: {required_columns - set(df.columns)}")
        st.stop()

    df['Date'] = pd.to_datetime(df['Date'])
    
    # === Preview Data ===
    with st.expander("🔍 Preview Uploaded Data"):
        st.dataframe(df.head())

    # === Filter by Date Range ===
    st.subheader("📆 Date Filter")
    min_date, max_date = df['Date'].min(), df['Date'].max()
    start_date, end_date = st.date_input("Select date range", [min_date, max_date], min_value=min_date, max_value=max_date)

    mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    df = df.loc[mask]

    # === Alert Settings ===
    st.subheader("⚙️ Alert Settings")
    std_threshold = st.slider("Standard Deviation Threshold", 1.0, 5.0, 2.0)
    volume_multiplier = st.slider("Volume Spike Multiplier", 1.0, 10.0, 3.0)

    # === Group by Stock and Calculate Stats ===
    stock_groups = df.groupby('Stock')

    alert_rows = []
    volume_spike_rows = []
    buzz_rows = []

    alert_df = []
    volume_df = []
    buzz_df = []

    for stock, group in stock_groups:
        group = group.sort_values('Date')
        price_std = group['Price'].std()
        price_mean = group['Price'].mean()
        vol_mean = group['Volume'].mean()

        group['Price_Alert'] = abs(group['Price'] - price_mean) > (std_threshold * price_std)
        group['Volume_Spike'] = group['Volume'] > (volume_multiplier * vol_mean)

        alert_df.append(group[group['Price_Alert']])
        volume_df.append(group[group['Volume_Spike']])

        if group['Price_Alert'].any():
            buzz_rows.append(stock)

    # === Concatenate DataFrames ===
    alert_df = pd.concat(alert_df) if alert_df else pd.DataFrame()
    volume_df = pd.concat(volume_df) if volume_df else pd.DataFrame()

    # === Main Charts ===
    st.subheader("📊 Volume Over Time")
    fig = px.bar(df, x='Date', y='Volume', color='Stock', title="Trading Volume")
    st.plotly_chart(fig, use_container_width=True)

    # === Alert Display ===
    st.subheader("🚨 Alerts")

    col1, col2, col3 = st.columns(3)

    with col1:
        with st.expander(f"📍 Buzzing Stocks ({len(set(buzz_rows))})"):
            if buzz_rows:
                buzz_set = sorted(set(buzz_rows))
                st.dataframe(pd.DataFrame(buzz_set, columns=["Buzzing Stocks"]))
            else:
                st.write("No stocks triggered buzz alert.")

    with col2:
        with st.expander(f"🔥 Price Alerts ({len(alert_df)})"):
            if not alert_df.empty:
                st.dataframe(alert_df[['Date', 'Stock', 'Price']])
            else:
                st.write("No price alerts triggered.")

    with col3:
        with st.expander(f"📊 Volume Spikes ({len(volume_df)})"):
            if not volume_df.empty:
                st.dataframe(volume_df[['Date', 'Stock', 'Volume']])
            else:
                st.write("No volume spikes detected.")

    # === Download Filtered Data ===
    st.subheader("⬇️ Download")
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Filtered Data", csv, "filtered_data.csv", "text/csv")
