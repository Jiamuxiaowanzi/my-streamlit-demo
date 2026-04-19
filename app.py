import streamlit as st
import folium
import json
import math
import pandas as pd
from streamlit_folium import st_folium
from folium.plugins import Draw

# ==========================================
# 1. 核心算法与工具函数
# ==========================================

def gcj02_to_wgs84(lng, lat):
    """
    GCJ-02 (高德/腾讯) 转 WGS-84 (GPS/Leaflet标准)
    这是一个近似算法，精度足够用于无人机规划
    """
    def transform(lat, lon):
        a = 6378245.0
        ee = 0.006693421622965943
        pi = 3.1415926535897932384626

        dlat = _transform_lat(lon - 105.0, lat - 35.0)
        dlng = _transform_lng(lon - 105.0, lat - 35.0)
        radlat = lat / 180.0 * pi
        magic = math.sin(radlat)
        magic = 1 - ee * magic * magic
        sqrtmagic = math.sqrt(magic)
        dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
        dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
        return dlat, dlng

    def _transform_lat(x, y):
        pi = 3.1415926535897932384626
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + \
            0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * pi) + 20.0 *
                math.sin(2.0 * x * pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * pi) + 40.0 *
                math.sin(y / 3.0 * pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * pi) + 320 *
                math.sin(y * pi / 30.0)) * 2.0 / 3.0
        return ret

    def _transform_lng(x, y):
        pi = 3.1415926535897932384626
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + \
            0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * pi) + 20.0 *
                math.sin(2.0 * x * pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * pi) + 40.0 *
                math.sin(x / 3.0 * pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * pi) + 300.0 *
                math.sin(x / 30.0 * pi)) * 2.0 / 3.0
        return ret

    pi = 3.1415926535897932384626
    if out_of_china(lng, lat):
        return lng, lat
    dlat, dlng = transform(lat, lng)
    mgLat = lat + dlat
    mgLng = lng + dlng
    return lng * 2 - mgLng, lat * 2 - mgLat

def out_of_china(lng, lat):
    return not (lng > 72.004 and lng < 137.8347 and lat > 0.8293 and lat < 55.8271)

# ==========================================
# 2. 页面配置与初始化
# ==========================================

st.set_page_config(page_title="无人机智能航线规划", layout="wide")
st.title("🚁 无人机智能航线规划系统")

# 初始化 Session State (用于在重绘时保持数据)
if 'obstacles' not in st.session_state:
    st.session_state.obstacles = []

# ==========================================
# 3. 侧边栏：控制面板
# ==========================================

with st.sidebar:
    st.header("⚙️ 任务配置")

    # 基础参数
    flight_height = st.number_input("✈️ 飞行高度 (米)", min_value=10, max_value=500, value=120, step=5)
    safety_radius = st.number_input("🛡️ 安全半径 (米)", min_value=1, max_value=100, value=5, step=1)

    st.divider()

    # 起终点设置
    st.subheader("📍 起终点设置")
    start_lng = st.number_input("起点经度 (GCJ-02)", value=116.397428, format="%.6f")
    start_lat = st.number_input("起点纬度 (GCJ-02)", value=39.90923, format="%.6f")
    end_lng = st.number_input("终点经度 (GCJ-02)", value=116.407428, format="%.6f")
    end_lat = st.number_input("终点纬度 (GCJ-02)", value=39.91923, format="%.6f")

    st.divider()

    # 障碍物管理
    st.subheader("🚧 障碍物管理")
    st.write(f"当前障碍物数量: **{len(st.session_state.obstacles)}**")

    # 导出 JSON
    if st.session_state.obstacles:
        obs_json = json.dumps(st.session_state.obstacles, indent=4, ensure_ascii=False)
        st.download_button(
            label="💾 下载障碍物配置 (JSON)",
            data=obs_json,
            file_name="obstacles_config.json",
            mime="application/json"
        )

    # 清空按钮
    if st.button("🗑️ 清空所有障碍物"):
        st.session_state.obstacles = []
        st.rerun()

# ==========================================
# 4. 地图绘制逻辑
# ==========================================

# 默认中心点 (北京)
m = folium.Map(location=[39.90923, 116.397428], zoom_start=15, tiles=None)

