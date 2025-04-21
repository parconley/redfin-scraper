import json, re, glob, os, pandas as pd, textwrap

# ---------- helper functions ----------
def combine_address(item):
    parts = []
    sl = item.get('streetLine', {})
    if isinstance(sl, dict):
        sl = sl.get('value')
    if sl: parts.append(sl)
    city = item.get('city')
    state = item.get('state')
    zipc = item.get('zip')
    if city: parts.append(city)
    if state: parts.append(state)
    if zipc: parts.append(zipc)
    return ", ".join(parts)

PROPERTY_TYPE_MAP = {
    1: "Single-family",
    3: "Townhouse/Row",
    4: "Multi-family",
    6: "Single-family",   # Redfin propertyType 6 seems SF?
    13: "Duplex/Triplex"
}

def map_property_type(ui_code):
    return PROPERTY_TYPE_MAP.get(ui_code, str(ui_code))

def find_parking(item):
    facts = item.get("keyFacts", [])
    for f in facts:
        desc = f.get("description", "").lower()
        if "garage" in desc:
            return "Garage"
        if "carport" in desc:
            return "Carport"
        if "on street" in desc or "street" in desc:
            return "On Street"
    # fallback heuristic in remarks
    remarks = item.get("listingRemarks", "") or ""
    if "garage" in remarks.lower():
        return "Garage (from remarks)"
    return ""

_UNIT_RE = re.compile(r'\b(\d+)\s*-?\s*(unit|plex)\b', re.I)
_DUPLEX_RE = re.compile(r'\bduplex\b', re.I)
_TRIPLEX_RE = re.compile(r'\btriplex\b', re.I)
_QUAD_RE = re.compile(r'\bquadplex|fourplex|quadruplex\b', re.I)

def infer_num_units(item):
    ui = item.get("uiPropertyType")
    if ui == 4:   # Redfin multi-family listing page type
        # attempt to parse remarks
        txt = (item.get("listingRemarks") or "")
        m = _UNIT_RE.search(txt)
        if m:
            return int(m.group(1))
        if _TRIPLEX_RE.search(txt):
            return 3
        if _QUAD_RE.search(txt):
            return 4
        if _DUPLEX_RE.search(txt):
            return 2
        return 2  # default for multi listing
    return 1

def build_record(item):
    rec = {}
    rec["address"] = combine_address(item)
    rec["zip_code"] = item.get("zip")
    rec["days_on_market"] = (item.get("dom") or {}).get("value")
    rec["listing_summary"] = item.get("listingRemarks")
    rec["url"] = item.get("url")
    rec["asking_price"] = (item.get("price") or {}).get("value")
    rec["beds"] = item.get("beds")
    rec["baths"] = item.get("baths")
    rec["square_feet"] = (item.get("sqFt") or {}).get("value")
    rec["year_built"] = (item.get("yearBuilt") or {}).get("value")
    rec["parking"] = find_parking(item)
    rec["property_type"] = map_property_type(item.get("uiPropertyType"))
    rec["num_units"] = infer_num_units(item)

    # unit beds
    rec["unit_1_beds"] = rec["beds"] if rec["num_units"] == 1 else None
    rec["unit_2_beds"] = None
    rec["unit_3_beds"] = None
    rec["unit_4_beds"] = None

    rec["total_monthly_revenue"] = None
    rec["taxes"] = None
    rec["land_assessment"] = None
    rec["additions_assessment"] = None
    return rec

# ---------- main processing ----------
input_files = glob.glob('./dataset_redfin-search_*.json')
records = []
for fpath in input_files:
    with open(fpath, 'r') as f:
        data = json.load(f)
        for item in data:
            records.append(build_record(item))

# DataFrame
col_order = [
    "address","zip_code","days_on_market","listing_summary","url",
    "asking_price","beds","baths","square_feet","year_built","parking",
    "property_type","num_units",
    "unit_1_beds","unit_2_beds","unit_3_beds","unit_4_beds",
    "total_monthly_revenue","taxes","land_assessment","additions_assessment"
]
df = pd.DataFrame(records, columns=col_order)

# save CSV
csv_path = './quick_deal_import.csv'
df.to_csv(csv_path, index=False)