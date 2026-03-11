import hashlib
import json
import re
from typing import Dict, List, Optional
from zipfile import BadZipFile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from pypdf import PdfReader

st.set_page_config(page_title="Bin Allocation Visualizer", layout="wide")

DEFAULT_MAPPING = {
    "bin_id": ["bin_id", "Storage Bin", "Storage Bin.1"],
    "zone": ["zone", "Storage Type", "Storage Section"],
    "storage_section": ["storage_section", "Storage Section"],
    "aisle": ["aisle", "Aisle"],
    "stack": ["stack", "Stack"],
    "level": ["level", "Level"],
    "rack_bin_section": ["rack_bin_section", "Bin Section"],
    "rack_bin_depth": ["rack_bin_depth", "Bin Depth"],
    "bin_type": ["bin_type", "Storage Bin Type", "Fixed Stor. Bin Type", "Storage Type"],
    "status": ["status", "User Status"],
    "disabled_reason": ["disabled_reason", "User Status"],
    "capacity": ["capacity", "Total Capacity"],
    "used_capacity": ["used_capacity"],
    "empty_indicator": ["Empty Indicator"],
    "full_indicator": ["Full Indicator"],
    "stock_removal_block": ["Stock Removal Block"],
    "putaway_block": ["Putaway Block"],
    "remaining_capacity": ["Remaining Capacity"],
    "no_handling_units": ["No. Handling Units"],
}

TYPE_MAP = {
    "pick": "PICKING",
    "picking": "PICKING",
    "buffer": "BUFFER",
    "reserve": "BUFFER",
}

STATUS_MAP = {
    "available": "AVAILABLE",
    "free": "AVAILABLE",
    "empty": "AVAILABLE",
    "occupied": "OCCUPIED",
    "full": "OCCUPIED",
    "used": "OCCUPIED",
    "disabled": "DISABLED",
    "blocked": "DISABLED",
    "hold": "DISABLED",
}

COLOR_MAP = {
    "AVAILABLE": "#2ca02c",
    "OCCUPIED": "#1f77b4",
    "DISABLED": "#d62728",
    "UNKNOWN": "#7f7f7f",
}

DEFAULT_CODES_PDF = (
    "/Users/fibunix/Library/Containers/net.whatsapp.WhatsApp/Data/tmp/documents/"
    "2CDF3076-C85B-429C-9179-A249109FBBBC/--codes.pdf"
)

MANUAL_SECTION_MAPPING = {
    "RLY1": "Ladies",
    "RKD1": "Kids",
    "RMN1": "Men",
    "RHM1": "Home",
    "RDV1": "Divided",
}

PROCESSED_STORE_DIR = Path(__file__).resolve().parent / "processed_store"
PROCESSED_INDEX_FILE = PROCESSED_STORE_DIR / "index.jsonl"


def normalize_col_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).strip().lower())


def classify_storage_type(value: object) -> str:
    t = canonical_text(value).replace(" ", "")
    if t.startswith("rhp"):
        return "PICKING"
    if t.startswith("rhb"):
        return "BUFFER"
    return "OTHER"


def is_truthy(value: object) -> bool:
    t = canonical_text(value)
    return t in {"x", "1", "true", "yes", "y", "blocked", "hold"}


def canonical_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_bin_type(value: object) -> str:
    t = canonical_text(value)
    return TYPE_MAP.get(t, str(value).strip().upper() if str(value).strip() else "UNKNOWN")


def normalize_status(value: object) -> str:
    t = canonical_text(value)
    return STATUS_MAP.get(t, str(value).strip().upper() if str(value).strip() else "UNKNOWN")


def safe_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def generate_processed_id(df: pd.DataFrame) -> str:
    stable_df = df.reindex(sorted(df.columns), axis=1).fillna("")
    payload = stable_df.to_csv(index=False, lineterminator="\n").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16].upper()
    return f"BIN-{digest}"


def normalize_processed_id(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        return ""
    if normalized.startswith("BIN-"):
        return normalized
    return f"BIN-{normalized}"


def persist_processed_df(df: pd.DataFrame, processed_id: str, source_name: str) -> Path:
    PROCESSED_STORE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PROCESSED_STORE_DIR / f"{processed_id}.csv"
    df.to_csv(output_path, index=False)

    metadata = {
        "processed_id": processed_id,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "source_name": source_name,
    }
    with PROCESSED_INDEX_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(metadata) + "\n")
    return output_path