# 添加高德卫星图层 (需要转换坐标系，这里直接使用 WGS84 坐标系的瓦片或者使用OpenStreetMap演示)
# 注意：Streamlit Folium 默认使用 Leaflet，坐标系为 WGS84
# 为了演示方便，这里使用 OpenStreetMap，实际部署建议配置高德/天地图 WGS84 接口
folium.TileLayer('OpenStreetMap').add_to(m)
# 如果有高德 WGS84 的 URL，可以在这里 add_to(m)

# 绘制已有的障碍物
for obs in st.session_state.obstacles:
    folium.Polygon(
        locations=obs['coords'],
        color="red",
        weight=2,
        fill=True,
        fill_color="red",
        fill_opacity=0.4,
        tooltip=f"高度: {obs['height']}m"
    ).add_to(m)

# 绘制起终点 (转换坐标系)
# 注意：输入是GCJ02，地图是WGS84，必须转换
wgs_start_lng, wgs_start_lat = gcj02_to_wgs84(start_lng, start_lat)
wgs_end_lng, wgs_end_lat = gcj02_to_wgs84(end_lng, end_lat)

folium.Marker([wgs_start_lat, wgs_start_lng], popup="起点", icon=folium.Icon(color='green', icon='play')).add_to(m)
folium.Marker([wgs_end_lat, wgs_end_lng], popup="终点", icon=folium.Icon(color='red', icon='stop')).add_to(m)

# 绘制简单的直线航线 (演示用)
folium.PolyLine(
    [[wgs_start_lat, wgs_start_lng], [wgs_end_lat, wgs_end_lng]],
    color="blue",
    weight=2.5,
    opacity=0.7,
    dash_array='5, 5'
).add_to(m)

# 添加绘图控件
draw = Draw(
    export=False,
    draw_options={
        'polyline': False,
        'rectangle': False,
        'circle': False,
        'marker': False,
        'circlemarker': False,
    }
)
draw.add_to(m)

# ==========================================
# 5. 交互逻辑处理
# ==========================================

# 显示地图并获取用户绘制数据
output = st_folium(m, width=700, height=500)

# 处理新绘制的障碍物
if output and output['last_active_drawing']:
    geom = output['last_active_drawing']
    if geom['geometry']['type'] == 'Polygon':
        coords = geom['geometry']['coordinates'][0] # 获取外环坐标

        # 弹出对话框获取高度 (Streamlit 原生不支持弹窗，这里用简单的输入框代替，或者在侧边栏处理)
        # 为了体验，我们假设新添加的障碍物默认高度为 50米，或者让用户在侧边栏输入
        st.info("检测到新绘制的障碍物")

        # 这里做一个简单的逻辑：添加到列表
        # 实际项目中，你可能需要一个 modal 来输入高度
        new_obs = {
            "id": len(st.session_state.obstacles) + 1,
            "height": 50, # 默认高度
            "coords": coords
        }
        st.session_state.obstacles.append(new_obs)
        st.rerun()

# ==========================================
# 6. 航线规划逻辑展示
# ==========================================

st.subheader("📊 规划分析结果")

if st.button("🚀 生成规划方案"):
    with st.spinner('正在计算避障路径...'):
        # 这里模拟复杂的计算过程
        # 实际逻辑：遍历 st.session_state.obstacles，计算与直线的相交，生成绕行点

        st.success("规划完成！")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("总距离", "1.24 km")
            st.metric("预计耗时", "4 分钟")

        with col2:
            st.metric("障碍物数量", len(st.session_state.obstacles))
            st.metric("策略", "自动绕行" if len(st.session_state.obstacles) > 0 else "直线飞行")

        st.write("**避障策略详情:**")
        if len(st.session_state.obstacles) == 0:
            st.write("✅ 路径畅通，无物理障碍。")
        else:
            st.write("⚠️ 检测到障碍物，已生成以下规避策略：")
            for obs in st.session_state.obstacles:
                if obs['height'] < flight_height:
                    st.write(f"- 障碍物 #{obs['id']}: 高度 {obs['height']}m < 飞行高度 {flight_height}m -> **直接飞越**")
                else:
                    st.write(f"- 障碍物 #{obs['id']}: 高度 {obs['height']}m >= 飞行高度 {flight_height}m -> **侧向绕行**")
