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

def get_value_from_json_obj(obj):
    """Extract value from JSON object or return the object itself if it's not a dict"""
    if isinstance(obj, dict) and 'value' in obj:
        return obj['value']
    return obj

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
    # fallback: 1st unit gets all beds
    if total_beds and num_units>1:
        beds = [total_beds] + [None]*(num_units-1)
        return beds[:4] + [None]*(4-len(beds[:4]))
    # fallback for single unit
    if total_beds and num_units==1:
        return [total_beds, None, None, None]
    return [None, None, None, None]

def extract_tax_info(item):
    """Extract tax information from the item"""
    tax_info = {}
    
    # Try to find tax information in the facts
    facts = item.get("facts", [])
    for fact_group in facts:
        for fact in fact_group.get("facts", []):
            name = fact.get("factName", "").lower()
            value = fact.get("factValue")
            
            if "tax" in name and "year" not in name.lower():
                tax_info["taxes"] = parse_dollar_amount(value)
            elif "assessed value" in name.lower() or "land value" in name.lower():
                tax_info["land_assessment"] = parse_dollar_amount(value)
            elif "improvement value" in name.lower() or "building value" in name.lower():
                tax_info["additions_assessment"] = parse_dollar_amount(value)
    
    # Also check the taxInfo object if it exists
    tax_obj = item.get("taxInfo", {})
    if not tax_info.get("taxes") and tax_obj.get("taxesDue"):
        tax_info["taxes"] = tax_obj.get("taxesDue")
    if not tax_info.get("land_assessment") and tax_obj.get("landAssessedValue"):
        tax_info["land_assessment"] = tax_obj.get("landAssessedValue")
    if not tax_info.get("additions_assessment") and tax_obj.get("additionsAssessedValue"):
        tax_info["additions_assessment"] = tax_obj.get("additionsAssessedValue")
        
    return tax_info

def parse_dollar_amount(text):
    """Parse a dollar amount from text like '$1,234' to a number"""
    if not text:
        return None
    if isinstance(text, (int, float)):
        return text
    if isinstance(text, str):
        text = text.replace('$', '').replace(',', '')
        try:
            return float(text)
        except ValueError:
            pass
    return None

def build_record(item):
    rec = {}
    # basic listing info
    rec["address"]         = combine_address(item)
    rec["zip_code"]        = item.get("zip")
    rec["area"]            = None  # Yellow column
    rec["days_on_market"]  = get_value_from_json_obj(item.get("dom"))
    rec["listing_summary"] = item.get("listingRemarks")
    rec["url"]             = item.get("url")
    rec["asking_price"]    = get_value_from_json_obj(item.get("price"))
    
    # features
    rec["beds"]            = item.get("beds")
    rec["baths"]           = item.get("baths")
    rec["square_feet"]     = get_value_from_json_obj(item.get("sqFt"))
    rec["year_built"]      = get_value_from_json_obj(item.get("yearBuilt"))
    rec["parking"]         = find_parking(item)
    rec["property_type"]   = map_property_type(item.get("uiPropertyType"))
    
    # Yellow column
    rec["stories"]         = None
    
    # Unit information
    num_units              = infer_num_units(item)
    rec["num_units"]       = num_units
    
    # Yellow column 
    rec["rent_to_own"]     = None
    
    # unit bed columns
    unit_beds = infer_unit_beds(item, num_units, rec["beds"])
    rec["unit_1_beds"], rec["unit_2_beds"], rec["unit_3_beds"], rec["unit_4_beds"] = unit_beds
    
    # Yellow column - skip a space at the end of "Ratio SF per Bed"
    rec["ratio_sf_per_bed"] = None
    
    # Yellow columns - financials
    rec["rent_unit_1"]      = None
    rec["rent_unit_2"]      = None
    rec["rent_unit_3"]      = None
    rec["rent_unit_4"]      = None
    rec["other_revenue"]    = None
    
    # Regular columns
    rec["total_monthly_revenue"] = None
    
    # Get tax info
    tax_info = extract_tax_info(item)
    rec["taxes"] = tax_info.get("taxes")
    rec["land_assessment"] = tax_info.get("land_assessment")
    rec["additions_assessment"] = tax_info.get("additions_assessment")
    
    # More yellow columns
    rec["insurance"]        = None
    rec["maintenance"]      = None
    rec["vacancy"]          = None
    rec["management"]       = None
    rec["misc_exp"]         = None
    rec["util_cost"]        = None
    rec["electric"]         = None
    rec["lawn"]             = None
    rec["total_expenses"]   = None
    rec["ratio"]            = None
    rec["financing"]        = None
    rec["asking_price_1"]   = None
    rec["condition"]        = None
    rec["weight_market_1"]  = None
    rec["asking_price_2"]   = None
    rec["condition_2"]      = None
    rec["weight_market_2"]  = None
    rec["asking_price_3"]   = None
    rec["condition_3"]      = None
    
    return rec

# ------------------ MAIN -----------------
records=[]
for path in glob.glob(INPUT_PATTERN):
    with open(path,'r') as f:
        data=json.load(f)
    for itm in data:
        records.append(build_record(itm))

# column order explicit - matching exactly what's in the spreadsheet
base_cols = [
    "address", "zip_code", "area", "days_on_market",
    "listing_summary", "url", "asking_price",
    "beds", "baths", "square_feet", "year_built", "parking",
    "property_type", "stories", 
    "num_units", "rent_to_own", "unit_1_beds", "unit_2_beds", "unit_3_beds", "unit_4_beds",
    "ratio_sf_per_bed", "rent_unit_1", "rent_unit_2", "rent_unit_3", "rent_unit_4", "other_revenue",
    "total_monthly_revenue", "taxes", "land_assessment", "additions_assessment",
    "insurance", "maintenance", "vacancy", "management", "misc_exp", 
    "util_cost", "electric", "lawn", "total_expenses", "ratio", 
    "financing", "asking_price_1", "condition", "weight_market_1",
    "asking_price_2", "condition_2", "weight_market_2", 
    "asking_price_3", "condition_3"
]

df = pd.DataFrame(records, columns=base_cols)

# Ensure output directory exists
os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

# save CSV
df.to_csv(OUTPUT_CSV, index=False)
print(f"CSV file saved to {OUTPUT_CSV}")
print(f"Processed {len(records)} listings")