def load_processed_df(processed_id: str) -> Optional[pd.DataFrame]:
    normalized_id = normalize_processed_id(processed_id)
    if not normalized_id:
        return None
    input_path = PROCESSED_STORE_DIR / f"{normalized_id}.csv"
    if not input_path.exists():
        return None
    out = pd.read_csv(input_path)
    for col in ["capacity", "used_capacity", "remaining_capacity", "no_handling_units"]:
        if col in out.columns:
            out[col] = safe_number(out[col])
    if "is_empty" in out.columns:
        out["is_empty"] = (
            out["is_empty"].astype(str).str.strip().str.lower().isin({"true", "1", "x", "yes", "y"})
        )
    return out


def choose_column(label: str, columns: List[str], default_name: Optional[str]) -> Optional[str]:
    options = ["<not present>"] + columns
    default_idx = options.index(default_name) if default_name in options else 0
    selected = st.sidebar.selectbox(label, options, index=default_idx)
    return None if selected == "<not present>" else selected


def find_best_default(columns: List[str], candidates: List[str]) -> Optional[str]:
    if not candidates:
        return None
    for candidate in candidates:
        if candidate in columns:
            return candidate
    normalized = {normalize_col_name(c): c for c in columns}
    for candidate in candidates:
        key = normalize_col_name(candidate)
        if key in normalized:
            return normalized[key]
    return None


def derive_bin_type(row: pd.Series) -> str:
    current = normalize_bin_type(row.get("bin_type", ""))
    if current in {"PICKING", "BUFFER"}:
        return current
    t = canonical_text(row.get("bin_type", ""))
    if "pick" in t:
        return "PICKING"
    if "buffer" in t or "reserve" in t:
        return "BUFFER"
    by_storage_type = classify_storage_type(row.get("zone", ""))
    if by_storage_type in {"PICKING", "BUFFER"}:
        return by_storage_type
    return "OTHER"


def derive_status(row: pd.Series) -> str:
    current = normalize_status(row.get("status", ""))
    if current in {"AVAILABLE", "OCCUPIED", "DISABLED"}:
        return current

    has_block = is_truthy(row.get("stock_removal_block")) or is_truthy(row.get("putaway_block"))
    user_status = canonical_text(row.get("disabled_reason", ""))
    if has_block or (user_status not in {"", "0", "na", "n/a"}):
        return "DISABLED"

    if is_truthy(row.get("full_indicator")):
        return "OCCUPIED"
    if is_truthy(row.get("empty_indicator")):
        return "AVAILABLE"

    if float(row.get("used_capacity", 0) or 0) > 0:
        return "OCCUPIED"
    if float(row.get("no_handling_units", 0) or 0) > 0:
        return "OCCUPIED"
    return "AVAILABLE"


def derive_is_empty(row: pd.Series) -> bool:
    if is_truthy(row.get("empty_indicator")):
        return True
    if is_truthy(row.get("full_indicator")):
        return False
    if float(row.get("used_capacity", 0) or 0) > 0:
        return False
    if float(row.get("no_handling_units", 0) or 0) > 0:
        return False
    return normalize_status(row.get("status", "")) != "OCCUPIED"


@st.cache_data(show_spinner=False)
def load_section_mapping(pdf_path: str) -> Dict[str, str]:
    if not Path(pdf_path).exists():
        return MANUAL_SECTION_MAPPING.copy()
    reader = PdfReader(pdf_path)
    mapping: Dict[str, str] = {}
    for page in reader.pages:
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.lower() in {"sec", "description"}:
                continue
            if re.match(r"^[A-Z][a-z]{2}\s[A-Z][a-z]{2}\s\d{1,2}\s", line):
                continue
            m = re.match(r"^([A-Z0-9]{4})(.+)$", line)
            if not m:
                continue
            code = m.group(1).strip()
            desc = m.group(2).strip()
            if code and desc:
                mapping[code] = desc
    mapping.update(MANUAL_SECTION_MAPPING)
    return mapping


