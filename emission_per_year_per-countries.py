
# make_world_maps_per_capita.py
# Cartes monde CO₂ par habitant (per capita) pour plusieurs années
# Compatible Python 3.12 (nécessite: pygal, pygal_maps_world)

import csv, re
from pathlib import Path
from collections import defaultdict

from pygal_maps_world.maps import World
from pygal_maps_world.i18n import COUNTRIES

CSV_PATH = Path("co-emissions-per-capita.csv")  # <-- ton fichier
OUT_DIR  = Path("maps_out_percap")
OUT_DIR.mkdir(exist_ok=True)

# ======= PARAMÈTRES =======
# 1) Liste d'années à générer :
YEARS = [1990, 2000, 2010, 2020, 2023]
# 2) OU bien, mets AUTO_LAST_N à un entier (ex. 15) pour générer les N dernières années :
AUTO_LAST_N = None
# Nombre minimal de pays exigé pour produire la carte d'une année :
MIN_COUNTRIES_PER_YEAR = 60
# ==========================

def norm(d): return {(k or "").strip().lower(): v for k, v in d.items()}
def looks_num(x: str) -> bool:
    try:
        float((x or "").replace(" ", "").replace(",", ""))
        return True
    except:
        return False

# Écarter les agrégats / régions / groupes
AGG_PATTERNS = [
    r"\bworld\b", r"\binternational\b", r"\beurope\b", r"\beu\b", r"\beu-?\d+\b",
    r"\bafrica\b", r"\basia\b", r"\boceania\b",
    r"\bnorth america\b", r"\bsouth america\b",
    r"\b(excl\.)\b", r"\(excl", r"\ball income\b", r"\bupper|lower middle\b",
    r"\bhigh income\b", r"\blow income\b", r"\bglobal\b", r"\bunion\b"
]
agg_re = re.compile("|".join(AGG_PATTERNS), re.I)

# Alias de pays fréquents
ALIASES = {
    "united states":"us","united states of america":"us","russia":"ru","russian federation":"ru",
    "south korea":"kr","north korea":"kp","iran":"ir","czech republic":"cz","viet nam":"vn","laos":"la",
    "bolivia":"bo","brunei":"bn","syria":"sy","eswatini":"sz","ivory coast":"ci","côte d’ivoire":"ci","cote d'ivoire":"ci",
    "myanmar (burma)":"mm","cape verde":"cv","north macedonia":"mk","palestine":"ps","moldova":"md",
    "timor-leste":"tl","east timor":"tl","uk":"gb","united kingdom":"gb","tanzania":"tz",
    "são tomé and príncipe":"st","sao tome and principe":"st","hong kong":"hk","macau":"mo","cabo verde":"cv",
    "democratic republic of congo":"cd","congo (kinshasa)":"cd","congo (brazzaville)":"cg"
}
NAME_TO_CODE = {v.lower(): k for k, v in COUNTRIES.items()}

def to_code(name: str):
    key = (name or "").lower().strip()
    if agg_re.search(key): return None
    if key in ALIASES: return ALIASES[key]
    if key in NAME_TO_CODE: return NAME_TO_CODE[key]
    key2 = key.replace("’", "'").replace("&", "and")
    if key2 in NAME_TO_CODE: return NAME_TO_CODE[key2]
    key3 = re.sub(r"\s*\(.*?\)\s*", "", key2).strip()
    return NAME_TO_CODE.get(key3)

# --- Lecture du CSV
rows = []
with CSV_PATH.open("r", encoding="utf-8") as f:
    rd = csv.DictReader(f)
    for r in rd:
        rows.append(norm(r))
if not rows:
    raise SystemExit("CSV vide ou illisible.")

keys = rows[0].keys()

# Colonne année
col_year = "year" if "year" in keys else next((k for k in keys if re.fullmatch(r"year|annee|année", k)), None)
if not col_year:
    raise SystemExit("Colonne 'year' introuvable.")

# Colonne pays (on prend la 1re dispo)
col_country = next((c for c in ["country","entity","region","area","name","location"] if c in keys), None)
if not col_country:
    col_country = next((k for k in keys if not k.isnumeric()), None)
    if not col_country:
        raise SystemExit("Colonne pays introuvable.")

# Colonnes candidates pour **per capita**
# priorité aux noms contenant 'per' et 'capita' et 'co2/co₂'
def percap_priority(colname: str) -> int:
    n = colname.lower()
    score = 0
    if "co2" in n or "co₂" in n: score += 2
    if "per" in n and "capita" in n: score += 3
    if "pc" in n: score += 1
    if "kg" in n: score -= 1   # si kg, c’est souvent pas la principale
    if "share" in n or "intensity" in n or "percent" in n: score -= 5
    return score

value_cols = sorted(keys, key=percap_priority, reverse=True)
# Nettoyage: on enlève année/pays
value_cols = [c for c in value_cols if c not in (col_year, col_country)]

# Construire {année: {code_iso2: valeur}}
by_year = defaultdict(dict)
for r in rows:
    # année
    try: y = int(float(r.get(col_year, "")))
    except: continue

    # pays -> code
    name = r.get(col_country) or ""
    code = to_code(name)
    if not code:
        continue

    # choisir une valeur "per capita"
    val = None
    for col in value_cols:
        raw = (r.get(col) or "").replace(" ", "").replace(",", "")
        # on n’accepte cette colonne que si son nom a un score positif (vraie per-capita)
        if percap_priority(col) <= 0:
            continue
        if looks_num(raw):
            val = float(raw)
            break
    if val is None:
        continue

    by_year[y][code] = val

available_years = sorted(by_year.keys())
if not available_years:
    raise SystemExit("Aucune année exploitable (aucune valeur per capita trouvée).")

# Sélection des années à générer
if AUTO_LAST_N:
    target_years = sorted(available_years, reverse=True)[:AUTO_LAST_N]
else:
    target_years = [y for y in YEARS if y in by_year]
if not target_years:
    target_years = sorted(available_years, reverse=True)[:10]  # fallback: 10 dernières

generated = []
for y in sorted(target_years):
    data = by_year[y]
    if len(data) < MIN_COUNTRIES_PER_YEAR:
        print(f"Skip {y}: seulement {len(data)} pays mappés (<{MIN_COUNTRIES_PER_YEAR}).")
        continue
    chart = World()
    chart.title = f"CO₂ par habitant (t/hab) — {y}"
    chart.add("tCO₂/hab", data)
    out_svg = OUT_DIR / f"world_percap_{y}.svg"
    chart.render_to_file(str(out_svg))
    generated.append(out_svg.name)
    print(f"OK -> {out_svg} ({len(data)} pays)")

# Index HTML pratique
if generated:
    html = ["<html><head><meta charset='utf-8'><title>CO₂ per capita maps</title></head><body>",
            "<h1>Cartes CO₂ par habitant</h1>"]
    for fname in generated:
        html += [f"<h2>{fname.replace('world_percap_','').replace('.svg','')}</h2>",
                 f"<object type='image/svg+xml' data='{fname}' width='100%'></object><hr/>"]
    html.append("</body></html>")
    (OUT_DIR / "index.html").write_text("\n".join(html), encoding="utf-8")
    print(f"\nIndex: {OUT_DIR / 'index.html'}")
else:
    print("Aucune carte générée (augmente MIN_COUNTRIES_PER_YEAR ou ajuste YEARS/AUTO_LAST_N).")
