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
        df = pd.read_csv(file_path, low_memory=False, dtype={'EVENTCODE_26': str})

        required_cols = ['EVENTCODE_26', 'GOLDSTEINSCALE_30', 'ACTOR1GEO_FULLNAME_36', 'ACTOR1GEO_LAT_39',
                         'ACTOR1GEO_LONG_40']
        if not all(col in df.columns for col in required_cols):
            return pd.DataFrame()

        df = df.dropna(subset=['ACTOR1GEO_LAT_39', 'ACTOR1GEO_LONG_40'])
        df['ACTOR1GEO_LAT_39'] = pd.to_numeric(df['ACTOR1GEO_LAT_39'], errors='coerce')
        df['ACTOR1GEO_LONG_40'] = pd.to_numeric(df['ACTOR1GEO_LONG_40'], errors='coerce')
        df = df.dropna(subset=['ACTOR1GEO_LAT_39', 'ACTOR1GEO_LONG_40'])

        df['国家'] = df['ACTOR1GEO_FULLNAME_36'].fillna('未知').apply(lambda x: str(x).split(',')[-1].strip())

        try:
            mapping_df = pd.read_excel(mapping_file)
            mapping_dict = dict(zip(mapping_df.iloc[:, 0].astype(str).str.split('.').str[0], mapping_df.iloc[:, 1]))
            df['event_type'] = df['EVENTCODE_26'].str.split('.').str[0].map(mapping_dict).fillna('未知类型')
        except:
            df['event_type'] = '未知类型'

        return df
    except Exception:
        return pd.DataFrame()


# 3. 执行数据读取
df = load_data('20260315.export.CSV', '事件类别.xlsx')

# 4. 主界面交互逻辑
if df.empty:
    st.error("未能加载数据，请确保文件存在于正确目录。")
else:
    st.sidebar.title("数据筛选器")

    # 国家筛选
    selected_country = st.sidebar.selectbox("选择国家", ["全部"] + sorted(df['国家'].unique().tolist()))

    # 正负向筛选 (新增逻辑)
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

    st.markdown(f"### 🌍 GDELT全球事件监测地图")

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
            map_style='road',
            tooltip={
                "html": "<b>国家: {ACTOR1GEO_FULLNAME_36}</b><br/>事件类型: {event_type}<br/>Goldstein分值: {GOLDSTEINSCALE_30}"}
        ), width='stretch')
    else:
        st.info("当前所选条件无匹配事件。")