def build_mapped_df(df: pd.DataFrame, mapping: Dict[str, Optional[str]]) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for target_col, source_col in mapping.items():
        out[target_col] = df[source_col] if source_col in df.columns else None

    out["capacity"] = safe_number(out["capacity"])
    out["used_capacity"] = safe_number(out["used_capacity"])
    out["remaining_capacity"] = safe_number(out["remaining_capacity"])
    out["no_handling_units"] = safe_number(out["no_handling_units"])

    missing_capacity = out["capacity"] <= 0
    out.loc[missing_capacity, "capacity"] = out.loc[missing_capacity, "remaining_capacity"]
    if (out["used_capacity"] <= 0).all() and (out["capacity"] > 0).any():
        out["used_capacity"] = (out["capacity"] - out["remaining_capacity"]).clip(lower=0)

    out["bin_type"] = out.apply(derive_bin_type, axis=1)
    out["status"] = out.apply(derive_status, axis=1)
    if mapping.get("empty_indicator") is not None:
        out["is_empty"] = out["empty_indicator"].map(is_truthy)
    else:
        out["is_empty"] = out.apply(derive_is_empty, axis=1)
    out["occupancy_state"] = out["is_empty"].map({True: "Empty bins", False: "Occupied bins"})
    out["available_capacity"] = (out["capacity"] - out["used_capacity"]).clip(lower=0)

    for col in [
        "bin_id",
        "zone",
        "aisle",
        "stack",
        "level",
        "rack_bin_section",
        "rack_bin_depth",
        "disabled_reason",
    ]:
        out[col] = out[col].fillna("").astype(str).str.strip()

    out["zone"] = out["zone"].replace("", "UNASSIGNED")
    out["storage_section"] = out["storage_section"].fillna("").astype(str).str.strip().replace("", "UNASSIGNED")
    out["aisle"] = out["aisle"].replace("", "UNASSIGNED")
    out["stack"] = out["stack"].replace("", "UNASSIGNED")
    out["level"] = out["level"].replace("", "UNASSIGNED")
    out["rack_bin_section"] = out["rack_bin_section"].replace("", "UNASSIGNED")
    out["rack_bin_depth"] = out["rack_bin_depth"].replace("", "UNASSIGNED")
    out["bin_id"] = out["bin_id"].replace("", "NO_BIN_ID")
    out["storage_type_class"] = out["zone"].map(classify_storage_type)
    out["rack_location"] = (
        "Aisle " + out["aisle"] + " | Stack " + out["stack"] + " | Level " + out["level"]
    )
    out["rack_position"] = out["aisle"] + "-" + out["stack"]

    return out


def kpi_row(df: pd.DataFrame) -> None:
    total_bins = len(df)
    picking_bins = int((df["bin_type"] == "PICKING").sum())
    buffer_bins = int((df["bin_type"] == "BUFFER").sum())
    empty_bins = int((df["occupancy_state"] == "Empty bins").sum())
    occupied_bins = int((df["occupancy_state"] == "Occupied bins").sum())
    picking_empty = int(((df["bin_type"] == "PICKING") & (df["occupancy_state"] == "Empty bins")).sum())
    buffer_empty = int(((df["bin_type"] == "BUFFER") & (df["occupancy_state"] == "Empty bins")).sum())
    available_bins = int((df["status"] == "AVAILABLE").sum())
    disabled_bins = int((df["status"] == "DISABLED").sum())

    c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
    c1.metric("Total Bins", total_bins)
    c2.metric("Empty bins", empty_bins)
    c3.metric("Occupied bins", occupied_bins)
    c4.metric("Picking Bins", picking_bins)
    c5.metric("Picking Empty", picking_empty)
    c6.metric("Buffer Bins", buffer_bins)
    c7.metric("Buffer Empty", buffer_empty)
    c8.metric("Disabled", disabled_bins)
    st.caption(f"Available bins: {available_bins}")


