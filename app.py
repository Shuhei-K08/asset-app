from datetime import date

import pandas as pd
import streamlit as st
import httpx
from postgrest.exceptions import APIError
from supabase import create_client
import altair as alt
import datetime

today = datetime.date.today()

st.markdown("""
<style>

/* 背景グラデーション */
.stApp {
    background: linear-gradient(135deg, #f5f7fa, #e4ecf7);
}

/* ヘッダー */
.app-header {
    font-size: 28px;
    font-weight: 800;
    padding: 10px 0;
    color: #1f2937;
}

/* KPIカード */
.kpi-card {
    background: white;
    border-radius: 16px;
    padding: 18px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.08);
    text-align: center;
}

.kpi-value {
    font-size: 26px;
    font-weight: bold;
}

.kpi-label {
    font-size: 13px;
    color: #6b7280;
}

/* ホバーで浮く */
.card:hover {
    transform: translateY(-3px);
    transition: 0.2s;
}

/* ボタン改善 */
.stButton > button {
    background: linear-gradient(135deg, #f45b22, #ff7b54);
    color: white;
    border: none;
}

</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="資産管理アプリ", page_icon="💰", layout="wide")

ACCENT = "#f45b22"
NAVY = "#30475e"
MUTED = "#6b7c8f"
TYPE_LABELS = {"expense": "支出", "income": "収入"}
TYPE_VALUES = {"支出": "expense", "収入": "income"}
TABLE_COLUMNS = {
    "categories": "id,name,type",
    "transactions": "id,date,type,amount,category,description",
    "budgets": "id,category,amount",
    "balance_snapshots": "id,snapshot_month,balance,created_at",
    "recurring_transactions": "id,day,type,amount,category,description,start_month,end_month,active,created_at",
}

st.markdown(
    f"""
    <style>
    .stApp {{ background: #fbfbfa; }}
    h1, h2, h3 {{ letter-spacing: 0; }}
    .sheet-title {{
        color: {ACCENT};
        font-size: 2.1rem;
        font-weight: 800;
        margin: 0 0 .5rem;
    }}
    .sheet-caption {{
        color: {MUTED};
        font-size: .95rem;
        margin-bottom: 1rem;
    }}
    .claim-box {{
        display: inline-flex;
        gap: .75rem;
        align-items: center;
        background: #f1f2f4;
        color: #111827;
        font-weight: 700;
        padding: .25rem .5rem;
        margin: .25rem 0 1rem;
    }}
    .budget-card {{
        border: 1px solid #d7dbe0;
        background: #eef0f2;
        padding: 2rem;
        text-align: center;
        min-height: 210px;
    }}
    .budget-card .big {{
        color: {NAVY};
        font-size: 2.5rem;
        font-weight: 700;
        line-height: 1.1;
    }}
    .budget-card .label {{
        color: {MUTED};
        font-weight: 700;
        margin-top: .25rem;
    }}
    .budget-card hr {{
        width: 65%;
        border: 0;
        border-top: 2px dotted #b8bec6;
        margin: 1.3rem auto;
    }}
    div[data-testid="stMetricValue"] {{ color: {NAVY}; }}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_supabase_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def yen(value: float | int) -> str:
    return f"¥{int(value):,}"


def type_label(value: str) -> str:
    return TYPE_LABELS.get(value, value)


def type_value(label: str) -> str:
    return TYPE_VALUES.get(label, label)


def first_day(value: date | pd.Timestamp) -> date:
    return pd.to_datetime(value).date().replace(day=1)


def month_range(value: date | pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(first_day(value))
    end = start + pd.offsets.MonthEnd(0)
    return start, end


def month_label(value: date | pd.Timestamp) -> str:
    value = pd.Timestamp(value)
    return f"{value.year}年{value.month}月"


def month_selector(label: str, key: str, default: date | None = None) -> date:
    default = first_day(default or date.today())
    years = list(range(default.year - 5, default.year + 6))
    cols = st.columns([1, 1])
    year = cols[0].selectbox(f"年", years, index=years.index(default.year), key=f"{key}_year")
    month = cols[1].selectbox(f"月", list(range(1, 13)), index=default.month - 1, key=f"{key}_month")
    return date(int(year), int(month), 1)


def load_table(table_name: str, limit: int = 10000) -> pd.DataFrame:
    columns = TABLE_COLUMNS.get(table_name, "*")
    query = supabase.table(table_name).select(columns).limit(limit)
    if table_name == "transactions":
        query = query.order("date", desc=False)
    response = query.execute()
    return pd.DataFrame(response.data or [])


def load_optional_table(table_name: str) -> tuple[pd.DataFrame, bool]:
    try:
        return load_table(table_name), True
    except APIError:
        return pd.DataFrame(), False
    except httpx.TimeoutException:
        return pd.DataFrame(), False


def load_table_or_empty(table_name):
    import pandas as pd

    try:
        res = supabase.table(table_name).select("*").execute()
        df = pd.DataFrame(res.data)

        # 👇 これ追加（最重要）
        if table_name == "recurring_transactions" and df.empty:
            df = pd.DataFrame(columns=[
                "id",
                "type",
                "amount",
                "category",
                "description",
                "start_month",
                "end_month"
            ])

        return df

    except Exception as e:
        print(f"[load error] {table_name}:", e)
        return pd.DataFrame()

def normalize_transactions(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame(columns=["id", "date", "type", "amount", "category", "description", "signed_amount"])

    data = data.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["amount"] = pd.to_numeric(data["amount"], errors="coerce").fillna(0)
    if "description" not in data.columns:
        data["description"] = ""
    data["description"] = data["description"].fillna("")
    data["signed_amount"] = data.apply(
        lambda row: row["amount"] if row["type"] == "income" else -row["amount"],
        axis=1,
    )
    return data.dropna(subset=["date"])


def normalize_budgets(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame(columns=["id", "category", "amount"])

    data = data.copy()
    data["amount"] = pd.to_numeric(data["amount"], errors="coerce").fillna(0)

    return data

def normalize_snapshots(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame(columns=["id", "snapshot_month", "balance"])

    data = data.copy()
    data["snapshot_month"] = pd.to_datetime(data["snapshot_month"], errors="coerce")
    data["balance"] = pd.to_numeric(data["balance"], errors="coerce").fillna(0)
    return data.dropna(subset=["snapshot_month"]).sort_values("snapshot_month")


def normalize_recurring(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame(
            columns=["id", "day", "type", "amount", "category", "description", "start_month", "end_month", "active"]
        )

    data = data.copy()
    data["day"] = pd.to_numeric(data["day"], errors="coerce").fillna(1).astype(int)
    data["amount"] = pd.to_numeric(data["amount"], errors="coerce").fillna(0)
    data["start_month"] = pd.to_datetime(data["start_month"], errors="coerce")
    data["end_month"] = pd.to_datetime(data["end_month"], errors="coerce")
    if "description" not in data.columns:
        data["description"] = ""
    if "active" not in data.columns:
        data["active"] = True
    data["description"] = data["description"].fillna("")
    data["active"] = data["active"].fillna(True)
    return data.dropna(subset=["start_month"])


def save_transaction(tx_date: date, tx_type: str, category: str, amount: int, description: str):
    supabase.table("transactions").insert(
        {
            "date": tx_date.isoformat(),
            "type": tx_type,
            "amount": amount,
            "category": category,
            "description": description.strip(),
        }
    ).execute()


def delete_transaction(transaction_id: int):
    supabase.table("transactions").delete().eq("id", transaction_id).execute()


def save_budget(category: str, amount: int):
    supabase.table("budgets").upsert(
        {
            "category": category,
            "amount": amount
        },
        on_conflict="category"
    ).execute()


def save_category(name: str, category_type: str):
    supabase.table("categories").insert({"name": name.strip(), "type": category_type}).execute()


def delete_category(category_id: int):
    supabase.table("categories").delete().eq("id", category_id).execute()


def save_balance_snapshot(snapshot_month: date, balance: int):
    # 既存全部削除
    supabase.table("balance_snapshots").delete().neq("id", 0).execute()

    # 新規追加
    supabase.table("balance_snapshots").insert({
        "snapshot_month": snapshot_month.isoformat(),
        "balance": balance
    }).execute()


def save_recurring(type, amount, category, desc, start_month, end_month):

    supabase.table("recurring_transactions").insert({
        "type": type,
        "amount": amount,
        "category": category,
        "description": desc,
        "start_month": start_month.strftime("%Y-%m-%d"),
        "end_month": end_month.strftime("%Y-%m-%d") if end_month else None
    }).execute()

def delete_recurring(recurring_id, delete_mode):

    now = pd.Timestamp.today().strftime("%Y-%m-%d")

    if delete_mode == "all":
        supabase.table("recurring_transactions") \
            .update({
                "is_deleted": True,
                "deleted_at": now
            }) \
            .eq("id", int(recurring_id)) \
            .execute()

    elif delete_mode == "future":
        this_month = pd.Timestamp.today().replace(day=1)

        supabase.table("recurring_transactions") \
            .update({
                "end_month": this_month.strftime("%Y-%m-%d")
            }) \
            .eq("id", int(recurring_id)) \
            .execute()
        
def apply_recurring(month_df, recurring_df, selected_month):

    if recurring_df.empty:
        return month_df

    current_month = pd.to_datetime(selected_month).to_period("M").to_timestamp()

    rows = []

    for _, row in recurring_df.iterrows():

        start = pd.to_datetime(row["start_month"])
        end = pd.to_datetime(row["end_month"]) if pd.notnull(row["end_month"]) else None

        # 👇 この月に適用されるか
        if start <= current_month and (end is None or current_month <= end):

            rows.append({
                "date": current_month,
                "type": row["type"],
                "category": row["category"],
                "amount": row["amount"],
                "description": row.get("description", "定期")
            })

    if rows:
        recurring_month_df = pd.DataFrame(rows)
        month_df = pd.concat([month_df, recurring_month_df], ignore_index=True)

    return month_df


def format_jp_date(value: pd.Timestamp) -> str:
    return f"{value.year}年{value.month}月{value.day}日"


def display_transactions(data: pd.DataFrame, tx_type: str) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame(columns=["日付", "金額", "説明", "カテゴリ"])

    result = data.loc[data["type"] == tx_type, ["date", "amount", "description", "category"]].sort_values(
        "date", ascending=False
    )
    if result.empty:
        return pd.DataFrame(columns=["日付", "金額", "説明", "カテゴリ"])

    result = result.copy()
    result["日付"] = result["date"].apply(format_jp_date)
    result["金額"] = result["amount"].apply(yen)
    result = result.rename(columns={"description": "説明", "category": "カテゴリ"})
    return result[["日付", "金額", "説明", "カテゴリ"]]


def transactions_display_frame(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame(columns=["ID", "日付", "種別", "カテゴリ", "金額", "説明"])

    result = data.sort_values("date", ascending=False).copy()
    result["ID"] = result["id"]
    result["日付"] = result["date"]
    result["種別"] = result["type"].map(type_label)
    result["カテゴリ"] = result["category"]
    result["金額"] = result["amount"]
    result["説明"] = result["description"]
    return result[["ID", "日付", "種別", "カテゴリ", "金額", "説明"]]


def categories_display_frame(data: pd.DataFrame) -> pd.DataFrame:
    result = data.copy()
    result["ID"] = result["id"]
    result["カテゴリ名"] = result["name"]
    result["種別"] = result["type"].map(type_label)
    return result[["ID", "カテゴリ名", "種別"]]


def recurring_display_frame(df, category_list):

    if df.empty:
        return df

    result = df.copy()

    # 日付
    result["開始月"] = pd.to_datetime(result["start_month"], errors="coerce")
    result["終了月"] = pd.to_datetime(result["end_month"], errors="coerce")

    # 👇 ここでカテゴリ変換（これが正解の場所）
    result["カテゴリ"] = result["category"].apply(
        lambda x: x if x in category_list else "未分類"
    )

    # その他
    result = result.rename(columns={
        "id": "ID",
        "type": "種別",
        "amount": "金額",
        "description": "説明"
    })

    result["種別"] = result["種別"].map({
        "income": "収入",
        "expense": "支出"
    })

    return result[["ID", "種別", "カテゴリ", "金額", "開始月", "終了月", "説明"]]

def category_summary(
    month_df: pd.DataFrame,
    budgets_df: pd.DataFrame,
    categories: list[str],
    start: pd.Timestamp,
    tx_type: str,
) -> pd.DataFrame:
    actual = month_df[month_df["type"] == tx_type].groupby("category")["amount"].sum().rename("実際")

    planned = pd.Series(dtype=float, name="予定")
    if not budgets_df.empty:
        planned = budgets_df.set_index("category")["amount"].rename("予定")

    index = pd.Index(categories, name="カテゴリ")
    summary = pd.concat([planned, actual], axis=1).reindex(index).fillna(0)

    summary["差額"] = summary["予定"] - summary["実際"]
    if tx_type == "income":
        summary["差額"] = summary["実際"] - summary["予定"]

    return summary


def latest_snapshot_before(snapshots_df: pd.DataFrame, as_of: pd.Timestamp):
    if snapshots_df.empty:
        return None
    snapshot_ends = snapshots_df["snapshot_month"] + pd.offsets.MonthEnd(0)
    candidates = snapshots_df[snapshot_ends <= as_of]
    if candidates.empty:
        return None
    return candidates.iloc[-1]


def balance_at(transactions_df: pd.DataFrame, snapshots_df: pd.DataFrame, as_of: pd.Timestamp) -> int:
    if snapshots_df.empty:
        return 0

    # 最新の基準を取得
    latest = snapshots_df.sort_values("snapshot_month").iloc[-1]
    base_month = pd.Timestamp(latest["snapshot_month"])
    base_balance = int(latest["balance"])

    # 👉 基準より前は0
    if as_of < base_month:
        return 0

    # 基準以降のみ加算
    after = transactions_df[
        (transactions_df["date"] > (base_month + pd.offsets.MonthEnd(0)))
        & (transactions_df["date"] <= as_of)
    ]["signed_amount"].sum()

    return base_balance + int(after)

def month_balances(transactions_df: pd.DataFrame, snapshots_df: pd.DataFrame, selected_month: date) -> tuple[int, int]:
    start, end = month_range(selected_month)
    return (
        balance_at(transactions_df, snapshots_df, start - pd.Timedelta(days=1)),
        balance_at(transactions_df, snapshots_df, end),
    )


def monthly_asset_series(transactions_df: pd.DataFrame, snapshots_df: pd.DataFrame) -> pd.DataFrame:
    if snapshots_df.empty:
        return pd.DataFrame()

    latest = snapshots_df.sort_values("snapshot_month").iloc[-1]
    base_month = pd.Timestamp(latest["snapshot_month"])
    base_balance = int(latest["balance"])

    # 👉 基準以降のみ対象
    tx = transactions_df[transactions_df["date"] > (base_month + pd.offsets.MonthEnd(0))]

    # 基準前は0にするため、開始月固定
    if tx.empty:
        return pd.DataFrame({"月末残高": [base_balance]}, index=[base_month])

    monthly = tx.set_index("date")["signed_amount"].resample("ME").sum().cumsum()
    monthly = monthly + base_balance

    monthly.index = monthly.index.to_period("M").to_timestamp()

    # 基準月だけ追加
    base_row = pd.Series([base_balance], index=[base_month], name="月末残高")

    return pd.concat([base_row, monthly.rename("月末残高")]).to_frame()

def render_transaction_block(month_df, tx_type, title, categories, selected_month):

    base_key = f"{tx_type}_{title}"

    # =========================
    # 月固定（日付はサイドバーの月）
    # =========================
    tx_date = pd.to_datetime(selected_month).replace(day=1)

    # =========================
    # タイトル・合計
    # =========================
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)

    total = month_df.loc[month_df["type"] == tx_type, "amount"].sum()

    st.markdown(
        f'<div class="total">¥{int(total):,}</div>',
        unsafe_allow_html=True
    )

    # =========================
    # 入力フォーム（※日付なし）
    # =========================
    with st.form(f"{base_key}_form", clear_on_submit=True):

        cols = st.columns([1, 2, 1.5])

        amount = cols[0].number_input(
            "金額",
            min_value=1,
            step=100,
            value=1000,
            key=f"{base_key}_amount"
        )

        description = cols[1].text_input(
            "説明",
            key=f"{base_key}_desc"
        )

        category = cols[2].selectbox(
            "カテゴリ",
            categories,
            key=f"{base_key}_cat"
        )

        submitted = st.form_submit_button(f"{title}を追加")

        if submitted:
            insert_transaction(
                tx_date,            # 👈 月固定
                tx_type,
                category,
                int(amount),
                description or ""
            )
            st.success("追加しました")
            st.rerun()

    st.markdown("---")

    # =========================
    # 一覧データ
    # =========================
    df = month_df[month_df["type"] == tx_type].copy()

    if df.empty:
        st.info("データがありません")
        return

    df = df.set_index("id")

    display_df = df.rename(columns={
        "date": "年月",
        "amount": "金額",
        "description": "説明",
        "category": "カテゴリ",
    })

    display_df = display_df.drop(columns=["type", "signed_amount"], errors="ignore")

    # =========================
    # 年月表示に変換
    # =========================
    display_df["年月"] = pd.to_datetime(display_df["年月"]).dt.strftime("%Y年%-m月")

    # Windowsの場合はこちら
    # display_df["年月"] = pd.to_datetime(display_df["年月"]).dt.strftime("%Y年%m月")

    # None対策
    display_df["説明"] = display_df["説明"].fillna("")
    display_df["カテゴリ"] = display_df["カテゴリ"].fillna("")

    # 削除列
    display_df["削除"] = False

    display_df = display_df[["年月", "金額", "説明", "カテゴリ", "削除"]]

    # =========================
    # 表示
    # =========================
    edited = st.data_editor(
        display_df,
        key=f"{base_key}_table",
        use_container_width=True,
        hide_index=True,
        height=350,
        disabled=["年月", "金額", "説明", "カテゴリ"],
        column_config={
            "削除": st.column_config.CheckboxColumn("削除"),
            "金額": st.column_config.NumberColumn("金額", format="¥%d"),
        },
    )

    # =========================
    # 削除処理
    # =========================
    delete_ids = edited.index[edited["削除"]].tolist()

    if st.button(
        f"削除（{len(delete_ids)}件）",
        key=f"{base_key}_delete",
        disabled=not delete_ids
    ):
        for i in delete_ids:
            delete_transaction(int(i))

        st.success(f"{len(delete_ids)}件削除しました")
        st.rerun()


def insert_transaction(tx_date, tx_type, category, amount, description):
    supabase.table("transactions").insert({
        "date": tx_date.isoformat(),
        "type": tx_type,
        "category": category,
        "amount": amount,
        "description": description
    }).execute()

def render_category_delete_editor(cat_df: pd.DataFrame):
    editor_df = categories_display_frame(cat_df)
    editor_df.insert(0, "削除", False)
    edited = st.data_editor(
        editor_df,
        key="category_delete_editor",
        use_container_width=True,
        hide_index=True,
        disabled=["ID", "カテゴリ名", "種別"],
        column_config={
            "削除": st.column_config.CheckboxColumn("削除"),
            "ID": None,
        },
    )
    delete_ids = edited.loc[edited["削除"], "ID"].astype(int).tolist()
    st.caption("削除しても過去の取引に保存済みのカテゴリ文字列は残ります。")
    if st.button(f"チェックしたカテゴリを削除（{len(delete_ids)}件）", type="secondary", disabled=not delete_ids):
        for category_id in delete_ids:
            delete_category(category_id)
        st.success(f"{len(delete_ids)}件のカテゴリを削除しました。")
        st.rerun()


def render_recurring_delete_editor(recurring_df, key_suffix):

    editor_df = recurring_display_frame(recurring_df, category_list)
    
    if editor_df.empty:
        st.info("データがありません")
        return

    editor_df["削除"] = False

    editor_df["開始月"] = pd.to_datetime(editor_df["開始月"], errors="coerce")
    editor_df["終了月"] = pd.to_datetime(editor_df["終了月"], errors="coerce")

    edited = st.data_editor(
        editor_df,
        key=f"recurring_editor_{key_suffix}",
        use_container_width=True,
        column_config={
            "削除": st.column_config.CheckboxColumn("削除"),
            "開始月": st.column_config.DateColumn("開始月", format="YYYY-MM"),
            "終了月": st.column_config.DateColumn("終了月", format="YYYY-MM"),
            "金額": st.column_config.NumberColumn("金額", format="¥%d"),
        },
        disabled=["ID", "種別", "カテゴリ", "金額", "開始月"]
    )

    delete_mode = st.radio(
        "削除方法",
        ["全て削除", "今月以降を停止"],
        horizontal=True,
        key=f"delete_mode_{key_suffix}"
    )

    col1, col2 = st.columns(2)

    # 更新
    with col1:
        if st.button("変更を保存", key=f"save_{key_suffix}"):

            if not edited.equals(editor_df):

                count = 0
                for _, row in edited.iterrows():

                    end_month = None if pd.isna(row["終了月"]) else row["終了月"]

                    update_recurring(int(row["ID"]), end_month)
                    count += 1

                st.success(f"{count}件更新しました")
                st.rerun()
            else:
                st.info("変更はありません")

    # 削除
    with col2:
        delete_rows = edited[edited["削除"] == True]

        if st.button(f"削除（{len(delete_rows)}件）", key=f"delete_{key_suffix}"):

            if len(delete_rows) == 0:
                st.warning("削除対象を選択してください")
                return

            for _, row in delete_rows.iterrows():

                mode = "all" if delete_mode == "全て削除" else "future"
                delete_recurring(int(row["ID"]), mode)

            st.success(f"{len(delete_rows)}件削除しました")
            st.rerun()


def update_recurring(recurring_id, end_month):

    if pd.notna(end_month):
        end_month_str = pd.to_datetime(end_month).strftime("%Y-%m-%d")
    else:
        end_month_str = None

    supabase.table("recurring_transactions") \
        .update({"end_month": end_month_str}) \
        .eq("id", int(recurring_id)) \
        .execute()
    
def render_budget_table(title: str, summary: pd.DataFrame):
    st.markdown(f'<div class="sheet-title">{title}</div>', unsafe_allow_html=True)
    total = pd.DataFrame(
        {"予定": [summary["予定"].sum()], "実際": [summary["実際"].sum()], "差額": [summary["差額"].sum()]},
        index=["合計"],
    )
    table = pd.concat([total, summary])
    st.dataframe(
        table,
        use_container_width=True,
        column_config={
            "予定": st.column_config.NumberColumn(format="¥%d"),
            "実際": st.column_config.NumberColumn(format="¥%d"),
            "差額": st.column_config.NumberColumn(format="¥%d"),
        },
    )

def render_asset_trend(transactions_df, snapshots_df):
    if transactions_df.empty:
        st.info("データがありません")
        return

    df = transactions_df.copy()
    df["date"] = pd.to_datetime(df["date"])

    # =========================
    # 基準残高
    # =========================
    if snapshots_df.empty:
        base_balance = 0
        base_month = df["date"].min()
    else:
        snapshots_df = snapshots_df.copy()
        snapshots_df["snapshot_month"] = pd.to_datetime(snapshots_df["snapshot_month"])

        latest = snapshots_df.sort_values("snapshot_month").iloc[-1]

        base_balance = latest["balance"]
        base_month = latest["snapshot_month"]

    # 👇 月初に変換（超重要）
    base_month_start = base_month.replace(day=1)

    # =========================
    # 基準残高を1行追加
    # =========================
    base_row = pd.DataFrame({
        "date": [base_month_start],
        "signed_amount": [0],
    })

    # =========================
    # 収支
    # =========================
    df["signed_amount"] = df.apply(
        lambda x: x["amount"] if x["type"] == "income" else -x["amount"],
        axis=1
    )

    # 👇 基準より前は削除
    df = df[df["date"] >= base_month_start]

    # 👇 先頭に基準を入れる
    df = pd.concat([base_row, df], ignore_index=True)

    df = df.sort_values("date")

    # 👇 累積
    df["balance"] = base_balance + df["signed_amount"].cumsum()

    # =========================
    # 月単位
    # =========================
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()

    monthly_df = df.groupby("month")["balance"].last().reset_index()

    # =========================
    # 日本語
    # =========================
    monthly_df["month_str"] = monthly_df["month"].dt.strftime("%Y年%-m月")

    # =========================
    # 表示
    # =========================
    st.markdown('<div class="section-title">資産推移</div>', unsafe_allow_html=True)

    chart = alt.Chart(monthly_df).mark_line(point=True).encode(
        x=alt.X("month_str:N", title="月"),
        y=alt.Y("balance:Q", title="残高"),
    )

    st.altair_chart(chart, use_container_width=True)

def render_asset_trend_12m(transactions_df, snapshots_df, selected_month):
    """
    selected_month: datetime/date (その月を含めて過去12ヶ月を表示)
    """

    # -------------------------
    # 期間（過去12ヶ月）
    # -------------------------
    sel = pd.to_datetime(selected_month)
    end_month = sel.to_period("M").to_timestamp()               # 月初
    start_month = (sel.to_period("M") - 11).to_timestamp()      # 11ヶ月前の月初

    months = pd.date_range(start=start_month, end=end_month, freq="MS")  # 月初の連続

    # -------------------------
    # 取引データ整形
    # -------------------------
    if transactions_df.empty:
        df = pd.DataFrame(columns=["date", "signed_amount"])
    else:
        df = transactions_df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df["signed_amount"] = df.apply(
            lambda x: x["amount"] if x["type"] == "income" else -x["amount"],
            axis=1
        )
        # 月初に正規化
        df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()

    # -------------------------
    # 基準残高（snapshot）
    # 「各月の月初時点の残高」を決める
    # -------------------------
    if snapshots_df is not None and not snapshots_df.empty:
        ss = snapshots_df.copy()
        ss["snapshot_month"] = pd.to_datetime(ss["snapshot_month"])
        # 月初に揃える
        ss["month"] = ss["snapshot_month"].dt.to_period("M").dt.to_timestamp()
        ss = ss.sort_values("month")
    else:
        ss = pd.DataFrame(columns=["month", "balance"])

    # ヘルパー：ある月の月初残高（直近のスナップショットを使う）
    def base_balance_for_month(m):
        if ss.empty:
            return 0
        past = ss[ss["month"] <= m]
        if past.empty:
            return 0
        return int(past.iloc[-1]["balance"])

    # -------------------------
    # 月次残高を計算
    # 各月：
    #   月初残高（スナップショット） + その月の収支合計
    # -------------------------
    rows = []
    for m in months:
        # 月内の収支
        if not df.empty:
            month_sum = df.loc[df["month"] == m, "signed_amount"].sum()
        else:
            month_sum = 0

        # 月初残高
        base = base_balance_for_month(m)

        # 月末残高
        balance = int(base + month_sum)

        rows.append({
            "month": m,
            "balance": balance
        })

    monthly_df = pd.DataFrame(rows)

    # -------------------------
    # 日本語表記
    # -------------------------
    # Mac/Linux
    monthly_df["month_str"] = monthly_df["month"].dt.strftime("%Y年%-m月")
    # Windowsなら↑がダメな場合↓に変更
    # monthly_df["month_str"] = monthly_df["month"].dt.strftime("%Y年%m月")

    # -------------------------
    # グラフ
    # -------------------------
    st.markdown('<div class="section-title">資産推移（過去12ヶ月）</div>', unsafe_allow_html=True)

    chart = alt.Chart(monthly_df).mark_line(point=True).encode(
        x=alt.X("month_str:N", title="月"),
        y=alt.Y("balance:Q", title="残高"),
        tooltip=[
            alt.Tooltip("month_str:N", title="月"),
            alt.Tooltip("balance:Q", title="残高", format=",")
        ]
    )

    st.altair_chart(chart, use_container_width=True)

    # -------------------------
    # テーブル（0補完済み）
    # -------------------------
    display_df = monthly_df.rename(columns={
        "month_str": "月",
        "balance": "月末残高"
    })[["月", "月末残高"]]

    display_df["月末残高"] = display_df["月末残高"].map(lambda x: f"¥{x:,}")

    st.dataframe(display_df, use_container_width=True, hide_index=True)

def render_budget_progress(month_df, budgets_df):
    import streamlit as st
    import pandas as pd

    # =========================
    # 支出のみ集計
    # =========================
    expense_df = month_df[month_df["type"] == "expense"]

    actual = expense_df.groupby("category")["amount"].sum()

    budget = budgets_df.set_index("category")["amount"]

    df = pd.DataFrame({
        "actual": actual,
        "budget": budget
    }).fillna(0).reset_index()

    # =========================
    # UI表示
    # =========================
    st.markdown("## 予算進捗")

    for _, row in df.iterrows():
        category = row["category"]
        actual_val = row["actual"]
        budget_val = row["budget"]

        if budget_val == 0:
            progress = 0
        else:
            progress = min(actual_val / budget_val, 1.0)

        remaining = budget_val - actual_val

        # タイトル
        st.markdown(f"### {category}")

        # 金額
        st.markdown(f"¥{int(actual_val):,} / ¥{int(budget_val):,}")

        # プログレスバー
        st.progress(progress)

        # 残額（色分け）
        if remaining >= 0:
            st.markdown(f"<span style='color:green'>残り ¥{int(remaining):,}</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"<span style='color:red'>超過 ¥{int(abs(remaining)):,}</span>", unsafe_allow_html=True)

        st.markdown("---")

def render_asset_combo_chart(transactions_df, snapshots_df, selected_month):

    # =========================
    # 期間（12ヶ月）
    # =========================
    sel = pd.to_datetime(selected_month)

    start = (sel.to_period("M") - 11).to_timestamp()
    end = sel.to_period("M").to_timestamp() + pd.offsets.MonthEnd(1)

    df = transactions_df.copy()
    df["date"] = pd.to_datetime(df["date"])

    df = df[(df["date"] >= start) & (df["date"] <= end)]
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()

    # =========================
    # 集計
    # =========================
    income = df[df["type"] == "income"].groupby("month")["amount"].sum()
    expense = df[df["type"] == "expense"].groupby("month")["amount"].sum()

    months = pd.date_range(start=start, end=end, freq="MS")

    monthly = pd.DataFrame({"month": months}).set_index("month")
    monthly["income"] = income
    monthly["expense"] = expense

    monthly = monthly.fillna(0)
    monthly["expense"] = -monthly["expense"]

    # =========================
    # 基準残高
    # =========================
    if snapshots_df.empty:
        base_balance = 0
    else:
        ss = snapshots_df.copy()
        ss["snapshot_month"] = pd.to_datetime(ss["snapshot_month"])
        base_balance = int(ss.sort_values("snapshot_month").iloc[-1]["balance"])

    monthly["net"] = monthly["income"] + monthly["expense"]
    monthly["balance"] = base_balance + monthly["net"].cumsum()

    monthly = monthly.reset_index()
    monthly["month_str"] = monthly["month"].dt.strftime("%Y年%-m月")

    # =========================
    # ⭐ KPIカード（ここで表示）
    # =========================
    current = int(monthly.iloc[-1]["balance"])
    prev = int(monthly.iloc[-2]["balance"]) if len(monthly) > 1 else 0
    diff = current - prev
    valid_net = monthly.loc[monthly["net"] != 0, "net"]

    avg = int(valid_net.mean()) if not valid_net.empty else 0

    c1, c2, c3 = st.columns(3)

    c1.metric("現在資産", f"¥{current:,}")
    c2.metric("前月比", f"¥{diff:,}", delta=f"{diff:,}",
              delta_color="normal" if diff >= 0 else "inverse")
    c3.metric("平均増減", f"¥{avg:,}")

    st.markdown("---")

    # =========================
    # グラフ
    # =========================
    order = monthly["month_str"].tolist()

    tooltip = [
        alt.Tooltip("month_str:N", title="月"),
        alt.Tooltip("income:Q", title="収入", format=","),
        alt.Tooltip("expense:Q", title="支出", format=","),
        alt.Tooltip("net:Q", title="増減", format=","),
        alt.Tooltip("balance:Q", title="資産", format=","),
    ]

    base = alt.Chart(monthly).encode(
        x=alt.X("month_str:N", sort=order)
    )

    income_bar = base.mark_bar(color="#4dabf7").encode(
        y="income:Q", tooltip=tooltip
    )

    expense_bar = base.mark_bar(color="#ffa94d").encode(
        y="expense:Q", tooltip=tooltip
    )

    line = base.mark_line(
        point=True,
        strokeWidth=3,
        color="#6366f1"
    ).encode(
        y="balance:Q",
        tooltip=tooltip
    )

    zero_line = alt.Chart(pd.DataFrame({"y":[0]})).mark_rule(
        color="gray", strokeDash=[4,4]
    ).encode(y="y:Q")

    st.altair_chart(income_bar + expense_bar + line + zero_line, use_container_width=True)
    # =========================
    # 月別一覧テーブル
    # =========================

    st.markdown("### 月別一覧")

    display_df = monthly.copy()

    # 表示用フォーマット
    display_df = display_df[[
        "month_str", "income", "expense", "net", "balance"
    ]].rename(columns={
        "month_str": "年月",
        "income": "収入",
        "expense": "支出",
        "net": "増減",
        "balance": "資産"
    })

    # 金額フォーマット
    for col in ["収入", "支出", "増減", "資産"]:
        display_df[col] = display_df[col].map(lambda x: f"¥{int(x):,}")

    # 並び順逆
    display_df = display_df.iloc[::-1]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=35 * len(display_df) + 40  # 👈 自動調整
    )
def check_table_exists(supabase, table_name: str) -> bool:
    """
    テーブルが存在するかをSupabaseに問い合わせて確認
    """
    try:
        supabase.table(table_name).select("*").limit(1).execute()
        return True
    except Exception as e:
        print(f"[Table Check Error] {table_name}:", e)
        return False
    
def safe_category_display(category, category_list):
    if category in category_list:
        return category
    else:
        return "未分類"

def render_setup_notice(balance_ready: bool, recurring_ready: bool):
    missing = []

    if not balance_ready:
        missing.append("balance_snapshots")

    if not recurring_ready:
        missing.append("recurring_transactions")

    # どちらもOKなら何も出さない
    if not missing:
        return

    st.warning(
        f"追加機能に必要なテーブルが未作成です: {', '.join(missing)}"
    )

    st.caption(
        "SupabaseのSQL Editorで supabase_schema.sql を実行すると利用できます。"
    )
st.title("資産管理アプリ")

try:
    supabase = get_supabase_client()
    cat_df = load_table("categories")
except Exception as exc:
    st.error("Supabaseに接続できませんでした。secrets.toml の SUPABASE_URL / SUPABASE_KEY を確認してください。")
    st.exception(exc)
    st.stop()

if cat_df.empty:
    st.error("categoriesテーブルにデータがありません。先にカテゴリを登録してください。")
    st.stop()

required_category_columns = {"id", "name", "type"}
if not required_category_columns.issubset(cat_df.columns):
    st.error("categoriesテーブルには id, name, type カラムが必要です。")
    st.stop()

transactions_df = load_table_or_empty("transactions")

# 👇 これ追加
if transactions_df.empty:
    transactions_df = pd.DataFrame(columns=[
        "id", "date", "type", "amount", "category", "description"
    ])
transactions_df["date"] = pd.to_datetime(transactions_df["date"])
transactions_df["signed_amount"] = transactions_df.apply(
    lambda row: row["amount"] if row["type"] == "income" else -row["amount"],
    axis=1
)
budgets_df = load_table_or_empty("budgets")

snapshots_raw, balance_ready = load_optional_table("balance_snapshots")
recurring_raw, recurring_ready = load_optional_table("recurring_transactions")
snapshots_df = normalize_snapshots(snapshots_raw)
recurring_df = normalize_recurring(recurring_raw)

cat_df = cat_df.sort_values("id")
income_categories = cat_df[cat_df["type"] == "income"]["name"].tolist()
expense_categories = cat_df[cat_df["type"] == "expense"]["name"].tolist()

with st.sidebar:
    st.markdown("## 資産管理")
    page = st.radio(
        "メニュー",
        ["収支入力", "月間収支", "資産推移", "設定"],
        label_visibility="collapsed",
    )
    st.divider()
    selected_month = month_selector("対象月", "main_month")
start, end = month_range(selected_month)

month_df = transactions_df[(transactions_df["date"] >= start) & (transactions_df["date"] <= end)].copy()
recurring_df = load_table_or_empty("recurring_transactions")
month_df = apply_recurring(month_df, recurring_df, selected_month)
income = month_df.loc[month_df["type"] == "income", "amount"].sum()
expense = month_df.loc[month_df["type"] == "expense", "amount"].sum()
month_opening_balance, month_end_balance = month_balances(transactions_df, snapshots_df, selected_month)
monthly_saving = income - expense
saving_rate = (monthly_saving / month_opening_balance * 100) if month_opening_balance else 0

# =========================
# テーブル存在チェック
# =========================
balance_ready = check_table_exists(supabase, "balance_snapshots")
recurring_ready = check_table_exists(supabase, "recurring_transactions")

# =========================
# 通知表示
# =========================
render_setup_notice(balance_ready, recurring_ready)

render_setup_notice(balance_ready, recurring_ready)

if page == "収支入力":

    expense_df = month_df[month_df["type"] == "expense"]
    income_df = month_df[month_df["type"] == "income"]

    st.markdown(f'<div class="sheet-caption">{month_label(selected_month)} の支出と収入を左右に並べて登録します。</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        render_transaction_block(month_df, "expense", "支出", expense_categories, selected_month)

    with col2:
        render_transaction_block(month_df, "income", "収入", income_categories, selected_month)

elif page == "月間収支":

    header_left, header_right = st.columns([2.2, 1])
    with header_left:
        st.markdown('<div class="sheet-title">月間収支</div>', unsafe_allow_html=True)
    with header_right:
        st.metric("月初残高", yen(month_opening_balance))
        st.metric("月末残高", yen(month_end_balance))

    # 👇 ここに追加！！！
    c1, c2, c3, c4 = st.columns(4)

    c1.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-value">{yen(income)}</div>
      <div class="kpi-label">収入</div>
    </div>
    """, unsafe_allow_html=True)

    c2.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-value">{yen(expense)}</div>
      <div class="kpi-label">支出</div>
    </div>
    """, unsafe_allow_html=True)

    c3.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-value">{yen(monthly_saving)}</div>
      <div class="kpi-label">貯蓄</div>
    </div>
    """, unsafe_allow_html=True)

    c4.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-value">{saving_rate:.1f}%</div>
      <div class="kpi-label">貯蓄率</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    top_left, top_right = st.columns([1, 1])
    with top_left:
        st.bar_chart(pd.DataFrame({"残高": [month_opening_balance, month_end_balance]}, index=["月初残高", "月末残高"]))
    with top_right:
        st.markdown(
            f"""
            <div class="budget-card">
                <div class="big">{saving_rate:.0f}%</div>
                <div class="label">月初残高からの増減率</div>
                <hr>
                <div class="big">{yen(monthly_saving)}</div>
                <div class="label">今月の貯蓄額</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    render_budget_progress(month_df, budgets_df)

elif page == "資産推移":
    st.subheader("資産推移")
    all_transactions_df = load_table("transactions")
    render_asset_combo_chart(all_transactions_df, snapshots_df, selected_month)

elif page == "設定":
    st.markdown('<div class="sheet-title">設定</div>', unsafe_allow_html=True)
    setting_page = st.segmented_control(
        "設定メニュー",
        ["基準残高", "定期収支", "カテゴリ", "予算"],
        default="基準残高",
        key="settings_menu",
    )
    if setting_page == "基準残高":
        # =====================
        # 基準残高（フォーム化）
        # =====================

        st.subheader("基準残高")

        # 現在の基準表示
        if not snapshots_df.empty:
            latest = snapshots_df.sort_values("snapshot_month").iloc[-1]
            st.info(
                f"現在の基準：{latest['snapshot_month'].strftime('%Y-%m')} / ¥{int(latest['balance']):,}"
            )
        
        with st.form("snapshot_form"):
        
            snapshot_month = st.date_input("基準月")
            snapshot_balance = st.number_input("残高", min_value=0, step=10000)

            confirm = st.checkbox("内容を理解して更新する")

            submitted = st.form_submit_button("更新")

            if submitted:
                if not confirm:
                    st.error("チェックを入れてください")
                else:
                    save_balance_snapshot(snapshot_month, int(snapshot_balance))
                    st.success("更新しました")
                    st.rerun()

    # =========================
    # 定期収支ページ
    # =========================
    elif setting_page == "定期収支":

        st.subheader("定期収入・定期支出")

        # =========================
        # データ取得
        # =========================
        recurring_df = load_table_or_empty("recurring_transactions")

        if "is_deleted" in recurring_df.columns:
            recurring_df = recurring_df[recurring_df["is_deleted"] != True]
        expense_df = recurring_df[recurring_df["type"] == "expense"]
        income_df = recurring_df[recurring_df["type"] == "income"]

        cat_df = load_table_or_empty("categories")

        expense_categories = cat_df[cat_df["type"] == "expense"]["name"].tolist()
        income_categories = cat_df[cat_df["type"] == "income"]["name"].tolist()

        if cat_df.empty:
            st.warning("カテゴリを先に登録してください")
            st.stop()

        # =========================
        # ① 入力フォーム（カード）
        # =========================
        st.markdown('<div class="card">', unsafe_allow_html=True)

        # =========================
        # 種別（form外）
        # =========================
        recurring_type_label = st.segmented_control(
            "種別",
            ["支出", "収入"],
            default="支出",
            key="recurring_type"
        )

        recurring_type = "expense" if recurring_type_label == "支出" else "income"


        # =========================
        # 👇 form外
        # =========================
        use_end = st.checkbox("終了月を設定")

        # =========================
        # form（全部中に入れる）
        # =========================
        with st.form("recurring_form", clear_on_submit=True):
        
            cols = st.columns([1, 1, 1, 1, 1.5])

            # カテゴリ
            if recurring_type == "expense":
                category_list = expense_categories
            else:
                category_list = income_categories

            # 金額
            recurring_amount = cols[0].number_input(
                "金額",
                min_value=0,
                step=1000
            )

            # カテゴリ
            recurring_category = cols[1].selectbox(
                "カテゴリ",
                category_list,
                key=f"recurring_category_{recurring_type}"
            )

            # 年月
            import datetime
            today = datetime.date.today()

            years = list(range(today.year - 5, today.year + 5))
            months = list(range(1, 13))

            year = cols[2].selectbox("年", years, index=years.index(today.year))
            month = cols[3].selectbox("月", months, index=today.month - 1)

            start_month = pd.Timestamp(year=year, month=month, day=1)

            # =========================
            # 終了月（form内に入れる ←重要）
            # =========================
            end_month = None

            if use_end:
            
                end_years = [y for y in years if y >= year]

                end_year = cols[2].selectbox("終了年", end_years, key="end_year")

                if end_year == year:
                    end_months = [m for m in months if m >= month]
                else:
                    end_months = months

                end_month_val = cols[3].selectbox("終了月", end_months, key="end_month")

                end_month = pd.Timestamp(
                    year=end_year,
                    month=end_month_val,
                    day=1
                )

            # 説明
            recurring_desc = st.text_input("説明")

            # 👇 submitは必ずform内
            submitted = st.form_submit_button("定期収支を追加")

            if submitted:
                save_recurring(
                    recurring_type,
                    int(recurring_amount),
                    recurring_category,
                    recurring_desc or "",
                    start_month,
                    end_month
                )

                st.success("定期収支を追加しました")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # =========================
        # ② 一覧（ここに入れる ← 今回のやつ）
        # =========================
        st.markdown('<div class="card">', unsafe_allow_html=True)

        st.markdown('<div class="section-title">定期収支一覧</div>', unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["🔴 支出", "🟢 収入"])

        with tab1:
            st.markdown('<div class="expense-title">支出一覧</div>', unsafe_allow_html=True)
            render_recurring_delete_editor(expense_df, "expense")

        with tab2:
            st.markdown('<div class="income-title">収入一覧</div>', unsafe_allow_html=True)
            render_recurring_delete_editor(income_df, "income")

        st.markdown('</div>', unsafe_allow_html=True)

    elif setting_page == "カテゴリ":
        st.subheader("カテゴリの追加")
        with st.form("category_form", clear_on_submit=True):
            cols = st.columns([1, 2])
            new_type_label = cols[0].segmented_control(
                "種別",
                ["支出", "収入"],
                default="支出",
                key="category_new_type",
            )
            new_type = type_value(new_type_label)
            new_name = cols[1].text_input("カテゴリ名", key="category_new_name")
            if st.form_submit_button("カテゴリを追加", type="primary"):
                if not new_name.strip():
                    st.error("カテゴリ名を入力してください。")
                elif new_name.strip() in cat_df["name"].tolist():
                    st.error("同じカテゴリ名が既にあります。")
                else:
                    save_category(new_name, new_type)
                    st.success("カテゴリを追加しました。")
                    st.rerun()

        st.subheader("カテゴリ一覧・削除")
        render_category_delete_editor(cat_df)
        
    elif setting_page == "予算":

        st.subheader("予算設定（全月共通）")

        categories = cat_df["name"].tolist()
        
        with st.form("budget_form"):

            selected_category = st.selectbox("カテゴリ", categories)

            existing = budgets_df[budgets_df["category"] == selected_category]

            default_amount = 0
            if not existing.empty:
                default_amount = int(existing["amount"].iloc[0])

            amount = st.number_input(
                "予算",
                value=default_amount,
                step=1000
            )

            submitted = st.form_submit_button("保存")

            if submitted:
                save_budget(selected_category, int(amount))
                st.success("保存しました")
                st.rerun()

        # =========================
        # 予算一覧（全カテゴリ表示）
        # =========================

        st.divider()
        st.subheader("現在の予算一覧")

        # カテゴリベースで作る（ここがポイント）
        all_categories = cat_df[["name", "type"]].copy()

        # 予算と結合（LEFT JOIN）
        merged = all_categories.merge(
            budgets_df,
            left_on="name",
            right_on="category",
            how="left"
        )

        # 未設定は0円
        merged["amount"] = merged["amount"].fillna(0).astype(int)

        # 分割
        expense_df = merged[merged["type"] == "expense"]
        income_df = merged[merged["type"] == "income"]

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 💸 支出")
            st.dataframe(
                expense_df[["name", "amount"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "name": "カテゴリ",
                    "amount": st.column_config.NumberColumn("予算", format="¥%d"),
                }
            )
            st.caption(f"合計: ¥{expense_df['amount'].sum():,}")

        with col2:
            st.markdown("### 💰 収入")
            st.dataframe(
                income_df[["name", "amount"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "name": "カテゴリ",
                    "amount": st.column_config.NumberColumn("予算", format="¥%d"),
                }
            )
            st.caption(f"合計: ¥{income_df['amount'].sum():,}")