"""World Rowing's member federations: the data the quiz asks about.

data/federations.json and data/blades/*.png come from World Rowing's
"158 Member Federations" poster (extract_pdf.py). Continents and the extra
names people use are kept here by hand.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data" / "federations.json"
BLADES = ROOT / "data" / "blades"

# World Rowing's continental confederations.
CONTINENTS = {
    "Africa": """ALG ANG BEN BOT BUR CIV CMR CPV DJI EGY GHA GUI KEN LBA LES MAD MAR MAW MLI MOZ
                 MRI MTN NAM NGR NIG RSA SEN SLE SOM SUD SWZ TOG TUN UGA ZAM ZIM""",
    "Americas": """ARG BAR BER BOL BRA CAN CAY CHI COL CRC CUB DMA DOM ECU ESA GUA HAI HON JAM MEX
                   NCA PAN PAR PER PUR TTO URU USA VEN VIN""",
    "Asia": """AFG BAN BRN CAM CHN HKG INA IND IRI IRQ JOR JPN KAZ KGZ KOR KSA KUW LBN MAS MDV MGL
               MYA NEP PAK PHI PLE PRK QAT SGP SRI SYR THA TKM TPE UAE UZB VIE""",
    "Europe": """ALB ARM AUT AZE BEL BIH BLR BUL CRO CYP CZE DEN ESP EST FIN FRA GBR GEO GER GIB GRE
                 HUN IRL ISL ISR ITA LAT LTU LUX MDA MKD MLT MON NED NOR POL POR ROU RUS SLO SRB SUI
                 SVK SWE TUR UKR""",
    "Oceania": "ASA AUS FIJ KIR NZL PNG SAM TGA VAN",
}
CONTINENT_OF = {code: name for name, codes in CONTINENTS.items() for code in codes.split()}

# Other names (and old codes) that should count as right.
ALIASES = {
    "NED": ["Holland", "The Netherlands", "Nederland"],
    "GBR": ["GB", "Britain", "UK", "United Kingdom"],
    "USA": ["US", "America"],
    "GER": ["Deutschland"],
    "SUI": ["Schweiz", "Suisse", "Svizzera"],
    "AUT": ["Österreich"],
    "BEL": ["België", "Belgique"],
    "DEN": ["Danmark"],
    "ESP": ["España"],
    "ITA": ["Italia"],
    "NOR": ["Norge"],
    "SWE": ["Sverige"],
    "FIN": ["Suomi"],
    "POL": ["Polska"],
    "GRE": ["Hellas"],
    "CRO": ["Hrvatska"],
    "CZE": ["Czech"],
    "TUR": ["Türkiye"],
    "KOR": ["Korea"],
    "PRK": ["DPRK", "Democratic People's Republic of Korea"],
    "TPE": ["Taiwan"],
    "HKG": ["Hong Kong"],
    "MKD": ["Macedonia", "North Macedonia"],
    "SWZ": ["Swaziland"],
    "CIV": ["Côte d'Ivoire"],
    "CPV": ["Cabo Verde"],
    "BIH": ["Bosnia"],
    "VIN": ["Saint Vincent", "St Vincent"],
    "TTO": ["Trinidad"],
    "UAE": ["Emirates"],
    "NZL": ["NZ", "Aotearoa"],
    "MYA": ["Burma"],
    "RUS": ["Russian Federation"],
    "KSA": ["Saudi"],
    "ROU": ["ROM"],  # OarSpotter-era codes
    "VEN": ["VNE"],
    "MDA": ["MLD"],
    "LBN": ["LIB"],
    "SGP": ["SIN"],
}


def load():
    """All federations in poster order, with a stable numeric id per code."""
    feds = json.loads(DATA.read_text())
    missing = [f["code"] for f in feds if f["code"] not in CONTINENT_OF]
    if missing:
        raise SystemExit(f"No continent for {missing}: add them to CONTINENTS in federations.py")
    for i, f in enumerate(sorted(feds, key=lambda f: f["code"]), start=1):
        f["id"] = i
        f["continent"] = CONTINENT_OF[f["code"]]
        f["aliases"] = ALIASES.get(f["code"], [])
        f["image"] = BLADES / f"{f['code']}.png"
    return sorted(feds, key=lambda f: f["id"])