def render_charts(df: pd.DataFrame) -> None:
    left, right = st.columns(2)

    with left:
        st.subheader("Allocation by Bin Type")
        by_type = (
            df.groupby("bin_type", as_index=False)
            .size()
            .rename(columns={"size": "count"})
            .sort_values("count", ascending=False)
        )
        fig_type = px.pie(by_type, names="bin_type", values="count", hole=0.35)
        st.plotly_chart(fig_type, use_container_width=True)

        st.subheader("Disabled Reasons")
        disabled = df[df["status"] == "DISABLED"]
        if disabled.empty:
            st.info("No disabled bins in current filter.")
        else:
            by_reason = (
                disabled.assign(disabled_reason=disabled["disabled_reason"].replace("", "NO_REASON"))
                .groupby("disabled_reason", as_index=False)
                .size()
                .rename(columns={"size": "count"})
                .sort_values("count", ascending=False)
            )
            fig_reason = px.bar(by_reason, x="disabled_reason", y="count")
            st.plotly_chart(fig_reason, use_container_width=True)

        st.subheader("Empty bins vs Occupied bins by Bin Type")
        by_type_occ = (
            df.groupby(["bin_type", "occupancy_state"], as_index=False)
            .size()
            .rename(columns={"size": "count"})
        )
        fig_occ = px.bar(
            by_type_occ,
            x="bin_type",
            y="count",
            color="occupancy_state",
            barmode="stack",
            color_discrete_map={"Empty bins": "#2ca02c", "Occupied bins": "#d62728"},
        )
        st.plotly_chart(fig_occ, use_container_width=True)

    with right:
        st.subheader("Status by Zone")
        by_zone = (
            df.groupby(["zone", "status"], as_index=False)
            .size()
            .rename(columns={"size": "count"})
        )
        fig_zone = px.bar(
            by_zone,
            x="zone",
            y="count",
            color="status",
            barmode="stack",
            color_discrete_map=COLOR_MAP,
        )
        st.plotly_chart(fig_zone, use_container_width=True)

        st.subheader("Bins per Storage Section (Empty bins vs Occupied bins)")
        by_section = (
            df.groupby(["storage_section", "storage_section_desc", "occupancy_state"], as_index=False)
            .size()
            .rename(columns={"size": "count"})
        )
        by_section["section_label"] = by_section["storage_section"] + " - " + by_section["storage_section_desc"]
        section_order = (
            by_section.groupby("section_label", as_index=False)["count"].sum().sort_values("count", ascending=False)
        )
        fig_section = px.bar(
            by_section,
            x="section_label",
            y="count",
            color="occupancy_state",
            barmode="stack",
            category_orders={"section_label": section_order["section_label"].tolist()},
            color_discrete_map={"Empty bins": "#2ca02c", "Occupied bins": "#d62728"},
        )
        st.plotly_chart(fig_section, use_container_width=True)

        if (df["capacity"] > 0).any():
            st.subheader("Capacity Utilization by Bin Type")
            cap = (
                df.groupby("bin_type", as_index=False)[["capacity", "used_capacity"]]
                .sum()
                .assign(utilization_pct=lambda x: (x["used_capacity"] / x["capacity"].replace(0, pd.NA) * 100).fillna(0))
            )
            fig_util = px.bar(cap, x="bin_type", y="utilization_pct", range_y=[0, 100])
            fig_util.update_layout(yaxis_title="Utilization %")
            st.plotly_chart(fig_util, use_container_width=True)


def render_section_summary(df: pd.DataFrame) -> None:
    st.subheader("Storage Section Summary")
    summary = (
        df.groupby(["storage_section", "storage_section_desc"], as_index=False)
        .agg(
            total_bins=("bin_id", "count"),
            empty_bins=("is_empty", "sum"),
            picking_bins=("bin_type", lambda s: int((s == "PICKING").sum())),
            buffer_bins=("bin_type", lambda s: int((s == "BUFFER").sum())),
        )
        .sort_values("total_bins", ascending=False)
    )
    summary["occupied_bins"] = summary["total_bins"] - summary["empty_bins"]
    summary["section_label"] = summary["storage_section"] + " - " + summary["storage_section_desc"]
    st.dataframe(
        summary[
            [
                "section_label",
                "total_bins",
                "empty_bins",
                "occupied_bins",
                "picking_bins",
                "buffer_bins",
            ]
        ],
        use_container_width=True,
    )


