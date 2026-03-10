# Bin Allocation Visualizer

Python app to process an Excel/CSV file with warehouse bin locations and visualize:
- Picking vs buffer bin allocation
- Availability and occupancy
- Disabled bins and reason codes
- Interactive charts and location map

## 1) Setup

```bash
cd /Users/fibunix/development/hm/bin_allocation_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Run

```bash
streamlit run app.py
```

Accepted upload types: `.xlsx`, `.xls`, `.csv`.
For CSV, delimiter auto-detection is enabled (works with `;` SAP exports).

## 3) Excel Columns

Default expected columns (you can remap in the sidebar):
- `bin_id`
- `zone`
- `aisle`
- `level`
- `bin_type` (values like `PICKING`, `BUFFER`)
- `status` (values like `AVAILABLE`, `OCCUPIED`, `DISABLED`)
- `disabled_reason` (optional)
- `capacity` (optional numeric)
- `used_capacity` (optional numeric)

If `capacity` and `used_capacity` are present, utilization metrics are shown.

## SAP EWM Export Support

The app now auto-maps common SAP export columns such as:
- `Storage Bin` -> bin id
- `Storage Type` / `Storage Section` -> zone
- `Aisle` -> aisle
- `Level` -> level
- `Storage Bin Type` -> bin type
- `Total Capacity` + `Remaining Capacity` -> capacity/used capacity
- `Empty Indicator` / `Full Indicator` / `Stock Removal Block` / `Putaway Block` / `User Status` -> derived availability/disabled status
- `Storage Type` prefix `RHP*` -> picking, `RHB*` -> buffer (for totals and filtering)
- `Empty Indicator` (`X`) -> empty bin, blank -> not empty bin

Storage section descriptions are automatically loaded from:
- `/Users/fibunix/Library/Containers/net.whatsapp.WhatsApp/Data/tmp/documents/2CDF3076-C85B-429C-9179-A249109FBBBC/--codes.pdf`

Dashboard includes:
- Total empty and not-empty bins
- Empty/not-empty split for picking and buffer
- Total bins per storage section (mapped to code descriptions)

You can still override any mapping in the sidebar.
