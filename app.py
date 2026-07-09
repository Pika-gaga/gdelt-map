import streamlit as st
import pandas as pd
import pydeck as pdk

# 1. 页面基本配置
st.set_page_config(page_title="GDELT 事件分布图", layout="wide")

# CSS 样式：全屏化布局并隐藏默认页眉页脚
st.markdown("""
    <style>
        .block-container { padding: 1rem 1rem 0rem 1rem !important; max-width: 100% !important; }
        header {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)


# 2. 数据加载函数
@st.cache_data
def load_data(file_path, mapping_file):
    try:
        # 明确指定只需要的 5 列数据
        required_cols = ['EVENTCODE_26', 'GOLDSTEINSCALE_30', 'ACTOR1GEO_FULLNAME_36', 'ACTOR1GEO_LAT_39',
                         'ACTOR1GEO_LONG_40']

        # 核心优化：增加 usecols 参数！
        # 这样 Pandas 在读取硬盘时就只会提取这 5 列，丢弃其余 50+ 列，内存占用直降 90%，完美避开云端 OOM 崩溃
        df = pd.read_csv(file_path, usecols=required_cols, dtype={'EVENTCODE_26': str})

        df = df.dropna(subset=['ACTOR1GEO_LAT_39', 'ACTOR1GEO_LONG_40'])
        df['ACTOR1GEO_LAT_39'] = pd.to_numeric(df['ACTOR1GEO_LAT_39'], errors='coerce')
        df['ACTOR1GEO_LONG_40'] = pd.to_numeric(df['ACTOR1GEO_LONG_40'], errors='coerce')
        df = df.dropna(subset=['ACTOR1GEO_LAT_39', 'ACTOR1GEO_LONG_40'])

        df['国家'] = df['ACTOR1GEO_FULLNAME_36'].fillna('未知').apply(lambda x: str(x).split(',')[-1].strip())

        try:
            mapping_df = pd.read_excel(mapping_file)
            mapping_dict = dict(zip(mapping_df.iloc[:, 0].astype(str).str.split('.').str[0], mapping_df.iloc[:, 1]))
            df['event_type'] = df['EVENTCODE_26'].str.split('.').str[0].map(mapping_dict).fillna('未知类型')
        except Exception as e_excel:
            st.error(f"⚠️ 读取 Excel 映射文件报错: {e_excel} (请检查 requirements.txt 中是否包含 openpyxl)")
            df['event_type'] = '未知类型'

        return df
    except ValueError as ve:
        # 如果 CSV 里没有我们需要的列，usecols 会触发 ValueError
        st.error(f"⚠️ 报错: CSV 文件中找不到指定的列。请检查是否是标准的 GDELT 数据格式。详细: {ve}")
        return pd.DataFrame()
    except Exception as e_csv:
        st.error(f"⚠️ 读取 CSV 数据报错，详细原因: {e_csv}")
        return pd.DataFrame()


# 3. 执行数据读取
df = load_data('20260315.export.CSV', '事件类别.xlsx')

# 4. 主界面交互逻辑
if df.empty:
    st.warning("未能加载数据，请根据上方的红色报错信息进行排查。")
else:
    st.sidebar.title("数据筛选器")

    # 国家筛选
    selected_country = st.sidebar.selectbox("选择国家", ["全部"] + sorted(df['国家'].unique().tolist()))

    # 正负向筛选
    sentiment_filter = st.sidebar.selectbox("筛选事件极性",
                                            ["所有事件", "仅正向事件 (Goldstein > 0)", "仅负向事件 (Goldstein < 0)"])

    # 应用筛选逻辑
    filtered_df = df.copy()
    if selected_country != "全部":
        filtered_df = filtered_df[filtered_df['国家'] == selected_country]

    if sentiment_filter == "仅正向事件 (Goldstein > 0)":
        filtered_df = filtered_df[filtered_df['GOLDSTEINSCALE_30'] > 0]
    elif sentiment_filter == "仅负向事件 (Goldstein < 0)":
        filtered_df = filtered_df[filtered_df['GOLDSTEINSCALE_30'] < 0]

    st.markdown(f"### 🌍 全球事件热点分布 (当前筛选: {selected_country} | {sentiment_filter})")

    if not filtered_df.empty:
        # 定义颜色逻辑：正分绿，负分红，零分灰
        filtered_df['fill_color'] = filtered_df['GOLDSTEINSCALE_30'].apply(
            lambda x: [0, 204, 102, 200] if x > 0 else ([255, 51, 51, 200] if x < 0 else [128, 128, 128, 200])
        )

        layer = pdk.Layer(
            'ScatterplotLayer',
            data=filtered_df,
            get_position='[ACTOR1GEO_LONG_40, ACTOR1GEO_LAT_39]',
            get_fill_color='fill_color',
            get_radius=60000,
            pickable=True,
            auto_highlight=True
        )

        view_state = pdk.ViewState(
            latitude=filtered_df['ACTOR1GEO_LAT_39'].mean(),
            longitude=filtered_df['ACTOR1GEO_LONG_40'].mean(),
            zoom=3 if selected_country != "全部" else 1.5
        )

        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            map_provider='carto',
            map_style='light',
            tooltip={
                "html": "<b>国家: {ACTOR1GEO_FULLNAME_36}</b><br/>事件类型: {event_type}<br/>Goldstein分值: {GOLDSTEINSCALE_30}"}
        ), use_container_width=True)
    else:
        st.info("当前所选条件无匹配事件。")