def render_bin_map(df: pd.DataFrame) -> None:
    st.subheader("Bin Map")
    st.caption(
        "Aggregated visual map by Storage Section and Level. Color shows occupancy and bubble size shows bin count."
    )

    map_df = df.copy()
    map_df["section_label"] = map_df["storage_section"] + " - " + map_df["storage_section_desc"]
    section_order = (
        map_df.groupby("section_label", as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("count", ascending=False)["section_label"]
        .tolist()
    )
    grouped = (
        map_df.groupby(["section_label", "level", "occupancy_state"], as_index=False)
        .size()
        .rename(columns={"size": "bin_count"})
    )

    fig = px.scatter(
        grouped,
        x="section_label",
        y="level",
        size="bin_count",
        color="occupancy_state",
        category_orders={"section_label": section_order},
        color_discrete_map={"Empty bins": "#2ca02c", "Occupied bins": "#d62728"},
        hover_data=[
            "occupancy_state",
            "bin_count",
        ],
        title="Visual Allocation Map (Section and Level)",
    )
    fig.update_traces(marker={"opacity": 0.85, "line": {"width": 1, "color": "#1f2937"}})
    fig.update_xaxes(title="Storage Section")
    fig.update_yaxes(title="Level")
    st.plotly_chart(fig, use_container_width=True)


@st.cache_data(show_spinner=False)
def load_data(file) -> pd.DataFrame:
    name = (getattr(file, "name", "") or "").lower()
    if name.endswith(".csv"):
        df = pd.read_csv(file, sep=None, engine="python", encoding="utf-8-sig", dtype=str)
        if len(df.columns) == 1 and ";" in df.columns[0]:
            file.seek(0)
            df = pd.read_csv(file, sep=";", encoding="utf-8-sig", dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        return df.dropna(how="all")
    return pd.read_excel(file)


def main() -> None:
    st.title("Warehouse Bin Allocation Visualizer")
    st.write(
        "Upload an Excel file and explore picking/buffer allocation, availability, disabled bins, and capacity utilization."
    )

    st.sidebar.header("Data Source")
    source_mode = st.sidebar.radio("Select source", ["Upload file", "Restore by ID"])

    if source_mode == "Restore by ID":
        requested_id = st.sidebar.text_input("Processed ID", placeholder="BIN-1234ABCD...")
        if not requested_id.strip():
            st.info("Enter a processed ID in the sidebar to restore a previous run.")
            return
        processed_id = normalize_processed_id(requested_id)
        df = load_processed_df(processed_id)
        if df is None:
            st.error(f"No saved processed dataset found for ID: {processed_id}")
            return
        st.sidebar.success("Processed dataset restored.")
        st.sidebar.code(processed_id)
    else:
        uploaded_file = st.file_uploader("Upload file", type=["xlsx", "xls", "csv"])
        if not uploaded_file:
            st.info("Upload a file to begin.")
            return

        try:
            raw_df = load_data(uploaded_file)
        except BadZipFile:
            st.error(
                "The uploaded Excel file appears corrupted/incomplete. "
                "Please re-export it or save it again in Excel, or upload CSV."
            )
            return
        except Exception as exc:
            st.error(f"Could not parse file: {exc}")
            return
        if raw_df.empty:
            st.error("The uploaded file is empty.")
            return

        st.sidebar.header("Column Mapping")
        columns = list(raw_df.columns)

        mapping = {}
        for key, candidates in DEFAULT_MAPPING.items():
            default_name = find_best_default(columns, candidates)
            mapping[key] = choose_column(f"{key}", columns, default_name)

        required = ["bin_id", "aisle", "level", "zone", "storage_section"]
        missing_required = [k for k in required if mapping.get(k) is None]
        if missing_required:
            st.error(f"Missing required column mappings: {', '.join(missing_required)}")
            st.stop()

        df = build_mapped_df(raw_df, mapping)
        section_mapping = load_section_mapping(DEFAULT_CODES_PDF)
        df["storage_section_desc"] = df["storage_section"].map(section_mapping).fillna("UNMAPPED")
        processed_id = generate_processed_id(df)
        saved_path = persist_processed_df(df, processed_id, getattr(uploaded_file, "name", "uploaded_file"))

        st.sidebar.header("Processed Dataset")
        st.sidebar.code(processed_id)
        st.sidebar.caption(f"Saved as {saved_path.name}")

    st.sidebar.header("Filters")
    zones = ["ALL"] + sorted(df["zone"].unique().tolist())
    aisles = ["ALL"] + sorted(df["aisle"].unique().tolist())
    levels = ["ALL"] + sorted(df["level"].unique().tolist())
    sections = ["ALL"] + sorted(df["storage_section"].unique().tolist())

    type_filter = st.sidebar.selectbox(
        "Storage Type Group",
        ["ALL", "PICKING (RHP*)", "BUFFER (RHB*)", "OTHER"],
    )

    selected_zone = st.sidebar.selectbox("Zone", zones)
    selected_section = st.sidebar.selectbox("Storage Section", sections)
    selected_aisle = st.sidebar.selectbox("Aisle", aisles)
    selected_level = st.sidebar.selectbox("Level", levels)

    filtered = df.copy()
    if type_filter == "PICKING (RHP*)":
        filtered = filtered[filtered["storage_type_class"] == "PICKING"]
    elif type_filter == "BUFFER (RHB*)":
        filtered = filtered[filtered["storage_type_class"] == "BUFFER"]
    elif type_filter == "OTHER":
        filtered = filtered[filtered["storage_type_class"] == "OTHER"]
    if selected_zone != "ALL":
        filtered = filtered[filtered["zone"] == selected_zone]
    if selected_section != "ALL":
        filtered = filtered[filtered["storage_section"] == selected_section]
    if selected_aisle != "ALL":
        filtered = filtered[filtered["aisle"] == selected_aisle]
    if selected_level != "ALL":
        filtered = filtered[filtered["level"] == selected_level]

    if filtered.empty:
        st.warning("No rows match the current filters.")
        return

    kpi_row(filtered)
    render_charts(filtered)
    render_section_summary(filtered)
    render_bin_map(filtered)

    st.subheader("Data Table")
    st.dataframe(filtered, use_container_width=True)

    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered data as CSV",
        data=csv,
        file_name=f"filtered_bins_{processed_id}.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
