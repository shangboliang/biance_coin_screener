"""
@author beck
Streamlit Web Dashboard for POC Monitor
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict

import pandas as pd
import plotly.express as px
import streamlit as st

from auth import WebAuthenticator
from config import Config
from database import DatabaseManager
from poc_calculator import POCLevels
import os

# 页面配置
st.set_page_config(
    page_title=Config.STREAMLIT_PAGE_TITLE,
    page_icon=Config.STREAMLIT_PAGE_ICON,
    layout=Config.STREAMLIT_LAYOUT
)

# ==================== 访问控制 ====================
if Config.ENABLE_WEB_AUTH:
    authenticator = WebAuthenticator()
    if not authenticator.require_authentication():
        st.stop()

# 初始化数据库
@st.cache_resource
def get_database():
    """获取数据库实例"""
    return DatabaseManager()

db = get_database()


# ==================== 辅助函数 ====================

def get_impact_emoji(count: int) -> str:
    """获取冲击力等级emoji"""
    if count in Config.IMPACT_LEVELS:
        return Config.IMPACT_LEVELS[count]["emoji"]
    return "➡️"


def get_impact_color(count: int) -> str:
    """获取冲击力等级颜色"""
    if count in Config.IMPACT_LEVELS:
        return Config.IMPACT_LEVELS[count]["color"]
    return "#87CEEB"


def clean_poc_data(poc_data: Dict) -> Dict:
    """清理POC数据，移除数据库字段"""
    return {k: v for k, v in poc_data.items() if k != 'id'}


def get_coin_age_map() -> Dict[str, int]:
    """
    [新增] 获取全市场币种的年龄映射
    Returns: { 'BTCUSDT': 9999, 'ACTUSDT': 20, ... }
    """
    all_levels = db.get_all_latest_poc_levels()
    age_map = {}
    for item in all_levels:
        days = item.get('days_active')
        if days is None:
            days = 9999
        age_map[item['symbol']] = int(days)
    return age_map


def create_heatmap_data(poc_levels_list: List[Dict]) -> pd.DataFrame:
    """
    [已恢复] 创建热图数据 - 计算价格距离POC的百分比
    虽然新的 show_heatmap 有自己的逻辑，但为了保持代码完整性保留此函数
    """
    data = []
    for poc_data in poc_levels_list:
        poc_levels = POCLevels(**clean_poc_data(poc_data))

        # 需要展示的 6 个关卡
        poc_types = ["MPOC", "PMPOC", "PPMPOC", "QPOC", "PQPOC", "PPQPOC"]

        for poc_type in poc_types:
            poc_value = poc_levels.get_poc_value(poc_type)

            if poc_value and poc_value > 0:
                # 核心逻辑：计算距离百分比
                diff_percent = (poc_levels.current_price - poc_value) / poc_value * 100

                data.append({
                    "symbol": poc_levels.symbol,
                    "poc_type": poc_type,
                    "diff_percent": diff_percent,
                    "text": f"{diff_percent:+.2f}%"
                })
            else:
                data.append({
                    "symbol": poc_levels.symbol,
                    "poc_type": poc_type,
                    "diff_percent": None,
                    "text": "N/A"
                })

    if data:
        df = pd.DataFrame(data)
        pivot = df.pivot(index="symbol", columns="poc_type", values="diff_percent")
        return pivot
    return pd.DataFrame()


# ==================== 页面组件 ====================

def show_statistics():
    """显示统计信息"""
    stats = db.get_statistics()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="监控交易对",
            value=stats.get("total_symbols", 0),
            delta=None
        )

    with col2:
        st.metric(
            label="总穿透事件",
            value=stats.get("total_events", 0),
            delta=None
        )

    with col3:
        st.metric(
            label="今日事件",
            value=stats.get("today_events", 0),
            delta=None
        )

    with col4:
        st.metric(
            label="未通知事件",
            value=stats.get("unnotified_events", 0),
            delta=None
        )


def show_heatmap():
    """
    显示距离百分比热力图
    包含：新老币筛选、POC筛选、TV导出功能
    """
    st.subheader("🗺️ POC 距离概览 (表格热力图)")

    # --- 1. 获取数据 ---
    poc_levels_list = db.get_all_latest_poc_levels()
    if not poc_levels_list:
        st.warning("暂无数据，请先运行监控")
        return

    # --- 2. 筛选设置区域 ---
    with st.expander("🔍 筛选与设置", expanded=True):
        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            # 基础搜索与设置
            search_query = st.text_input("搜索币种", "").upper()
            threshold = st.slider("颜色饱和阈值 (%)", 1, 50, 15, help="超过这个百分比显示为最红/最绿")

        with col2:
            # [新增] 新老币筛选
            age_filter = st.radio("币种年限", ["全部", "新币 (🆕)", "老币"])
            # 安全获取配置里的阈值
            new_coin_days = getattr(Config, 'NEW_COIN_THRESHOLD_DAYS', 60)

        with col3:
            filter_conditions = st.multiselect(
                "只显示满足以下条件的币种:",
                [
                    "价格 > QPOC (当季)",
                    "价格 > PQPOC (上季)",
                    "价格 > PPQPOC (前季)",
                    "价格 > MPOC (当月)",
                    "价格 > PMPOC (上月)",
                    "价格 > PPMPOC (前月)"
                ],
                default=[]
            )
            display_limit = st.slider("显示数量", 0, 500, 100)

    # --- 3. 准备筛选逻辑 ---
    condition_map = {
        "价格 > QPOC (当季)": "QPOC",
        "价格 > PQPOC (上季)": "PQPOC",
        "价格 > PPQPOC (前季)": "PPQPOC",
        "价格 > MPOC (当月)": "MPOC",
        "价格 > PMPOC (上月)": "PMPOC",
        "价格 > PPMPOC (前月)": "PPMPOC"
    }

    # --- 4. 执行筛选 ---
    filtered_data = []
    for poc_data in poc_levels_list:
        p = POCLevels(**clean_poc_data(poc_data))

        # A. 搜索过滤
        if search_query and search_query not in p.symbol:
            continue

        # B. [新增] 新老币过滤
        days = 9999
        if p.days_active is not None:
            try:
                days = int(p.days_active)
            except:
                pass

        if age_filter == "新币 (🆕)" and days >= new_coin_days:
            continue
        if age_filter == "老币" and days < new_coin_days:
            continue

        # C. 逻辑条件过滤
        is_match = True
        for label in filter_conditions:
            target_poc_key = condition_map[label]
            val = p.get_poc_value(target_poc_key)
            if not val or p.current_price <= val:
                is_match = False
                break
        if not is_match:
            continue

        filtered_data.append(poc_data)

    # 数量限制
    if display_limit > 0:
        filtered_data = filtered_data[:display_limit]

    if not filtered_data:
        st.warning("没有符合条件的币种")
        return

    # ==================== 生成 TV 导入文件 ====================
    # 1. 生成内容
    tv_lines = []
    for item in filtered_data:
        line = f"BINANCE:{item['symbol']}.p"
        tv_lines.append(line)
    tv_content = "\n".join(tv_lines)

    # 2. 生成文件名
    utc8_time = datetime.utcnow() + timedelta(hours=8)
    date_str = utc8_time.strftime("%Y%m%d")

    if filter_conditions:
        short_names = [condition_map[c] for c in filter_conditions]
        condition_str = "-".join(short_names)
        file_name = f"{condition_str}-{date_str}.txt"
    else:
        file_name = f"{date_str}.txt"

    # 如果有新老币筛选，加后缀
    if age_filter != "全部":
        file_name = f"{age_filter}-{file_name}"

    # 3. 显示下载按钮
    st.download_button(
        label=f"📥 下载导入 TV 列表 ({len(tv_lines)}个)",
        data=tv_content,
        file_name=file_name,
        mime="text/plain",
        help="下载后在 TradingView 自选列表中选择 '从文件导入...'"
    )
    # ===============================================================

    # --- 5. 生成表格数据 ---
    data_list = []
    for poc_data in filtered_data:
        poc_levels = POCLevels(**clean_poc_data(poc_data))

        # 获取天数
        days = 9999
        if poc_levels.days_active is not None:
            try:
                days = int(poc_levels.days_active)
            except:
                pass

        display_symbol = poc_levels.symbol
        if days < new_coin_days:
            display_symbol = f"{poc_levels.symbol} 🆕"

        row = {
            "交易对": display_symbol,
            "上市天数": days if days != 9999 else "N/A"
        }

        # 计算百分比
        for poc_type in ["MPOC", "PMPOC", "PPMPOC", "QPOC", "PQPOC", "PPQPOC"]:
            val = poc_levels.get_poc_value(poc_type)
            if val and val > 0:
                diff = (poc_levels.current_price - val) / val * 100
                row[poc_type] = diff
            else:
                row[poc_type] = None
        data_list.append(row)

    # --- 6. 渲染美化表格 ---
    df = pd.DataFrame(data_list)
    df = df.set_index("交易对")

    cols = ["MPOC", "PMPOC", "PPMPOC", "QPOC", "PQPOC", "PPQPOC"]
    valid_cols = [c for c in cols if c in df.columns]

    st.dataframe(
        df[valid_cols].style
        .format("{:+.2f}%", na_rep="N/A")
        .background_gradient(
            cmap="RdYlGn",
            vmin=-threshold,
            vmax=threshold,
            axis=None
        )
        .highlight_null(color='#f0f2f6'),
        use_container_width=True,
        height=600
    )


def show_poc_table():
    """显示POC数据表"""
    st.subheader("📊 POC数据表")

    # 获取最新POC数据
    poc_levels_list = db.get_all_latest_poc_levels()

    if not poc_levels_list:
        st.warning("暂无数据，请先运行监控")
        return

    # 转换为DataFrame
    df = pd.DataFrame(poc_levels_list)

    # 添加冲击力等级
    df["breakthrough_count"] = df.apply(
        lambda row: sum([
            1 if row["current_price"] > row[poc] else 0
            for poc in ["mpoc", "pmpoc", "ppmpoc", "qpoc", "pqpoc", "ppqpoc"]
            if pd.notna(row[poc])
        ]),
        axis=1
    )

    df["impact_emoji"] = df["breakthrough_count"].apply(get_impact_emoji)

    # 选择显示的列
    display_columns = [
        "symbol", "current_price", "impact_emoji", "breakthrough_count",
        "mpoc", "pmpoc", "ppmpoc", "qpoc", "pqpoc", "ppqpoc", "timestamp"
    ]

    # 过滤选项
    col1, col2 = st.columns(2)

    with col1:
        min_impact = st.selectbox(
            "最小冲击力等级",
            options=[0, 1, 2, 3, 4, 5, 6],
            index=0
        )

    with col2:
        search_symbol = st.text_input("搜索交易对(Table)", "")

    # 应用过滤
    filtered_df = df[df["breakthrough_count"] >= min_impact]
    if search_symbol:
        filtered_df = filtered_df[
            filtered_df["symbol"].str.contains(search_symbol.upper())
        ]

    # 排序
    filtered_df = filtered_df.sort_values("breakthrough_count", ascending=False)

    # 显示表格
    st.dataframe(
        filtered_df[display_columns],
        use_container_width=True,
        height=400
    )

    # 导出功能
    if st.button("导出为CSV"):
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="下载CSV文件",
            data=csv,
            file_name=f"poc_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )


def show_crossover_events():
    """
    显示穿透事件 (支持 新老币 & 冲击力 筛选)
    """
    st.subheader("🚀 穿透事件历史")

    # 1. 准备辅助数据：建立 币种->天数 映射
    age_map = get_coin_age_map()
    new_coin_days = getattr(Config, 'NEW_COIN_THRESHOLD_DAYS', 60)

    # 2. 筛选控件
    with st.expander("🔍 事件筛选", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            # [新增] 冲击力筛选
            selected_impact = st.multiselect(
                "冲击力等级",
                options=[1, 2, 3, 4, 5, 6],
                default=[1, 2, 3, 4, 5, 6]
            )

        with col2:
            # [新增] 新老币筛选
            age_filter = st.radio(
                "币种年限",
                ["全部", "新币 (🆕)", "老币"],
                horizontal=True,
                key="event_age_filter"
            )

        with col3:
            symbol_filter = st.text_input("筛选交易对(Events)", "")
            limit = st.selectbox("显示数量", [50, 100, 200, 500, 1000], index=1)

    # 3. 获取原始数据
    raw_events = db.get_crossover_events(
        symbol=symbol_filter.upper() if symbol_filter else None,
        limit=1000
    )

    if not raw_events:
        st.info("暂无穿透事件")
        return

    # 4. 数据处理与筛选
    df = pd.DataFrame(raw_events)

    # 4.1 映射天数
    df['days_active'] = df['symbol'].map(age_map).fillna(9999)

    # 4.2 筛选冲击力
    if selected_impact:
        df = df[df['impact_level'].isin(selected_impact)]

    # 4.3 筛选新老币
    if age_filter == "新币 (🆕)":
        df = df[df['days_active'] < new_coin_days]
    elif age_filter == "老币":
        df = df[df['days_active'] >= new_coin_days]

    # 4.4 截取数量
    df = df.head(limit)

    if df.empty:
        st.warning("筛选条件下无数据")
        return

    # 5. 展示
    df["change_formatted"] = df["change_percent"].apply(lambda x: f"{x:+.2f}%")

    # 格式化显示列
    display_cols = ["symbol", "poc_type", "poc_value", "price_after", "change_formatted", "impact_emoji", "timestamp", "days_active"]
    col_map = {
        "symbol": "交易对", "poc_type": "POC类型", "poc_value": "POC价格",
        "price_after": "突破价格", "change_formatted": "涨幅",
        "impact_emoji": "等级", "timestamp": "时间", "days_active": "上市天数"
    }

    st.dataframe(
        df[display_cols].rename(columns=col_map),
        use_container_width=True,
        height=500
    )

    # 统计图表
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        # POC类型分布
        poc_type_counts = df["poc_type"].value_counts()
        fig1 = px.bar(
            x=poc_type_counts.index,
            y=poc_type_counts.values,
            labels={"x": "POC类型", "y": "事件数量"},
            title="筛选后-POC类型分布"
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        # 冲击力等级分布
        impact_counts = df["impact_level"].value_counts().sort_index()
        fig2 = px.pie(
            values=impact_counts.values,
            names=[f"等级{i}" for i in impact_counts.index],
            title="筛选后-冲击力占比"
        )
        st.plotly_chart(fig2, use_container_width=True)


def show_custom_query():
    """显示自定义查询"""
    st.subheader("🔍 自定义查询")

    st.markdown("""
    ### 查询语法示例
    - 价格突破多个POC: `current_price > qpoc AND current_price > pqpoc`
    - 价格接近QPOC: `ABS(current_price - qpoc) / qpoc < 0.01`
    - 新币强势突破: `days_active < 60 AND current_price > qpoc`
    """)

    # 预设查询
    preset_queries = {
        "突破所有季度POC": "current_price > qpoc AND current_price > pqpoc AND current_price > ppqpoc",
        "突破所有月度POC": "current_price > mpoc AND current_price > pmpoc AND current_price > ppmpoc",
        "接近当季POC (1%)": "ABS(current_price - qpoc) / qpoc < 0.01",
        "新币强势突破 (天数<60)": "days_active < 60 AND current_price > qpoc",
        "高于全局POC": "current_price > global_poc"
    }

    selected_preset = st.selectbox("选择预设查询", ["自定义"] + list(preset_queries.keys()))

    if selected_preset == "自定义":
        condition = st.text_area("输入SQL WHERE条件", "current_price > qpoc")
    else:
        condition = preset_queries[selected_preset]
        st.code(condition, language="sql")

    if st.button("执行查询"):
        try:
            results = db.query_by_condition(condition)

            if results:
                df = pd.DataFrame(results)
                st.success(f"找到 {len(results)} 个符合条件的交易对")

                # 显示结果
                display_columns = [
                    "symbol", "current_price",
                    "mpoc", "pmpoc", "ppmpoc",
                    "qpoc", "pqpoc", "ppqpoc",
                    "timestamp"
                ]
                # 如果有 days_active 也显示
                if "days_active" in df.columns:
                    display_columns.append("days_active")

                st.dataframe(df[display_columns], use_container_width=True)
            else:
                st.warning("未找到符合条件的数据")

        except Exception as e:
            st.error(f"查询失败: {e}")


def show_hot_symbols():
    """显示热门币种 (最接近POC关卡)"""
    st.subheader("🔥 热门币种 (最接近POC关卡)")

    # 获取所有POC数据
    poc_levels_list = db.get_all_latest_poc_levels()

    if not poc_levels_list:
        st.warning("暂无数据")
        return

    # 计算热度
    hot_data = []
    for poc_data in poc_levels_list:
        poc_levels = POCLevels(**clean_poc_data(poc_data))

        # 计算到每个POC的距离
        poc_types = ["MPOC", "PMPOC", "PPMPOC", "QPOC", "PQPOC", "PPQPOC"]
        min_distance = float('inf')
        nearest_poc = ""

        for poc_type in poc_types:
            poc_value = poc_levels.get_poc_value(poc_type)
            if poc_value:
                distance = abs(poc_levels.current_price - poc_value) / poc_value * 100
                if distance < min_distance:
                    min_distance = distance
                    nearest_poc = poc_type

        if min_distance != float('inf'):
            hot_data.append({
                "symbol": poc_levels.symbol,
                "current_price": poc_levels.current_price,
                "nearest_poc": nearest_poc,
                "distance_percent": min_distance,
                "breakthrough_count": poc_levels.count_breakthroughs(),
                "impact_emoji": get_impact_emoji(poc_levels.count_breakthroughs())
            })

    # 排序
    hot_data.sort(key=lambda x: x["distance_percent"])

    # 显示数量选择
    top_n = st.slider("显示数量", 10, 50, 20)

    # 转换为DataFrame
    df = pd.DataFrame(hot_data[:top_n])

    # 重命名列
    column_names = {
        "symbol": "交易对",
        "current_price": "当前价格",
        "nearest_poc": "最近POC",
        "distance_percent": "距离(%)",
        "breakthrough_count": "突破数",
        "impact_emoji": "等级"
    }

    st.dataframe(
        df.rename(columns=column_names),
        use_container_width=True,
        height=400
    )


def show_breakout_leaders():
    """显示强势突破榜 (远离成本区)"""
    st.subheader("🚀 强势突破榜 (趋势最强)")

    # 获取数据
    poc_levels_list = db.get_all_latest_poc_levels()
    if not poc_levels_list:
        st.warning("暂无数据")
        return

    leader_data = []
    for poc_data in poc_levels_list:
        poc_levels = POCLevels(**clean_poc_data(poc_data))

        # 核心逻辑：计算相对于 QPOC (季度成本) 的乖离率
        # 如果没有 QPOC，降级使用 MPOC
        benchmark_poc = poc_levels.get_poc_value("QPOC") or poc_levels.get_poc_value("MPOC")

        if benchmark_poc and poc_levels.current_price > benchmark_poc:
            # 计算乖离率: (当前价 - 成本价) / 成本价
            deviation = (poc_levels.current_price - benchmark_poc) / benchmark_poc * 100

            leader_data.append({
                "symbol": poc_levels.symbol,
                "current_price": poc_levels.current_price,
                "benchmark_price": benchmark_poc,
                "deviation_percent": deviation,  # 乖离率
                "breakthrough_count": poc_levels.count_breakthroughs(),
                "impact_emoji": get_impact_emoji(poc_levels.count_breakthroughs())
            })

    if not leader_data:
        st.info("当前市场暂无显著突破 QPOC/MPOC 的强势币种")
        return

    # 按乖离率从大到小排序（涨得越猛越靠前）
    leader_data.sort(key=lambda x: x["deviation_percent"], reverse=True)

    # 交互：选择显示数量
    top_n = st.slider("显示强势币数量", 10, 100, 20, key="breakout_slider")

    # 构建 DataFrame
    df = pd.DataFrame(leader_data[:top_n])

    # 格式化显示
    display_df = df.rename(columns={
        "symbol": "交易对",
        "current_price": "当前价格",
        "benchmark_price": "基准POC(季/月)",
        "deviation_percent": "乖离率(%)",  # 这里的数字越大，说明离成本区越远，趋势越强
        "impact_emoji": "强度等级"
    })

    st.dataframe(
        display_df[["交易对", "当前价格", "乖离率(%)", "基准POC(季/月)", "强度等级"]],
        use_container_width=True,
        height=400
    )


# ==================== 主界面 ====================

def main():
    """主函数"""
    st.title("📊 币安POC监控工具")
    st.markdown("---")

    # 侧边栏
    with st.sidebar:
        st.header("导航")
        page = st.radio(
            "选择页面",
            [
                "📈 概览",  # 综合看板
                "🚀 强势突破榜",  # <--- 新增：专门看 DUSK 这种起飞的币
                "🗺️ POC热图",  # 已升级：支持过滤和全显
                "🔥 热门币种 (测试中)",  # <--- 改名：更准确，指回踩关键位的币
                "📊 POC数据表",
                "⚡ 穿透事件历史",  # 改个图标避免和突破榜混淆
                "🔍 自定义查询"
            ]
        )

        st.markdown("---")
        st.header("操作")

        if st.button("🔄 刷新数据"):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")

        # 代理状态显示
        binance_proxy_status = "启用" if Config.BINANCE_USE_PROXY else "禁用"
        telegram_proxy_status = "启用" if Config.TELEGRAM_USE_PROXY else "禁用"

        st.info(f"""
        **系统信息**

        数据库: {Config.DB_NAME}

        监控间隔: {Config.MONITOR_INTERVAL}秒

        币安API代理: {binance_proxy_status}

        Telegram代理: {telegram_proxy_status}
        """)

    # 显示统计信息
    show_statistics()
    st.markdown("---")

    # ==================== 页面路由逻辑 ====================

    if page == "📈 概览":
        st.header("全市场扫描概览")

        # 将概览页分为左右两栏，形成鲜明对比
        col1, col2 = st.columns(2)

        with col1:
            st.info("🎯 **回踩蓄力 (测试关键位)**")
            show_hot_symbols()

        with col2:
            st.success("🚀 **趋势爆发 (远离成本区)**")
            show_breakout_leaders()

        st.markdown("---")

        # 在下方显示最近的穿透记录，作为即时动态补充
        st.subheader("📋 最新穿透动态")
        events = db.get_crossover_events(limit=5)  # 只显示最新的5条，避免太长
        if events:
            # 简略显示，使用 columns 一行显示一条
            for event in events:
                c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
                c1.write(f"**{event['symbol']}**")
                c2.write(f"{event['impact_emoji']} 突破 {event['poc_type']}")
                c3.write(f"涨幅: `{event['change_percent']:+.2f}%`")
                c4.caption(f"{event['timestamp']}")
        else:
            st.caption("暂无最新动态")

    elif page == "🚀 强势突破榜":
        show_breakout_leaders()

    elif page == "🗺️ POC热图":
        show_heatmap()

    elif page == "🔥 热门币种 (测试中)":
        show_hot_symbols()

    elif page == "📊 POC数据表":
        show_poc_table()

    elif page == "⚡ 穿透事件历史":
        show_crossover_events()

    elif page == "🔍 自定义查询":
        show_custom_query()


if __name__ == "__main__":
    main()