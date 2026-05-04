from __future__ import annotations

import os
from datetime import date
from typing import Any

import altair as alt
import httpx
import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError
from supabase import create_client


st.set_page_config(page_title="資産管理アプリ", page_icon="💰", layout="wide")


ACCENT = "#f45b22"
ACCENT_DARK = "#d9480f"
INK = "#172033"
NAVY = "#30475e"
MUTED = "#687386"
SURFACE = "#ffffff"
SOFT = "#f4f6f8"
LINE = "#dbe1ea"
TYPE_LABELS = {"expense": "支出", "income": "収入"}
TYPE_VALUES = {"支出": "expense", "収入": "income"}


def inject_styles() -> None:
    """アプリ全体の見た目を整えるCSSを注入します。"""
    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
                radial-gradient(circle at top left, rgba(244, 91, 34, .10), transparent 24rem),
                radial-gradient(circle at top right, rgba(77, 171, 247, .10), transparent 22rem),
                linear-gradient(135deg, #f8fafc 0%, #eef3f8 52%, #fffaf5 100%);
            color: {INK};
        }}
        h1, h2, h3, label {{ letter-spacing: 0; }}
        section[data-testid="stSidebar"] {{
            display: none;
        }}
        .block-container {{
            max-width: 1180px;
            padding-top: 1rem;
            padding-bottom: 3rem;
        }}
        .app-hero {{
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 1rem;
            padding: 1.55rem 1.65rem;
            margin-bottom: .8rem;
            color: white;
            background:
                linear-gradient(135deg, rgba(15, 23, 42, .96), rgba(48, 71, 94, .80)),
                radial-gradient(circle at 10% 15%, rgba(244, 91, 34, .50), transparent 24rem),
                radial-gradient(circle at 88% 30%, rgba(77, 171, 247, .30), transparent 20rem);
            border: 1px solid rgba(255, 255, 255, .22);
            border-radius: 8px;
            box-shadow: 0 18px 50px rgba(23, 32, 51, .18);
        }}
        .app-hero h1 {{
            margin: 0;
            font-size: 2.15rem;
            line-height: 1.1;
            color: white;
        }}
        .app-hero p {{
            margin: .35rem 0 0;
            color: rgba(255, 255, 255, .78);
        }}
        .hero-month {{
            text-align: right;
            color: rgba(255, 255, 255, .88);
            font-weight: 700;
            white-space: nowrap;
        }}
        .control-strip {{
            padding: .7rem .8rem .6rem;
            margin-bottom: 1rem;
            border: 1px solid rgba(219, 225, 234, .92);
            border-radius: 8px;
            background: rgba(255, 255, 255, .72);
            box-shadow: 0 10px 30px rgba(23, 32, 51, .07);
            backdrop-filter: blur(12px);
        }}
        .control-strip [data-testid="stHorizontalBlock"] {{
            align-items: end;
        }}
        div[data-testid="stHorizontalBlock"]:has(.nav-caption) {{
            align-items: end;
            padding: .72rem .82rem .65rem;
            margin: 0 0 1rem;
            border: 1px solid rgba(219, 225, 234, .92);
            border-radius: 8px;
            background: rgba(255, 255, 255, .74);
            box-shadow: 0 10px 30px rgba(23, 32, 51, .07);
            backdrop-filter: blur(12px);
        }}
        .nav-caption {{
            color: {MUTED};
            font-size: .72rem;
            font-weight: 800;
            margin: 0 0 .15rem;
        }}
        div[data-testid="stSegmentedControl"] {{
            gap: .25rem;
        }}
        div[data-testid="stSegmentedControl"] button {{
            min-height: 2.35rem;
            border-radius: 8px;
            border: 1px solid rgba(219, 225, 234, .95);
            background: rgba(255, 255, 255, .86);
            color: {INK};
            font-weight: 800;
        }}
        div[data-testid="stSegmentedControl"] button[aria-pressed="true"] {{
            border-color: rgba(23, 32, 51, .95);
            background: linear-gradient(135deg, #172033, #30475e);
            color: white;
            box-shadow: 0 8px 18px rgba(23, 32, 51, .18);
        }}
        div[data-testid="stSegmentedControl"] button[aria-selected="true"],
        div[data-testid="stSegmentedControl"] button[aria-checked="true"] {{
            border-color: rgba(23, 32, 51, .95);
            background: linear-gradient(135deg, #172033, #30475e);
            color: white;
            box-shadow: 0 8px 18px rgba(23, 32, 51, .18);
        }}
        div[data-testid="stSelectbox"] label,
        div[data-testid="stNumberInput"] label,
        div[data-testid="stDateInput"] label,
        div[data-testid="stTextInput"] label {{
            color: {MUTED};
            font-weight: 800;
            font-size: .82rem;
        }}
        div[data-baseweb="select"] > div,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextInput"] input,
        div[data-testid="stDateInput"] input {{
            border-radius: 8px;
            border-color: rgba(219, 225, 234, .95);
            background: rgba(255, 255, 255, .9);
        }}
        .section-title {{
            color: {INK};
            font-size: 1.35rem;
            font-weight: 800;
            margin: .5rem 0 .65rem;
        }}
        .section-caption {{
            color: {MUTED};
            font-size: .95rem;
            margin: -.25rem 0 1rem;
        }}
        .metric-card {{
            min-height: 118px;
            padding: 1rem 1.1rem;
            border: 1px solid rgba(219, 225, 234, .95);
            border-radius: 8px;
            background:
                linear-gradient(180deg, rgba(255,255,255,.96), rgba(255,255,255,.84));
            box-shadow: 0 12px 30px rgba(23, 32, 51, .08);
            position: relative;
            overflow: hidden;
        }}
        .metric-card::before {{
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 4px;
            background: linear-gradient(180deg, {ACCENT}, #4dabf7);
        }}
        .metric-label {{
            color: {MUTED};
            font-size: .84rem;
            font-weight: 700;
            margin-bottom: .35rem;
        }}
        .metric-value {{
            color: {NAVY};
            font-size: 1.7rem;
            font-weight: 850;
            line-height: 1.12;
            overflow-wrap: anywhere;
        }}
        .metric-sub {{
            color: {MUTED};
            font-size: .8rem;
            margin-top: .4rem;
        }}
        .panel {{
            padding: 1.15rem;
            border: 1px solid rgba(219, 225, 234, .95);
            border-radius: 8px;
            background: rgba(255, 255, 255, .86);
            box-shadow: 0 10px 26px rgba(23, 32, 51, .07);
        }}
        .status-pill {{
            display: inline-flex;
            align-items: center;
            gap: .4rem;
            padding: .25rem .55rem;
            border-radius: 999px;
            background: rgba(244, 91, 34, .12);
            color: {ACCENT_DARK};
            font-size: .82rem;
            font-weight: 800;
        }}
        .insight-card {{
            min-height: 132px;
            padding: 1rem;
            border: 1px solid rgba(219, 225, 234, .95);
            border-radius: 8px;
            background: rgba(255, 255, 255, .88);
            box-shadow: 0 10px 28px rgba(23, 32, 51, .07);
        }}
        .insight-title {{
            color: {MUTED};
            font-size: .78rem;
            font-weight: 850;
            margin-bottom: .4rem;
        }}
        .insight-value {{
            color: {INK};
            font-size: 1.2rem;
            font-weight: 900;
            line-height: 1.25;
        }}
        .insight-note {{
            color: {MUTED};
            font-size: .82rem;
            margin-top: .45rem;
        }}
        .action-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: .85rem;
            margin: .75rem 0 1rem;
        }}
        .action-card {{
            min-height: 116px;
            padding: 1rem;
            border: 1px solid rgba(219, 225, 234, .95);
            border-radius: 8px;
            background:
                linear-gradient(180deg, rgba(255,255,255,.96), rgba(255,255,255,.86));
            box-shadow: 0 10px 26px rgba(23, 32, 51, .07);
        }}
        .action-card strong {{
            display: block;
            color: {INK};
            font-size: 1.18rem;
            margin-top: .35rem;
        }}
        .action-card span {{
            color: {MUTED};
            font-size: .82rem;
            font-weight: 800;
        }}
        .danger-note {{
            padding: .85rem .95rem;
            border: 1px solid rgba(244, 91, 34, .28);
            border-radius: 8px;
            background: rgba(244, 91, 34, .08);
            color: {ACCENT_DARK};
            font-weight: 750;
            line-height: 1.55;
        }}
        .mobile-list {{
            display: none;
        }}
        .mobile-card {{
            border: 1px solid rgba(219, 225, 234, .95);
            border-radius: 8px;
            padding: .85rem .95rem;
            margin: .55rem 0;
            background: rgba(255, 255, 255, .92);
            box-shadow: 0 8px 22px rgba(23, 32, 51, .07);
        }}
        .mobile-card-top {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: .75rem;
            margin-bottom: .55rem;
        }}
        .mobile-card-title {{
            color: {INK};
            font-size: .98rem;
            font-weight: 850;
            line-height: 1.25;
        }}
        .mobile-card-amount {{
            color: {NAVY};
            font-size: 1.08rem;
            font-weight: 900;
            white-space: nowrap;
        }}
        .mobile-card-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: .35rem;
        }}
        .mobile-chip {{
            display: inline-flex;
            align-items: center;
            min-height: 1.65rem;
            padding: .15rem .45rem;
            border-radius: 999px;
            background: {SOFT};
            color: {MUTED};
            font-size: .78rem;
            font-weight: 750;
        }}
        .desktop-table {{
            display: block;
        }}
        .stButton > button, .stFormSubmitButton > button {{
            border: 0;
            border-radius: 8px;
            color: white;
            background: linear-gradient(135deg, {ACCENT}, #ff855c);
            box-shadow: 0 8px 18px rgba(244, 91, 34, .22);
            font-weight: 750;
        }}
        .stButton > button:hover, .stFormSubmitButton > button:hover {{
            border: 0;
            color: white;
            background: linear-gradient(135deg, {ACCENT_DARK}, {ACCENT});
        }}
        div[data-testid="stMetricValue"] {{ color: {NAVY}; }}
        div[data-testid="stDataFrame"] {{
            border-radius: 8px;
            overflow: hidden;
        }}
        div[data-testid="stDataFrame"] [role="grid"] {{
            border: 1px solid rgba(219, 225, 234, .95);
        }}
        @media (max-width: 720px) {{
            .block-container {{
                padding: .85rem .85rem 2rem;
            }}
            .app-hero {{
                display: block;
                padding: 1rem;
                margin-bottom: .7rem;
            }}
            .app-hero h1 {{
                font-size: 1.65rem;
            }}
            .app-hero p {{
                font-size: .86rem;
            }}
            .hero-month {{ text-align: left; margin-top: .75rem; }}
            .control-strip {{
                position: static;
                padding: .65rem;
                margin-bottom: .85rem;
            }}
            div[data-testid="stSegmentedControl"] {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
            div[data-testid="stSegmentedControl"] button {{
                width: 100%;
                padding: .35rem .45rem;
                font-size: .86rem;
            }}
            div[data-testid="stHorizontalBlock"] {{
                gap: .6rem;
            }}
            .metric-card {{
                min-height: 96px;
                padding: .8rem .85rem;
                margin-bottom: .6rem;
            }}
            .metric-value {{ font-size: 1.35rem; }}
            .desktop-table {{
                display: none;
            }}
            .mobile-list {{
                display: block;
            }}
            .action-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def get_supabase_client():
    """Streamlit secretsからSupabaseクライアントを作成してキャッシュします。"""
    return create_client(required_secret("SUPABASE_URL"), required_secret("SUPABASE_KEY"))


def optional_secret(name: str) -> str | None:
    """Streamlit secretsまたは環境変数から任意の設定値を取得します。"""
    try:
        return st.secrets.get(name) or os.getenv(name)
    except Exception:
        return os.getenv(name)


def required_secret(name: str) -> str:
    """必須設定値を取得し、見つからない場合は分かりやすいエラーにします。"""
    value = optional_secret(name)
    if not value:
        raise RuntimeError(f"{name} が設定されていません。")
    return value


def require_login() -> None:
    """アプリ共通の簡易パスワード認証を実行します。"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return

    st.title("ログイン")
    app_password = optional_secret("APP_PASSWORD")
    if not app_password:
        st.error("APP_PASSWORD が設定されていません。.streamlit/secrets.toml または環境変数を確認してください。")
        st.stop()

    password = st.text_input("パスワードを入力してください", type="password")
    if st.button("ログイン"):
        if password == app_password:
            st.session_state.authenticated = True
            st.rerun()
        st.error("パスワードが違います")
    st.stop()


def yen(value: float | int) -> str:
    """数値を日本円表記へ変換します。"""
    return f"¥{int(value):,}"


def first_day(value: date | pd.Timestamp) -> date:
    """指定日の月初日を返します。"""
    return pd.to_datetime(value).date().replace(day=1)


def month_range(value: date | pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    """指定月の開始日と終了日をTimestampで返します。"""
    start = pd.Timestamp(first_day(value))
    return start, start + pd.offsets.MonthEnd(0)


def month_label(value: date | pd.Timestamp) -> str:
    """年月を日本語の表示ラベルに変換します。"""
    ts = pd.Timestamp(value)
    return f"{ts.year}年{ts.month}月"


def format_month(ts: pd.Timestamp) -> str:
    """Timestampを年/月の短い日本語ラベルへ変換します。"""
    return f"{ts.year}年{ts.month}月"


def format_jp_date(value: Any) -> str:
    """日付を年月日の日本語表記へ変換します。"""
    ts = pd.Timestamp(value)
    return f"{ts.year}年{ts.month}月{ts.day}日"


def type_label(value: str) -> str:
    """DB上の収支タイプを画面表示ラベルへ変換します。"""
    return TYPE_LABELS.get(value, value)


def type_value(label: str) -> str:
    """画面表示ラベルをDB上の収支タイプへ変換します。"""
    return TYPE_VALUES.get(label, label)


def month_selector(label: str, key: str, default: date | None = None) -> date:
    """年と月のセレクトボックスで対象月を選択します。"""
    default = first_day(default or date.today())
    years = list(range(default.year - 5, default.year + 6))
    st.caption(label)
    cols = st.columns(2)
    year = cols[0].selectbox("年", years, index=years.index(default.year), key=f"{key}_year")
    month = cols[1].selectbox("月", list(range(1, 13)), index=default.month - 1, key=f"{key}_month")
    return date(int(year), int(month), 1)


def selected_month_from_state(key: str, default: date | None = None) -> date:
    """月セレクタの現在値をsession_stateから取得します。"""
    default = first_day(default or date.today())
    year = int(st.session_state.get(f"{key}_year", default.year))
    month = int(st.session_state.get(f"{key}_month", default.month))
    return date(year, month, 1)


def ensure_columns(df: pd.DataFrame, defaults: dict[str, Any]) -> pd.DataFrame:
    """不足している列をデフォルト値で補完します。"""
    result = df.copy()
    for column, default in defaults.items():
        if column not in result.columns:
            result[column] = default
    return result


def load_table(table_name: str, limit: int = 10000) -> pd.DataFrame:
    """Supabaseからテーブルを読み込みDataFrameに変換します。"""
    query = supabase.table(table_name).select("*").limit(limit)
    if table_name == "transactions":
        query = query.order("date", desc=False)
    response = query.execute()
    return pd.DataFrame(response.data or [])


def load_optional_table(table_name: str) -> tuple[pd.DataFrame, bool]:
    """存在しない可能性のあるテーブルを安全に読み込みます。"""
    try:
        return load_table(table_name), True
    except (APIError, httpx.TimeoutException, Exception):
        return pd.DataFrame(), False


def normalize_categories(data: pd.DataFrame) -> pd.DataFrame:
    """カテゴリデータの欠損列と削除フラグを整えます。"""
    columns = {"id": pd.NA, "name": "", "type": "expense", "is_deleted": False}
    data = ensure_columns(data, columns)
    data["is_deleted"] = data["is_deleted"].fillna(False).astype(bool)
    return data.dropna(subset=["id", "name"]).sort_values("id")


def normalize_transactions(data: pd.DataFrame) -> pd.DataFrame:
    """取引データの日付・金額・符号付き金額を整えます。"""
    data = ensure_columns(
        data,
        {"id": pd.NA, "date": pd.NaT, "type": "expense", "amount": 0, "category": "", "description": ""},
    )
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["amount"] = pd.to_numeric(data["amount"], errors="coerce").fillna(0).astype(int)
    data["description"] = data["description"].fillna("")
    data["category"] = data["category"].fillna("")
    data["signed_amount"] = data.apply(lambda row: row["amount"] if row["type"] == "income" else -row["amount"], axis=1)
    return data.dropna(subset=["date"])


def normalize_budgets(data: pd.DataFrame) -> pd.DataFrame:
    """予算データの金額を数値化します。"""
    data = ensure_columns(data, {"id": pd.NA, "category": "", "amount": 0})
    data["amount"] = pd.to_numeric(data["amount"], errors="coerce").fillna(0).astype(int)
    return data


def normalize_snapshots(data: pd.DataFrame) -> pd.DataFrame:
    """基準残高データの日付と金額を整えます。"""
    data = ensure_columns(data, {"id": pd.NA, "snapshot_month": pd.NaT, "balance": 0})
    data["snapshot_month"] = pd.to_datetime(data["snapshot_month"], errors="coerce")
    data["balance"] = pd.to_numeric(data["balance"], errors="coerce").fillna(0).astype(int)
    return data.dropna(subset=["snapshot_month"]).sort_values("snapshot_month")


def normalize_recurring(data: pd.DataFrame) -> pd.DataFrame:
    """定期収支データの期間・金額・削除フラグを整えます。"""
    data = ensure_columns(
        data,
        {
            "id": pd.NA,
            "day": 1,
            "type": "expense",
            "amount": 0,
            "category": "",
            "description": "",
            "start_month": pd.NaT,
            "end_month": pd.NaT,
            "active": True,
            "is_deleted": False,
        },
    )
    data["day"] = pd.to_numeric(data["day"], errors="coerce").fillna(1).astype(int).clip(1, 28)
    data["amount"] = pd.to_numeric(data["amount"], errors="coerce").fillna(0).astype(int)
    data["start_month"] = pd.to_datetime(data["start_month"], errors="coerce")
    data["end_month"] = pd.to_datetime(data["end_month"], errors="coerce")
    data["description"] = data["description"].fillna("")
    data["active"] = data["active"].fillna(True).astype(bool)
    data["is_deleted"] = data["is_deleted"].fillna(False).astype(bool)
    return data.dropna(subset=["start_month"])


def save_transaction(tx_date: date | pd.Timestamp, tx_type: str, category: str, amount: int, description: str) -> None:
    """取引を1件追加します。"""
    supabase.table("transactions").insert(
        {
            "date": pd.Timestamp(tx_date).date().isoformat(),
            "type": tx_type,
            "amount": int(amount),
            "category": category,
            "description": (description or "").strip(),
        }
    ).execute()


def update_transaction(transaction_id: int, amount: int, category: str, description: str) -> None:
    """取引の金額・カテゴリ・説明を更新します。"""
    supabase.table("transactions").update(
        {"amount": int(amount), "category": category, "description": description or ""}
    ).eq("id", int(transaction_id)).execute()


def delete_transaction(transaction_id: int) -> None:
    """取引を1件削除します。"""
    supabase.table("transactions").delete().eq("id", int(transaction_id)).execute()


def save_category(name: str, category_type: str) -> None:
    """カテゴリを1件追加します。"""
    payload = {"name": name.strip(), "type": category_type, "is_deleted": False}
    try:
        supabase.table("categories").insert(payload).execute()
    except Exception:
        payload.pop("is_deleted")
        supabase.table("categories").insert(payload).execute()


def delete_category(category_id: int) -> None:
    """カテゴリを論理削除し、列がない場合は物理削除にフォールバックします。"""
    try:
        supabase.table("categories").update({"is_deleted": True}).eq("id", int(category_id)).execute()
    except Exception:
        supabase.table("categories").delete().eq("id", int(category_id)).execute()


def rename_category(category_id: int, old_name: str, new_name: str) -> None:
    """カテゴリ名を変更し、既存データ内のカテゴリ文字列も更新します。"""
    supabase.table("categories").update({"name": new_name.strip()}).eq("id", int(category_id)).execute()
    reassign_category_references(old_name, new_name.strip())


def reassign_category_references(old_name: str, new_name: str) -> None:
    """取引・予算・定期収支に保存済みのカテゴリ名を付け替えます。"""
    for table_name in ["transactions", "recurring_transactions"]:
        try:
            supabase.table(table_name).update({"category": new_name}).eq("category", old_name).execute()
        except Exception:
            pass

    try:
        supabase.table("budgets").update({"category": new_name}).eq("category", old_name).execute()
    except Exception:
        try:
            supabase.table("budgets").delete().eq("category", old_name).execute()
        except Exception:
            pass


def delete_category_with_reassignment(category_id: int, old_name: str, new_name: str) -> None:
    """カテゴリに紐づくデータを移行してからカテゴリを削除します。"""
    reassign_category_references(old_name.strip(), new_name.strip())
    delete_category(category_id)


def category_name_by_id(cat_df: pd.DataFrame, category_id: int) -> str:
    """カテゴリIDからカテゴリ名を取得します。"""
    matched = cat_df.loc[cat_df["id"].astype(int) == int(category_id), "name"]
    return str(matched.iloc[0]) if not matched.empty else ""


def save_budget(category: str, amount: int) -> None:
    """カテゴリ別の月次予算を保存します。"""
    supabase.table("budgets").upsert({"category": category, "amount": int(amount)}, on_conflict="category").execute()


def save_balance_snapshot(snapshot_month: date, balance: int) -> None:
    """基準残高を単一レコードとして保存し直します。"""
    supabase.table("balance_snapshots").delete().neq("id", 0).execute()
    supabase.table("balance_snapshots").insert(
        {"snapshot_month": first_day(snapshot_month).isoformat(), "balance": int(balance)}
    ).execute()


def save_recurring(tx_type: str, day: int, amount: int, category: str, desc: str, start_month: pd.Timestamp, end_month) -> None:
    """定期収支を1件追加します。"""
    payload = {
        "day": int(day),
        "type": tx_type,
        "amount": int(amount),
        "category": category,
        "description": desc or "",
        "start_month": pd.Timestamp(start_month).strftime("%Y-%m-%d"),
        "end_month": pd.Timestamp(end_month).strftime("%Y-%m-%d") if end_month is not None else None,
        "active": True,
        "is_deleted": False,
    }
    try:
        supabase.table("recurring_transactions").insert(payload).execute()
    except Exception:
        payload.pop("is_deleted", None)
        supabase.table("recurring_transactions").insert(payload).execute()


def update_recurring(recurring_id: int, end_month) -> None:
    """定期収支の終了月を更新します。"""
    end_month_str = pd.Timestamp(end_month).strftime("%Y-%m-%d") if pd.notna(end_month) else None
    supabase.table("recurring_transactions").update({"end_month": end_month_str}).eq("id", int(recurring_id)).execute()


def delete_recurring(recurring_id: int, delete_mode: str, selected_month: date) -> None:
    """定期収支を全削除または指定月以降停止にします。"""
    if delete_mode == "all":
        try:
            supabase.table("recurring_transactions").update({"is_deleted": True}).eq("id", int(recurring_id)).execute()
        except Exception:
            supabase.table("recurring_transactions").delete().eq("id", int(recurring_id)).execute()
        return

    stop_month = pd.Timestamp(selected_month).to_period("M").to_timestamp()
    supabase.table("recurring_transactions").update({"end_month": stop_month.strftime("%Y-%m-%d")}).eq(
        "id", int(recurring_id)
    ).execute()


def active_categories(cat_df: pd.DataFrame, tx_type: str | None = None) -> list[str]:
    """有効なカテゴリ名を種別で絞り込んで返します。"""
    data = cat_df[~cat_df["is_deleted"]]
    if tx_type:
        data = data[data["type"] == tx_type]
    return data["name"].dropna().tolist()


def apply_recurring(month_df: pd.DataFrame, recurring_df: pd.DataFrame, selected_month: date) -> pd.DataFrame:
    """指定月の表示用データに定期収支を合成します。"""
    if recurring_df.empty:
        return month_df

    current = pd.Timestamp(selected_month).to_period("M").to_timestamp()
    rows: list[dict[str, Any]] = []
    active = recurring_df[(recurring_df["active"]) & (~recurring_df["is_deleted"])]

    for _, row in active.iterrows():
        start = pd.Timestamp(row["start_month"]).to_period("M").to_timestamp()
        end = pd.Timestamp(row["end_month"]).to_period("M").to_timestamp() if pd.notna(row["end_month"]) else None
        if start <= current and (end is None or current <= end):
            rows.append(
                {
                    "id": pd.NA,
                    "date": current.replace(day=int(row["day"])),
                    "type": row["type"],
                    "category": row["category"],
                    "amount": int(row["amount"]),
                    "description": row.get("description") or "定期",
                    "signed_amount": int(row["amount"]) if row["type"] == "income" else -int(row["amount"]),
                    "source": "recurring",
                }
            )

    if not rows:
        return month_df

    base = month_df.copy()
    base["source"] = "manual"
    combined = pd.concat([base, pd.DataFrame(rows)], ignore_index=True)
    return combined.drop_duplicates(subset=["date", "type", "category", "amount", "description"])


def expand_recurring_transactions(transactions_df: pd.DataFrame, recurring_df: pd.DataFrame, until_month: date) -> pd.DataFrame:
    """資産計算用に定期収支を過去から対象月まで展開します。"""
    result = transactions_df.copy()
    if recurring_df.empty:
        return result

    rows: list[dict[str, Any]] = []
    until = pd.Timestamp(until_month).to_period("M").to_timestamp()
    active = recurring_df[(recurring_df["active"]) & (~recurring_df["is_deleted"])]

    for _, row in active.iterrows():
        start = pd.Timestamp(row["start_month"]).to_period("M").to_timestamp()
        end = pd.Timestamp(row["end_month"]).to_period("M").to_timestamp() if pd.notna(row["end_month"]) else until
        end = min(end, until)
        for month in pd.date_range(start=start, end=end, freq="MS"):
            amount = int(row["amount"])
            rows.append(
                {
                    "id": pd.NA,
                    "date": month.replace(day=int(row["day"])),
                    "type": row["type"],
                    "amount": amount,
                    "category": row["category"],
                    "description": row.get("description") or "定期",
                    "signed_amount": amount if row["type"] == "income" else -amount,
                }
            )

    if rows:
        result = pd.concat([result, pd.DataFrame(rows)], ignore_index=True)
    return normalize_transactions(result)


def month_balances(transactions_df: pd.DataFrame, snapshots_df: pd.DataFrame, selected_month: date) -> tuple[int, int]:
    """対象月の月初残高と月末残高を計算します。"""
    if snapshots_df.empty:
        base_balance = 0
        base_cutoff = pd.Timestamp("1900-01-01")
    else:
        latest = snapshots_df.sort_values("snapshot_month").iloc[-1]
        base_balance = int(latest["balance"])
        base_month = pd.Timestamp(latest["snapshot_month"]).to_period("M").to_timestamp()
        base_cutoff = base_month + pd.offsets.MonthEnd(0)

    tx = transactions_df.copy()
    current = pd.Timestamp(selected_month).to_period("M")
    start = current.to_timestamp()
    end = start + pd.offsets.MonthEnd(0)

    before = tx[(tx["date"] > base_cutoff) & (tx["date"] < start)]["signed_amount"].sum()
    during = tx[(tx["date"] >= start) & (tx["date"] <= end)]["signed_amount"].sum()
    opening = int(base_balance + before)
    return opening, int(opening + during)


def monthly_asset_rows(transactions_df: pd.DataFrame, snapshots_df: pd.DataFrame, selected_month: date) -> pd.DataFrame:
    """資産推移画面に使う直近12ヶ月の月次集計を作成します。"""
    selected = pd.Timestamp(selected_month).to_period("M")
    months = [selected - 11 + i for i in range(12)]
    rows: list[dict[str, Any]] = []

    for period in months:
        start = period.to_timestamp()
        end = start + pd.offsets.MonthEnd(0)
        opening, ending = month_balances(transactions_df, snapshots_df, start.date())
        month_df = transactions_df[(transactions_df["date"] >= start) & (transactions_df["date"] <= end)]
        income = int(month_df.loc[month_df["type"] == "income", "amount"].sum())
        expense = int(month_df.loc[month_df["type"] == "expense", "amount"].sum())
        rows.append(
            {
                "month": start,
                "month_label": format_month(start),
                "opening": opening,
                "income": income,
                "expense": expense,
                "expense_negative": -expense,
                "net": income - expense,
                "balance": ending,
            }
        )
    return pd.DataFrame(rows)


def render_hero(selected_month: date) -> None:
    """ページ上部のタイトルエリアを表示します。"""
    st.markdown(
        f"""
        <div class="app-hero">
            <div>
                <h1>資産管理アプリ</h1>
                <p>毎月の収支、予算、定期収支、残高推移をひとつの画面感で管理します。</p>
            </div>
            <div class="hero-month">{month_label(selected_month)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, sub: str = "") -> None:
    """カード型のKPIを表示します。"""
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def insight_card(title: str, value: str, note: str) -> None:
    """月間状況の短い気づきをカード表示します。"""
    st.markdown(
        f"""
        <div class="insight-card">
            <div class="insight-title">{title}</div>
            <div class="insight-value">{value}</div>
            <div class="insight-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_top_controls(balance_ready: bool, recurring_ready: bool) -> tuple[str, date]:
    """サイドバーの代わりになる上部ナビゲーションと対象月選択を表示します。"""
    pages = ["収支入力", "月間収支", "資産推移", "分析", "設定"]
    labels = {
        "収支入力": "入力",
        "月間収支": "月間",
        "資産推移": "推移",
        "分析": "分析",
        "設定": "設定",
    }

    left, middle, right = st.columns([2.4, .95, 1.25])
    with left:
        st.markdown('<div class="nav-caption">NAVIGATION</div>', unsafe_allow_html=True)
        page_label = st.segmented_control(
            "メニュー",
            [labels[page] for page in pages],
            default=labels[pages[0]],
            label_visibility="collapsed",
            key="main_page_nav",
        )
    with middle:
        st.toggle("スマホ用カード表示", value=False, key="mobile_card_mode")
    with right:
        selected_month = month_selector("対象月", "main_month")

    render_setup_notice(balance_ready, recurring_ready)
    reverse_labels = {value: key for key, value in labels.items()}
    return reverse_labels[page_label], selected_month


def mobile_card_mode() -> bool:
    """スマホ向けカード表示モードが有効かを返します。"""
    return bool(st.session_state.get("mobile_card_mode", False))


def render_compact_card(title: str, amount: str, chips: list[str], body: str = "") -> None:
    """HTMLを使わずにコンパクトな一覧カードを表示します。"""
    with st.container(border=True):
        cols = st.columns([1.7, 1])
        cols[0].markdown(f"**{title}**")
        cols[1].markdown(f"**{amount}**")
        if chips:
            st.caption(" / ".join(str(chip) for chip in chips if chip))
        if body:
            st.caption(body)


def render_mobile_transaction_cards(data: pd.DataFrame, tx_type: str) -> None:
    """取引一覧をスマホ向けカードとして表示します。"""
    if not mobile_card_mode():
        return
    tx = data[data["type"] == tx_type].sort_values("date", ascending=False)
    if tx.empty:
        st.info("表示できるデータがありません。")
        return

    st.caption("カード表示")
    for _, row in tx.iterrows():
        source = "定期" if row.get("source") == "recurring" else "手入力"
        title = str(row.get("description") or row.get("category") or type_label(tx_type))
        render_compact_card(
            title=title,
            amount=yen(row["amount"]),
            chips=[format_jp_date(row["date"]), str(row.get("category") or "未分類"), source],
        )


def render_mobile_table_cards(df: pd.DataFrame, title_col: str, amount_col: str, meta_cols: list[str]) -> None:
    """汎用テーブルをスマホ向けカードとして表示します。"""
    if not mobile_card_mode():
        return
    if df.empty:
        st.info("表示できるデータがありません。")
        return

    st.caption("カード表示")
    for _, row in df.iterrows():
        amount = row[amount_col]
        amount_text = amount if isinstance(amount, str) else yen(amount)
        chips = []
        for col in meta_cols:
            if col in row and pd.notna(row[col]):
                value = row[col]
                value_text = value if isinstance(value, str) else yen(value)
                chips.append(f"{col}: {value_text}")
        render_compact_card(str(row[title_col]), amount_text, chips)


def render_mobile_info_cards(df: pd.DataFrame, title_col: str, value_col: str, meta_cols: list[str]) -> None:
    """金額以外の一覧をスマホ向けカードとして表示します。"""
    if not mobile_card_mode():
        return
    if df.empty:
        st.info("表示できるデータがありません。")
        return

    st.caption("カード表示")
    for _, row in df.iterrows():
        chips = [f"{col}: {row[col]}" for col in meta_cols if col in row and pd.notna(row[col])]
        render_compact_card(str(row[title_col]), str(row[value_col]), chips)


def category_summary(month_df: pd.DataFrame, budgets_df: pd.DataFrame, categories: list[str], tx_type: str) -> pd.DataFrame:
    """カテゴリ別の予定・実績・差額テーブルを作成します。"""
    actual = month_df[month_df["type"] == tx_type].groupby("category")["amount"].sum().rename("実際")
    planned = budgets_df.set_index("category")["amount"].rename("予定") if not budgets_df.empty else pd.Series(dtype=float)
    summary = pd.concat([planned, actual], axis=1).reindex(pd.Index(categories, name="カテゴリ")).fillna(0)
    summary["差額"] = summary["実際"] - summary["予定"] if tx_type == "income" else summary["予定"] - summary["実際"]
    return summary.astype(int)


def render_category_charts(month_df: pd.DataFrame) -> None:
    """支出・収入をカテゴリ別の横棒グラフで表示します。"""
    cols = st.columns(2)
    for col, tx_type, title, color in [
        (cols[0], "expense", "支出カテゴリ", "#ff8a5b"),
        (cols[1], "income", "収入カテゴリ", "#4dabf7"),
    ]:
        with col:
            st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
            data = month_df[month_df["type"] == tx_type].groupby("category", as_index=False)["amount"].sum()
            if data.empty:
                st.info(f"{title}のデータがありません。")
                continue
            chart = (
                alt.Chart(data)
                .mark_bar(color=color, cornerRadiusEnd=4)
                .encode(
                    x=alt.X("amount:Q", title="金額"),
                    y=alt.Y("category:N", sort="-x", title="カテゴリ"),
                    tooltip=[alt.Tooltip("category:N", title="カテゴリ"), alt.Tooltip("amount:Q", title="金額", format=",")],
                )
            )
            st.altair_chart(chart, use_container_width=True)


def render_budget_table(title: str, summary: pd.DataFrame) -> None:
    """予定・実績・差額のカテゴリ別テーブルを表示します。"""
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    total = pd.DataFrame(
        {"予定": [summary["予定"].sum()], "実際": [summary["実際"].sum()], "差額": [summary["差額"].sum()]},
        index=["合計"],
    )
    table = pd.concat([total, summary])
    mobile_table = table.reset_index().rename(columns={"index": "カテゴリ"})
    render_mobile_table_cards(mobile_table, "カテゴリ", "実際", ["予定", "差額"])
    if not mobile_card_mode():
        st.dataframe(
            table,
            use_container_width=True,
            column_config={
                "予定": st.column_config.NumberColumn(format="¥%d"),
                "実際": st.column_config.NumberColumn(format="¥%d"),
                "差額": st.column_config.NumberColumn(format="¥%d"),
            },
        )


def render_monthly_insights(month_df: pd.DataFrame, budgets_df: pd.DataFrame, cat_df: pd.DataFrame, selected_month: date) -> None:
    """月間収支から自動インサイトを3つ表示します。"""
    st.markdown('<div class="section-title">今月のインサイト</div>', unsafe_allow_html=True)

    expense_df = month_df[month_df["type"] == "expense"]
    top_category = "支出なし"
    top_amount = 0
    if not expense_df.empty:
        top = expense_df.groupby("category")["amount"].sum().sort_values(ascending=False)
        top_category = str(top.index[0])
        top_amount = int(top.iloc[0])

    expense_total = int(expense_df["amount"].sum())
    expense_budget = int(
        budgets_df[budgets_df["category"].isin(active_categories(cat_df, "expense"))]["amount"].sum()
    ) if not budgets_df.empty else 0
    budget_gap = expense_budget - expense_total
    budget_status = "予算内" if budget_gap >= 0 else "予算超過"
    budget_note = f"支出予算 {yen(expense_budget)} / 実績 {yen(expense_total)}" if expense_budget else "支出予算を設定すると精度が上がります"

    selected_ts = pd.Timestamp(selected_month)
    month_end = selected_ts + pd.offsets.MonthEnd(0)
    today = pd.Timestamp.today().normalize()
    remaining_days = max((month_end.normalize() - today).days + 1, 0) if today.to_period("M") == selected_ts.to_period("M") else 0
    daily_budget = int(max(budget_gap, 0) / remaining_days) if remaining_days and expense_budget else 0

    cols = st.columns(3)
    with cols[0]:
        insight_card("最大支出カテゴリ", f"{top_category} / {yen(top_amount)}", "支出の偏りをすぐ確認できます")
    with cols[1]:
        insight_card("予算ステータス", f"{budget_status} {yen(abs(budget_gap))}", budget_note)
    with cols[2]:
        insight_card("残り1日の目安", yen(daily_budget), f"今月の残り {remaining_days}日で使える平均額")


def render_transaction_form(tx_type: str, categories: list[str], selected_month: date) -> None:
    """支出または収入の追加フォームを表示します。"""
    title = type_label(tx_type)
    with st.form(f"add_{tx_type}_form", clear_on_submit=True):
        cols = st.columns([1, 1.2, 1.4, 1.7])
        tx_date = cols[0].date_input("日付", value=selected_month, key=f"{tx_type}_date")
        amount = cols[1].number_input("金額", min_value=0, step=100, value=0, key=f"{tx_type}_amount")
        category = cols[2].selectbox("カテゴリ", categories, key=f"{tx_type}_category")
        description = cols[3].text_input("説明", key=f"{tx_type}_description")
        if st.form_submit_button(f"{title}を追加", type="primary"):
            if int(amount) <= 0:
                st.warning("金額を入力してください。")
                return
            save_transaction(tx_date, tx_type, category, int(amount), description)
            st.success(f"{title}を追加しました。")
            st.rerun()


def render_transaction_editor(month_df: pd.DataFrame, categories: list[str], tx_type: str) -> None:
    """取引一覧を編集・削除できるテーブルとして表示します。"""
    data = month_df[(month_df["type"] == tx_type) & (month_df.get("source", "manual") != "recurring")].copy()
    if data.empty:
        st.info("手入力のデータがありません。")
        return

    if mobile_card_mode():
        render_transaction_card_editor(data, categories, tx_type)
        return
    editor = data[["id", "date", "amount", "category", "description"]].copy()
    editor["削除"] = False
    edited = st.data_editor(
        editor,
        key=f"{tx_type}_editor",
        use_container_width=True,
        hide_index=True,
        disabled=["date"],
        column_config={
            "id": None,
            "date": st.column_config.DateColumn("日付", format="YYYY-MM-DD"),
            "amount": st.column_config.NumberColumn("金額", step=1, format="¥%d"),
            "category": st.column_config.SelectboxColumn("カテゴリ", options=categories),
            "description": st.column_config.TextColumn("説明"),
            "削除": st.column_config.CheckboxColumn("削除"),
        },
    )

    if st.button("変更を保存", key=f"{tx_type}_save"):
        delete_rows = edited[edited["削除"]]
        for _, row in delete_rows.iterrows():
            delete_transaction(int(row["id"]))

        changed_count = 0
        keep_rows = edited[~edited["削除"]]
        original = editor.drop(columns=["削除"])
        merged = keep_rows.merge(original, on="id", suffixes=("_new", "_old"))
        for _, row in merged.iterrows():
            amount_new = int(float(row["amount_new"]))
            changed = (
                pd.Timestamp(row["date_new"]).date() != pd.Timestamp(row["date_old"]).date()
                or amount_new != int(row["amount_old"])
                or str(row["category_new"]) != str(row["category_old"])
                or str(row["description_new"] or "") != str(row["description_old"] or "")
            )
            if changed:
                update_transaction(int(row["id"]), amount_new, str(row["category_new"]), str(row["description_new"] or ""))
                changed_count += 1

        st.success(f"削除:{len(delete_rows)}件 / 更新:{changed_count}件")
        st.rerun()


def render_transaction_card_editor(data: pd.DataFrame, categories: list[str], tx_type: str) -> None:
    """スマホでも操作しやすい1件単位の取引編集フォームを表示します。"""
    st.caption("カード編集")
    for _, row in data.sort_values("date", ascending=False).iterrows():
        transaction_id = int(row["id"])
        title = str(row.get("description") or row.get("category") or type_label(tx_type))
        with st.expander(f"{format_jp_date(row['date'])} / {title} / {yen(row['amount'])}"):
            with st.form(f"transaction_card_edit_{tx_type}_{transaction_id}"):
                amount = st.number_input(
                    "金額",
                    min_value=0,
                    step=100,
                    value=int(row["amount"]),
                    key=f"card_amount_{tx_type}_{transaction_id}",
                )
                current_category = str(row.get("category") or "")
                category_index = categories.index(current_category) if current_category in categories else 0
                category = st.selectbox(
                    "カテゴリ",
                    categories,
                    index=category_index,
                    key=f"card_category_{tx_type}_{transaction_id}",
                )
                description = st.text_input(
                    "説明",
                    value=str(row.get("description") or ""),
                    key=f"card_description_{tx_type}_{transaction_id}",
                )
                delete_this = st.checkbox("この取引を削除する", key=f"card_delete_{tx_type}_{transaction_id}")
                submitted = st.form_submit_button("保存")
                if submitted:
                    if delete_this:
                        delete_transaction(transaction_id)
                        st.success("削除しました。")
                        st.rerun()
                    if int(amount) <= 0:
                        st.error("金額は1円以上で入力してください。")
                        return
                    update_transaction(transaction_id, int(amount), category, description)
                    st.success("更新しました。")
                    st.rerun()


def render_transaction_page(month_df: pd.DataFrame, cat_df: pd.DataFrame, selected_month: date) -> None:
    """収支入力ページを表示します。"""
    st.markdown('<div class="section-title">収支入力</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-caption">支出と収入をタブで切り替え、追加・編集・削除できます。</div>', unsafe_allow_html=True)
    tabs = st.tabs(["💸 支出", "💰 収入"])
    for tab, tx_type in [(tabs[0], "expense"), (tabs[1], "income")]:
        with tab:
            categories = active_categories(cat_df, tx_type)
            if not categories:
                st.warning("カテゴリを先に追加してください。")
                continue
            render_transaction_form(tx_type, categories, selected_month)
            st.divider()
            render_transaction_editor(month_df, categories, tx_type)


def render_monthly_page(
    month_df: pd.DataFrame, budgets_df: pd.DataFrame, cat_df: pd.DataFrame, opening: int, ending: int, selected_month: date
) -> None:
    """月間収支ページを表示します。"""
    income = int(month_df.loc[month_df["type"] == "income", "amount"].sum())
    expense = int(month_df.loc[month_df["type"] == "expense", "amount"].sum())
    saving = income - expense
    saving_rate = (saving / opening * 100) if opening else 0

    cols = st.columns(4)
    with cols[0]:
        metric_card("収入", yen(income), "この月の入金合計")
    with cols[1]:
        metric_card("支出", yen(expense), "この月の出金合計")
    with cols[2]:
        metric_card("貯蓄", yen(saving), "収入 - 支出")
    with cols[3]:
        metric_card("貯蓄率", f"{saving_rate:.1f}%", "月初残高に対する増減")

    st.divider()
    render_monthly_insights(month_df, budgets_df, cat_df, selected_month)
    st.divider()
    left, right = st.columns([1.15, .85])
    with left:
        balance_df = pd.DataFrame({"項目": ["月初残高", "月末残高"], "残高": [opening, ending]})
        chart = alt.Chart(balance_df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=ACCENT).encode(
            x=alt.X("項目:N", title=None),
            y=alt.Y("残高:Q", title="残高"),
            tooltip=["項目", alt.Tooltip("残高:Q", format=",")],
        )
        st.altair_chart(chart, use_container_width=True)
    with right:
        st.markdown(
            f"""
            <div class="panel">
                <span class="status-pill">月次サマリー</span>
                <div style="height:.85rem"></div>
                <div class="metric-label">月初残高</div>
                <div class="metric-value">{yen(opening)}</div>
                <div style="height:.7rem"></div>
                <div class="metric-label">月末残高</div>
                <div class="metric-value">{yen(ending)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()
    render_category_charts(month_df)
    st.divider()
    render_budget_table("支出 予算進捗", category_summary(month_df, budgets_df, active_categories(cat_df, "expense"), "expense"))
    render_budget_table("収入 予定進捗", category_summary(month_df, budgets_df, active_categories(cat_df, "income"), "income"))


def render_asset_page(transactions_df: pd.DataFrame, snapshots_df: pd.DataFrame, selected_month: date) -> None:
    """資産推移ページを表示します。"""
    monthly = monthly_asset_rows(transactions_df, snapshots_df, selected_month)
    if monthly.empty:
        st.info("表示できる資産データがありません。")
        return

    current = int(monthly.iloc[-1]["balance"])
    prev = int(monthly.iloc[-2]["balance"]) if len(monthly) > 1 else current
    avg_net = int(monthly["net"].mean())
    cols = st.columns(3)
    with cols[0]:
        metric_card("現在資産", yen(current), "選択月の月末残高")
    with cols[1]:
        metric_card("前月比", yen(current - prev), "前月末との差分")
    with cols[2]:
        metric_card("平均増減", yen(avg_net), "直近12ヶ月平均")

    st.divider()
    base = alt.Chart(monthly).encode(x=alt.X("month_label:N", sort=monthly["month_label"].tolist(), title=None))
    income_bar = base.mark_bar(color="#4dabf7", cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        y=alt.Y("income:Q", title="収支 / 残高")
    )
    expense_bar = base.mark_bar(color="#ffad66", cornerRadiusBottomLeft=3, cornerRadiusBottomRight=3).encode(y="expense_negative:Q")
    balance_line = base.mark_line(point=True, strokeWidth=3, color=NAVY).encode(y="balance:Q")
    st.altair_chart(income_bar + expense_bar + balance_line, use_container_width=True)

    display = monthly[["month_label", "opening", "income", "expense", "net", "balance"]].copy().iloc[::-1]
    display = display.rename(
        columns={"month_label": "年月", "opening": "月初残高", "income": "収入", "expense": "支出", "net": "増減", "balance": "月末残高"}
    )
    render_mobile_table_cards(display, "年月", "月末残高", ["月初残高", "収入", "支出", "増減"])
    if not mobile_card_mode():
        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            column_config={col: st.column_config.NumberColumn(format="¥%d") for col in display.columns if col != "年月"},
        )


def render_analysis_page(month_df: pd.DataFrame, budgets_df: pd.DataFrame, cat_df: pd.DataFrame) -> None:
    """カテゴリ別の利用状況と予算差分を分析表示します。"""
    st.markdown('<div class="section-title">カテゴリ分析</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-caption">支出の偏りと予算との差分を見ながら、カテゴリ整理の判断材料にできます。</div>', unsafe_allow_html=True)

    expense = month_df[month_df["type"] == "expense"].groupby("category", as_index=False)["amount"].sum()
    income = month_df[month_df["type"] == "income"].groupby("category", as_index=False)["amount"].sum()
    total_expense = int(expense["amount"].sum()) if not expense.empty else 0
    top_expense = expense.sort_values("amount", ascending=False).head(1)
    top_name = str(top_expense["category"].iloc[0]) if not top_expense.empty else "なし"
    top_share = int(top_expense["amount"].iloc[0] / total_expense * 100) if total_expense else 0

    cols = st.columns(3)
    with cols[0]:
        metric_card("支出カテゴリ数", f"{len(expense)}件", "今月使われた支出カテゴリ")
    with cols[1]:
        metric_card("最大カテゴリ", top_name, f"支出全体の {top_share}%")
    with cols[2]:
        metric_card("未使用カテゴリ", f"{len(set(active_categories(cat_df, 'expense')) - set(expense['category'].tolist()))}件", "整理候補の目安")

    st.divider()
    left, right = st.columns(2)
    with left:
        st.markdown('<div class="section-title">支出ランキング</div>', unsafe_allow_html=True)
        if expense.empty:
            st.info("支出データがありません。")
        else:
            chart = (
                alt.Chart(expense.sort_values("amount", ascending=False).head(10))
                .mark_bar(color=ACCENT, cornerRadiusEnd=4)
                .encode(
                    x=alt.X("amount:Q", title="金額"),
                    y=alt.Y("category:N", sort="-x", title="カテゴリ"),
                    tooltip=[alt.Tooltip("category:N", title="カテゴリ"), alt.Tooltip("amount:Q", title="金額", format=",")],
                )
            )
            st.altair_chart(chart, use_container_width=True)
    with right:
        st.markdown('<div class="section-title">収入ランキング</div>', unsafe_allow_html=True)
        if income.empty:
            st.info("収入データがありません。")
        else:
            chart = (
                alt.Chart(income.sort_values("amount", ascending=False).head(10))
                .mark_bar(color="#4dabf7", cornerRadiusEnd=4)
                .encode(
                    x=alt.X("amount:Q", title="金額"),
                    y=alt.Y("category:N", sort="-x", title="カテゴリ"),
                    tooltip=[alt.Tooltip("category:N", title="カテゴリ"), alt.Tooltip("amount:Q", title="金額", format=",")],
                )
            )
            st.altair_chart(chart, use_container_width=True)

    st.divider()
    render_budget_table("カテゴリ別 予算差分", category_summary(month_df, budgets_df, active_categories(cat_df, "expense"), "expense"))


def render_snapshot_settings(snapshots_df: pd.DataFrame) -> None:
    """基準残高の設定画面を表示します。"""
    st.subheader("基準残高")
    if not snapshots_df.empty:
        latest = snapshots_df.sort_values("snapshot_month").iloc[-1]
        st.info(f"現在の基準: {latest['snapshot_month'].strftime('%Y-%m')} / {yen(latest['balance'])}")

    with st.form("snapshot_form"):
        snapshot_month = st.date_input("基準月", value=date.today().replace(day=1))
        snapshot_balance = st.number_input("残高", min_value=0, step=10000)
        confirm = st.checkbox("現在の基準残高を置き換える")
        if st.form_submit_button("更新", type="primary"):
            if not confirm:
                st.error("確認チェックを入れてください。")
            else:
                save_balance_snapshot(snapshot_month, int(snapshot_balance))
                st.success("基準残高を更新しました。")
                st.rerun()


def recurring_display_frame(df: pd.DataFrame) -> pd.DataFrame:
    """定期収支の一覧表示用DataFrameを作成します。"""
    if df.empty:
        return pd.DataFrame(columns=["ID", "種別", "日", "カテゴリ", "金額", "開始月", "終了月", "説明", "削除"])
    result = df.copy()
    result["ID"] = result["id"]
    result["種別"] = result["type"].map(type_label)
    result["日"] = result["day"]
    result["カテゴリ"] = result["category"]
    result["金額"] = result["amount"]
    result["開始月"] = result["start_month"]
    result["終了月"] = result["end_month"]
    result["説明"] = result["description"]
    result["削除"] = False
    return result[["ID", "種別", "日", "カテゴリ", "金額", "開始月", "終了月", "説明", "削除"]]


def render_recurring_settings(recurring_df: pd.DataFrame, cat_df: pd.DataFrame, selected_month: date) -> None:
    """定期収支の追加・停止・削除画面を表示します。"""
    st.subheader("定期収入・定期支出")
    type_label_selected = st.segmented_control("種別", ["支出", "収入"], default="支出", key="recurring_type")
    recurring_type = type_value(type_label_selected)
    categories = active_categories(cat_df, recurring_type)

    with st.form("recurring_form", clear_on_submit=True):
        cols = st.columns([.7, 1.1, 1.4, 1, 1])
        day = cols[0].number_input("日", min_value=1, max_value=28, value=1, step=1)
        amount = cols[1].number_input("金額", min_value=0, step=1000)
        category = cols[2].selectbox("カテゴリ", categories)
        start_month = cols[3].date_input("開始月", value=selected_month)
        use_end = cols[4].checkbox("終了月あり")
        end_month = st.date_input("終了月", value=selected_month, disabled=not use_end)
        desc = st.text_input("説明")
        if st.form_submit_button("定期収支を追加", type="primary"):
            save_recurring(recurring_type, int(day), int(amount), category, desc, pd.Timestamp(start_month), end_month if use_end else None)
            st.success("定期収支を追加しました。")
            st.rerun()

    st.divider()
    tabs = st.tabs(["💸 支出", "💰 収入"])
    for tab, tx_type in [(tabs[0], "expense"), (tabs[1], "income")]:
        with tab:
            df = recurring_df[(recurring_df["type"] == tx_type) & (~recurring_df["is_deleted"])].copy()
            recurring_cards = recurring_display_frame(df)
            if mobile_card_mode():
                render_recurring_card_editor(df, tx_type, selected_month)
                continue
            edited = st.data_editor(
                recurring_cards,
                key=f"recurring_editor_{tx_type}",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID": None,
                    "日": st.column_config.NumberColumn("日", min_value=1, max_value=28, step=1, disabled=True),
                    "金額": st.column_config.NumberColumn("金額", format="¥%d", disabled=True),
                    "開始月": st.column_config.DateColumn("開始月", format="YYYY-MM", disabled=True),
                    "終了月": st.column_config.DateColumn("終了月", format="YYYY-MM"),
                    "削除": st.column_config.CheckboxColumn("削除"),
                },
                disabled=["種別", "カテゴリ", "説明"],
            )
            delete_mode = st.radio("削除方法", ["全て削除", "選択月以降を停止"], horizontal=True, key=f"delete_mode_{tx_type}")
            if st.button("一覧を保存", key=f"recurring_save_{tx_type}"):
                delete_rows = edited[edited["削除"]]
                for _, row in delete_rows.iterrows():
                    delete_recurring(int(row["ID"]), "all" if delete_mode == "全て削除" else "future", selected_month)
                for _, row in edited[~edited["削除"]].iterrows():
                    update_recurring(int(row["ID"]), row["終了月"])
                st.success(f"{len(edited)}件を確認しました。")
                st.rerun()


def render_recurring_card_editor(df: pd.DataFrame, tx_type: str, selected_month: date) -> None:
    """スマホでも操作しやすい定期収支の1件単位編集フォームを表示します。"""
    if df.empty:
        st.info("データがありません。")
        return

    st.caption("カード編集")
    for _, row in df.sort_values("start_month", ascending=False).iterrows():
        recurring_id = int(row["id"])
        title = f"{row['category']} / {yen(row['amount'])}"
        with st.expander(title):
            st.caption(f"{type_label(tx_type)} / 毎月{int(row['day'])}日 / 開始 {format_month(row['start_month'])}")
            with st.form(f"recurring_card_edit_{tx_type}_{recurring_id}"):
                has_end = pd.notna(row["end_month"])
                use_end = st.checkbox("終了月を設定", value=has_end, key=f"recurring_card_use_end_{recurring_id}")
                default_end = pd.Timestamp(row["end_month"]).date() if has_end else selected_month
                end_month = st.date_input("終了月", value=default_end, disabled=not use_end, key=f"recurring_card_end_{recurring_id}")
                delete_mode = st.radio(
                    "削除方法",
                    ["削除しない", "全て削除", "選択月以降を停止"],
                    horizontal=True,
                    key=f"recurring_card_delete_mode_{recurring_id}",
                )
                submitted = st.form_submit_button("保存")
                if submitted:
                    if delete_mode != "削除しない":
                        delete_recurring(recurring_id, "all" if delete_mode == "全て削除" else "future", selected_month)
                        st.success("削除設定を反映しました。")
                        st.rerun()
                    update_recurring(recurring_id, end_month if use_end else None)
                    st.success("更新しました。")
                    st.rerun()


def categories_display_frame(cat_df: pd.DataFrame) -> pd.DataFrame:
    """カテゴリ一覧の表示用DataFrameを作成します。"""
    data = cat_df[~cat_df["is_deleted"]].copy()
    data["ID"] = data["id"]
    data["カテゴリ名"] = data["name"]
    data["種別"] = data["type"].map(type_label)
    data["削除"] = False
    return data[["ID", "カテゴリ名", "種別", "削除"]]


def category_usage_counts(
    category_name: str, transactions_df: pd.DataFrame, budgets_df: pd.DataFrame, recurring_df: pd.DataFrame
) -> dict[str, int]:
    """カテゴリ名に紐づく各テーブルの件数を集計します。"""
    return {
        "transactions": int((transactions_df["category"] == category_name).sum()) if "category" in transactions_df.columns else 0,
        "budgets": int((budgets_df["category"] == category_name).sum()) if "category" in budgets_df.columns else 0,
        "recurring": int((recurring_df["category"] == category_name).sum()) if "category" in recurring_df.columns else 0,
    }


def render_category_stats(cat_df: pd.DataFrame, transactions_df: pd.DataFrame, budgets_df: pd.DataFrame, recurring_df: pd.DataFrame) -> None:
    """カテゴリ管理ページの利用状況サマリーを表示します。"""
    active = cat_df[~cat_df["is_deleted"]]
    total_tx = int(len(transactions_df))
    linked_categories = transactions_df["category"].nunique() if "category" in transactions_df.columns and not transactions_df.empty else 0
    recurring_count = int(len(recurring_df[~recurring_df["is_deleted"]])) if "is_deleted" in recurring_df.columns else int(len(recurring_df))
    st.markdown(
        f"""
        <div class="action-grid">
            <div class="action-card"><span>有効カテゴリ</span><strong>{len(active)}件</strong></div>
            <div class="action-card"><span>取引レコード</span><strong>{total_tx}件</strong></div>
            <div class="action-card"><span>使用中カテゴリ / 定期収支</span><strong>{linked_categories}種 / {recurring_count}件</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_category_add_form(cat_df: pd.DataFrame) -> None:
    """カテゴリ追加フォームを表示します。"""
    st.subheader("カテゴリ追加")
    with st.form("category_form", clear_on_submit=True):
        cols = st.columns([1, 2])
        new_type_label = cols[0].segmented_control("種別", ["支出", "収入"], default="支出")
        new_name = cols[1].text_input("カテゴリ名")
        if st.form_submit_button("カテゴリを追加", type="primary"):
            name = new_name.strip()
            if not name:
                st.error("カテゴリ名を入力してください。")
            elif name in active_categories(cat_df):
                st.error("同じカテゴリ名が既にあります。")
            else:
                save_category(name, type_value(new_type_label))
                st.success("カテゴリを追加しました。")
                st.rerun()


def render_category_rename_form(
    cat_df: pd.DataFrame, transactions_df: pd.DataFrame, budgets_df: pd.DataFrame, recurring_df: pd.DataFrame
) -> None:
    """カテゴリ名変更フォームを表示します。"""
    st.subheader("カテゴリ名変更")
    active = cat_df[~cat_df["is_deleted"]].copy()
    type_label_selected = st.segmented_control("種別", ["支出", "収入"], default="支出", key="rename_type")
    tx_type = type_value(type_label_selected)
    options = active[active["type"] == tx_type]["name"].tolist()
    if not options:
        st.info("変更できるカテゴリがありません。")
        return

    with st.form("category_rename_form"):
        scoped = active[active["type"] == tx_type].copy()
        source_ids = scoped["id"].astype(int).tolist()
        source_id = st.selectbox(
            "変更するカテゴリ",
            source_ids,
            key="rename_source_category_id",
            format_func=lambda category_id: category_name_by_id(scoped, int(category_id)),
        )
        old_name = category_name_by_id(scoped, int(source_id))
        usage = category_usage_counts(old_name, transactions_df, budgets_df, recurring_df)
        st.caption(f"紐づく取引 {usage['transactions']}件 / 予算 {usage['budgets']}件 / 定期収支 {usage['recurring']}件も同時に変更します。")
        new_name = st.text_input("新しいカテゴリ名", value=old_name)
        submitted = st.form_submit_button("カテゴリ名を変更", type="primary")
        if submitted:
            new_name = new_name.strip()
            if not new_name:
                st.error("新しいカテゴリ名を入力してください。")
            elif new_name != old_name and new_name in active_categories(cat_df):
                st.error("同じカテゴリ名が既にあります。")
            elif new_name == old_name:
                st.info("変更はありません。")
            else:
                rename_category(int(source_id), old_name, new_name)
                st.success(f"{old_name} を {new_name} に変更しました。")
                st.rerun()


@st.dialog("カテゴリ削除の確認")
def render_category_delete_confirm_dialog() -> None:
    """カテゴリ削除前の最終確認ダイアログを表示します。"""
    pending = st.session_state.get("pending_category_delete")
    if not pending:
        st.info("確認する削除内容がありません。")
        if st.button("閉じる"):
            st.rerun()
        return

    st.markdown("以下の内容でカテゴリを削除します。")
    st.warning(
        f"「{pending['old_name']}」に紐づく取引・予算・定期収支を、"
        f"「{pending['target_name']}」へ移行します。"
    )
    st.caption(
        f"移行対象: 取引 {pending['usage']['transactions']}件 / "
        f"予算 {pending['usage']['budgets']}件 / 定期収支 {pending['usage']['recurring']}件"
    )

    cols = st.columns(2)
    if cols[0].button("キャンセル", key="cancel_category_delete"):
        st.session_state.pop("pending_category_delete", None)
        st.rerun()
    if cols[1].button("移行して削除", type="primary", key="confirm_category_delete"):
        if pending["mode"] == "新規カテゴリを作成":
            save_category(pending["target_name"], pending["tx_type"])
        delete_category_with_reassignment(
            int(pending["source_id"]),
            pending["old_name"],
            pending["target_name"],
        )
        st.session_state.pop("pending_category_delete", None)
        st.success("カテゴリを削除しました。")
        st.rerun()


def render_category_delete_form(
    cat_df: pd.DataFrame, transactions_df: pd.DataFrame, budgets_df: pd.DataFrame, recurring_df: pd.DataFrame
) -> None:
    """カテゴリ削除時のデータ移行フォームを表示します。"""
    st.subheader("カテゴリ削除・データ移行")
    st.markdown(
        '<div class="danger-note">削除するカテゴリに紐づく取引・予算・定期収支は、選択した移行先カテゴリへ付け替えてから削除します。</div>',
        unsafe_allow_html=True,
    )
    active = cat_df[~cat_df["is_deleted"]].copy()
    type_label_selected = st.segmented_control("種別", ["支出", "収入"], default="支出", key="delete_type")
    tx_type = type_value(type_label_selected)
    scoped = active[active["type"] == tx_type].copy()
    source_ids = scoped["id"].astype(int).tolist()
    if not source_ids:
        st.info("削除できるカテゴリがありません。")
        return

    source_id = st.selectbox(
        "削除するカテゴリ",
        source_ids,
        key=f"delete_source_category_id_{tx_type}",
        format_func=lambda category_id: category_name_by_id(scoped, int(category_id)),
    )
    old_name = category_name_by_id(scoped, int(source_id))
    usage = category_usage_counts(old_name, transactions_df, budgets_df, recurring_df)
    st.caption(f"移行対象: 取引 {usage['transactions']}件 / 予算 {usage['budgets']}件 / 定期収支 {usage['recurring']}件")

    mode = st.radio("移行先", ["既存カテゴリ", "新規カテゴリを作成"], horizontal=True, key=f"delete_target_mode_{tx_type}")
    target_name = ""
    if mode == "既存カテゴリ":
        target_ids = [category_id for category_id in source_ids if category_id != int(source_id)]
        if not target_ids:
            st.warning("同じ種別の移行先カテゴリがありません。新規カテゴリを作成してください。")
        else:
            target_id = st.selectbox(
                "移行先カテゴリ",
                target_ids,
                key=f"delete_target_category_id_{tx_type}_{int(source_id)}",
                format_func=lambda category_id: category_name_by_id(scoped, int(category_id)),
            )
            target_name = category_name_by_id(scoped, int(target_id))
    else:
        target_name = st.text_input("新規カテゴリ名", key=f"delete_new_category_name_{tx_type}")

    target_name = target_name.strip()
    if target_name:
        st.info(f"「{old_name}」から「{target_name}」へ移行します。")

    if st.button("確認へ進む", type="primary", disabled=not target_name, key=f"open_category_delete_confirm_{tx_type}"):
        if target_name == old_name:
            st.error("削除するカテゴリ自身は移行先にできません。")
        elif mode == "新規カテゴリを作成" and target_name in active_categories(cat_df):
            st.error("同じカテゴリ名が既にあります。")
        else:
            st.session_state.pending_category_delete = {
                "source_id": int(source_id),
                "old_name": old_name,
                "target_name": target_name,
                "tx_type": tx_type,
                "mode": mode,
                "usage": usage,
            }
            st.rerun()

    if st.session_state.get("pending_category_delete"):
        render_category_delete_confirm_dialog()


def render_category_list(cat_df: pd.DataFrame) -> None:
    """カテゴリ一覧を表示します。"""
    st.subheader("カテゴリ一覧")
    category_cards = categories_display_frame(cat_df)
    render_mobile_info_cards(category_cards, "カテゴリ名", "種別", [])
    if not mobile_card_mode():
        st.dataframe(
            category_cards.drop(columns=["削除"]),
            key="category_list",
            use_container_width=True,
            hide_index=True,
            column_config={"ID": None},
        )


def render_category_settings(
    cat_df: pd.DataFrame, transactions_df: pd.DataFrame, budgets_df: pd.DataFrame, recurring_df: pd.DataFrame
) -> None:
    """カテゴリの追加・名称変更・削除移行画面を表示します。"""
    st.subheader("カテゴリ")
    st.caption("スマホでは、名称変更と削除・移行タブのフォームから1件ずつ安全に編集できます。")
    render_category_stats(cat_df, transactions_df, budgets_df, recurring_df)
    tabs = st.tabs(["追加", "名称変更", "削除・移行", "一覧"])
    with tabs[0]:
        render_category_add_form(cat_df)
    with tabs[1]:
        render_category_rename_form(cat_df, transactions_df, budgets_df, recurring_df)
    with tabs[2]:
        render_category_delete_form(cat_df, transactions_df, budgets_df, recurring_df)
    with tabs[3]:
        render_category_list(cat_df)


def render_budget_settings(cat_df: pd.DataFrame, budgets_df: pd.DataFrame) -> None:
    """カテゴリ別予算の編集画面を表示します。"""
    st.subheader("予算設定（全月共通）")
    categories = active_categories(cat_df)
    with st.form("budget_form"):
        selected_category = st.selectbox("カテゴリ", categories)
        existing = budgets_df[budgets_df["category"] == selected_category]
        default_amount = int(existing["amount"].iloc[0]) if not existing.empty else 0
        amount = st.number_input("予算", value=default_amount, step=1000)
        if st.form_submit_button("保存", type="primary"):
            save_budget(selected_category, int(amount))
            st.success("予算を保存しました。")
            st.rerun()

    merged = cat_df[~cat_df["is_deleted"]][["name", "type"]].merge(budgets_df, left_on="name", right_on="category", how="left")
    merged["amount"] = merged["amount"].fillna(0).astype(int)
    cols = st.columns(2)
    for col, tx_type, title in [(cols[0], "expense", "支出"), (cols[1], "income", "収入")]:
        with col:
            data = merged[merged["type"] == tx_type][["name", "amount"]].rename(columns={"name": "カテゴリ", "amount": "予算"})
            st.markdown(f"### {title}")
            render_mobile_table_cards(data, "カテゴリ", "予算", [])
            if not mobile_card_mode():
                st.dataframe(data, use_container_width=True, hide_index=True, column_config={"予算": st.column_config.NumberColumn(format="¥%d")})
            st.caption(f"合計: {yen(data['予算'].sum())}")


def render_settings_page(
    snapshots_df: pd.DataFrame,
    recurring_df: pd.DataFrame,
    cat_df: pd.DataFrame,
    budgets_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    selected_month: date,
) -> None:
    """設定ページのサブメニューを表示します。"""
    st.markdown('<div class="section-title">設定</div>', unsafe_allow_html=True)
    setting_page = st.segmented_control(
        "設定メニュー", ["基準残高", "定期収支", "カテゴリ", "予算"], default="基準残高", key="settings_menu"
    )
    if setting_page == "基準残高":
        render_snapshot_settings(snapshots_df)
    elif setting_page == "定期収支":
        render_recurring_settings(recurring_df, cat_df, selected_month)
    elif setting_page == "カテゴリ":
        render_category_settings(cat_df, transactions_df, budgets_df, recurring_df)
    elif setting_page == "予算":
        render_budget_settings(cat_df, budgets_df)


def render_setup_notice(balance_ready: bool, recurring_ready: bool) -> None:
    """追加テーブルが存在しない場合にサイドバーへ警告を表示します。"""
    missing = []
    if not balance_ready:
        missing.append("balance_snapshots")
    if not recurring_ready:
        missing.append("recurring_transactions")
    if missing:
        st.warning(f"追加機能に必要なテーブルが未作成です: {', '.join(missing)}")
        st.caption("SupabaseのSQL Editorで必要なテーブルを作成してください。")


def load_app_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, bool, bool]:
    """アプリで使う全テーブルを読み込み、画面用に正規化します。"""
    cat_df = normalize_categories(load_table("categories"))
    transactions_df = normalize_transactions(load_table("transactions"))
    budgets_df = normalize_budgets(load_table("budgets"))
    snapshots_raw, balance_ready = load_optional_table("balance_snapshots")
    recurring_raw, recurring_ready = load_optional_table("recurring_transactions")
    return (
        cat_df,
        transactions_df,
        budgets_df,
        normalize_snapshots(snapshots_raw),
        normalize_recurring(recurring_raw),
        balance_ready,
        recurring_ready,
    )


def main() -> None:
    """Streamlitアプリのエントリーポイントです。"""
    inject_styles()
    require_login()

    global supabase
    try:
        supabase = get_supabase_client()
        cat_df, transactions_df, budgets_df, snapshots_df, recurring_df, balance_ready, recurring_ready = load_app_data()
    except Exception as exc:
        st.error("Supabaseに接続できませんでした。secrets.toml の SUPABASE_URL / SUPABASE_KEY を確認してください。")
        st.exception(exc)
        st.stop()

    if cat_df.empty:
        st.error("categoriesテーブルにデータがありません。先にカテゴリを登録してください。")
        st.stop()

    selected_month = selected_month_from_state("main_month")
    render_hero(selected_month)
    page, selected_month = render_top_controls(balance_ready, recurring_ready)

    start, end = month_range(selected_month)
    full_transactions_df = expand_recurring_transactions(transactions_df, recurring_df, selected_month)
    month_manual_df = transactions_df[(transactions_df["date"] >= start) & (transactions_df["date"] <= end)].copy()
    month_df = apply_recurring(month_manual_df, recurring_df, selected_month)
    opening, ending = month_balances(full_transactions_df, snapshots_df, selected_month)

    if page == "収支入力":
        render_transaction_page(month_df, cat_df, selected_month)
    elif page == "月間収支":
        render_monthly_page(month_df, budgets_df, cat_df, opening, ending, selected_month)
    elif page == "資産推移":
        render_asset_page(full_transactions_df, snapshots_df, selected_month)
    elif page == "分析":
        render_analysis_page(month_df, budgets_df, cat_df)
    elif page == "設定":
        render_settings_page(snapshots_df, recurring_df, cat_df, budgets_df, transactions_df, selected_month)


if __name__ == "__main__":
    main()
