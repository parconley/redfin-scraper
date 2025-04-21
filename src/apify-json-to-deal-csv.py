import json, re, glob, os, pandas as pd

# ------------------ CONFIG -----------------
# Using relative paths based on project structure
INPUT_PATTERN = '../data/raw/dataset_redfin-search_*.json'
OUTPUT_CSV    = '../data/processed/quick_deal_import.csv'

# titles for blank spreadsheet‑calculation columns
CALC_COLS = [
    "ratio_sf_per_bed",
    "rent_unit_1", "rent_unit_2", "rent_unit_3", "rent_unit_4",
    "other_revenue",
    "insurance"
]

PROPERTY_TYPE_MAP = {
    1: "Single-family",
    3: "Townhouse/Row",
    4: "Multi-family",
    5: "Vacant Land",
    6: "Single-family",   # Redfin propertyType 6 seems SF?
    13: "Duplex/Triplex"
}

# ------------------ HELPERS -----------------
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

# unit inference regex
RE_UNITS_PHRASE = re.compile(r'(\d+)\s+(?:unit|plex)', re.I)
RE_PER_UNIT_BEDS = re.compile(r'(\d+)\s+bedroom[s]?\s+(?:and\s+\d+\s+bathroom[s]?\s+)?(?:in\s+)?each\s+unit', re.I)

def infer_num_units(item):
    ui = item.get("uiPropertyType")
    if ui == 4 or ui == 13:   # Redfin multi-family listing page type
        # attempt to parse remarks
        txt = (item.get("listingRemarks") or "")
        m = RE_UNITS_PHRASE.search(txt)
        if m:
            return int(m.group(1))
        if "triplex" in txt.lower(): return 3
        if "quad" in txt.lower():    return 4
        if "duplex" in txt.lower():  return 2
        return 2  # default for multi listing
    return 1

def infer_unit_beds(item, num_units, total_beds):
    # attempt explicit phrase: "3 bedrooms ... each unit"
    txt = item.get("listingRemarks","")
    m = RE_PER_UNIT_BEDS.search(txt)
    if m:
        per = int(m.group(1))
        beds = [per]*num_units
        return beds[:4] + [None]*(4-len(beds[:4]))
    # fallback: evenly divisible
    if total_beds and num_units>1 and total_beds % num_units == 0:
        per = total_beds//num_units
        beds = [per]*num_units
        return beds[:4] + [None]*(4-len(beds[:4]))
    # else unknown
    return [None,None,None,None]

def build_record(item):
    rec = {}
    rec["address"]         = combine_address(item)
    rec["zip_code"]        = item.get("zip")
    rec["days_on_market"]  = (item.get("dom") or {}).get("value")
    rec["listing_summary"] = item.get("listingRemarks")
    rec["url"]             = item.get("url")
    rec["asking_price"]    = (item.get("price") or {}).get("value")
    rec["beds"]            = item.get("beds")
    rec["baths"]           = item.get("baths")
    rec["square_feet"]     = (item.get("sqFt") or {}).get("value")
    rec["year_built"]      = (item.get("yearBuilt") or {}).get("value")
    rec["parking"]         = find_parking(item)
    rec["property_type"]   = map_property_type(item.get("uiPropertyType"))
    num_units              = infer_num_units(item)
    rec["num_units"]       = num_units

    # unit bed columns
    unit_beds = infer_unit_beds(item, num_units, rec["beds"])
    rec["unit_1_beds"], rec["unit_2_beds"], rec["unit_3_beds"], rec["unit_4_beds"] = unit_beds

    # blank calc / later‑lookup columns
    rec["total_monthly_revenue"] = None
    rec["taxes"]                 = None
    rec["land_assessment"]       = None
    rec["additions_assessment"]  = None
    # add empty calc cols
    for c in CALC_COLS:
        rec[c] = None
    return rec

# ------------------ MAIN -----------------
records=[]
for path in glob.glob(INPUT_PATTERN):
    with open(path,'r') as f:
        data=json.load(f)
    for itm in data:
        records.append(build_record(itm))

# column order explicit
base_cols = [
    "address","zip_code","days_on_market","listing_summary","url",
    "asking_price","beds","baths","square_feet","year_built","parking",
    "property_type","num_units",
    "unit_1_beds","unit_2_beds","unit_3_beds","unit_4_beds",
    "ratio_sf_per_bed",  # insert calc before revenue group for easier mapping
    "rent_unit_1","rent_unit_2","rent_unit_3","rent_unit_4","other_revenue",
    "total_monthly_revenue","taxes","land_assessment","additions_assessment",
    "insurance"
]
df = pd.DataFrame(records, columns=base_cols)

# Ensure output directory exists
os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

# save CSV
df.to_csv(OUTPUT_CSV,index=False)
print(f"CSV file saved to {OUTPUT_CSV}")
print(f"Processed {len(records)} listings")
