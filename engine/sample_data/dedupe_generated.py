"""
sample_data/dedupe_generated.py

The AI generator (generate_ai.py) recycled its batches, so the "clean" CSVs
contained unintended repeats, e.g. 20 x "Apex Systems Ltd", 35 x "Priya Sharma",
23 x "12 Bishopsgate". Those muddy the entity-resolution exercise because they
are not in the defect answer key.

This step keeps the FIRST occurrence of each company brand / person name /
street address and gives every later repeat a distinct, realistic identity:

  Accounts  : repeated brand (first two words of the name) -> new company name
              that fits the Industry; About/Note text and Website follow suit;
              the account's office address email moves to the new domain.
  Person    : repeated First_Name + Last_Name -> new name from the same
              cultural group and gender as the original first name.
  Addresses : repeated Address_line1 + ZipCode -> new street + postcode in
              the same city; lat/long nudged, phone re-numbered.
  Emp_Profile.Profile_Notes : leading "Name Surname - " fixed to the actual person.

IDs and every foreign key are left untouched. Idempotent: a second run finds
no repeats and changes nothing. Deterministic (fixed seed).
"""

from __future__ import annotations

import random
import re
import string
from collections import defaultdict
from datetime import datetime, timedelta

SEED = 7

# ── people ────────────────────────────────────────────────────────────────────
GROUPS = {
    "south_asian": {
        "F": ["Anjali", "Kavya", "Neha", "Pooja", "Divya", "Meera", "Ananya", "Shreya", "Ritu", "Sunita", "Nisha", "Harpreet"],
        "M": ["Rohan", "Anil", "Suresh", "Karan", "Nikhil", "Rahul", "Manoj", "Gurpreet", "Amit", "Varun", "Kunal", "Hitesh"],
        "L": ["Mehta", "Gupta", "Kapoor", "Joshi", "Chopra", "Reddy", "Nair", "Iyer", "Bhatt", "Kaur", "Sandhu", "Grewal", "Pillai", "Rao", "Saxena"]},
    "arabic": {
        "F": ["Layla", "Noor", "Mariam", "Zainab", "Sana", "Hiba", "Rania", "Samira", "Huda", "Leila"],
        "M": ["Omar", "Yusuf", "Bilal", "Tariq", "Imran", "Kareem", "Zain", "Faisal", "Khalid", "Idris"],
        "L": ["Rahman", "Hussain", "Qureshi", "Siddiqui", "Chaudhry", "Haddad", "Mansour", "Aziz", "Rashid", "Karim", "Farooq", "Nasser"]},
    "east_european": {
        "F": ["Agnieszka", "Joanna", "Zofia", "Monika", "Daria", "Irina", "Andreea", "Alina", "Simona", "Petra", "Lenka", "Oana"],
        "M": ["Marek", "Krzysztof", "Lukasz", "Bogdan", "Mihai", "Florin", "Stefan", "Dmitri", "Jakub", "Ondrej", "Radu", "Vlad"],
        "L": ["Wisniewski", "Zielinska", "Wojcik", "Kaminski", "Dvorak", "Horvat", "Constantin", "Stan", "Marin", "Georgescu", "Svoboda", "Nemec", "Kovacs", "Szabo"]},
    "west_african": {
        "F": ["Abena", "Efua", "Ngozi", "Funmi", "Yetunde", "Adaeze", "Ama", "Folake", "Zainab", "Esi"],
        "M": ["Kojo", "Yaw", "Chinedu", "Oluwaseun", "Emeka", "Tunde", "Kwabena", "Femi", "Ikenna", "Nana"],
        "L": ["Asante", "Adjei", "Nwosu", "Eze", "Adebayo", "Ogunleye", "Darko", "Appiah", "Obi", "Afolabi", "Bello", "Acheampong"]},
    "irish_scottish": {
        "F": ["Ciara", "Roisin", "Orla", "Eilidh", "Mhairi", "Sinead", "Caitlin", "Fiona", "Kirsty", "Grainne"],
        "M": ["Cian", "Declan", "Euan", "Fraser", "Conor", "Rory", "Seamus", "Ewan", "Lachlan", "Darragh"],
        "L": ["Byrne", "Kelly", "Quinn", "Fraser", "Docherty", "Kennedy", "Gallagher", "Maguire", "Lennox", "Cameron", "Ross", "Boyle"]},
    "british": {
        "F": ["Lucy", "Jessica", "Holly", "Abigail", "Georgia", "Lauren", "Bethany", "Imogen", "Harriet", "Kate", "Joanne", "Helen", "Alice", "Ruth", "Natalie", "Jade"],
        "M": ["Oliver", "Harry", "George", "Jack", "Joe", "Ben", "Luke", "Sam", "Adam", "Matthew", "Paul", "Mark", "Stuart", "Neil", "Graham", "Ian"],
        "L": ["Cooper", "Ward", "Price", "Barker", "Carter", "Mason", "Dixon", "Lawson", "Fisher", "Holt", "Marsh", "Webb", "Chapman", "Kerr", "Shaw", "Palmer", "Hale", "Pryce", "Rhodes", "Kirby"]},
}
FIRST_NAME_GROUP = {
    **{n: ("south_asian", g) for n, g in [("Priya", "F"), ("Rajesh", "M"), ("Vikram", "M"), ("Sanjay", "M"), ("Deepak", "M"), ("Arjun", "M"), ("Aarav", "M")]},
    **{n: ("arabic", g) for n, g in [("Ahmed", "M"), ("Mohammed", "M"), ("Muhammad", "M"), ("Fatima", "F"), ("Aisha", "F"), ("Amir", "M"), ("Amira", "F"), ("Yasmin", "F"), ("Hassan", "M"), ("Rafiq", "M"), ("Rashid", "M"), ("Amina", "F")]},
    **{n: ("east_european", g) for n, g in [("Elena", "F"), ("Magdalena", "F"), ("Piotr", "M"), ("Katarzyna", "F"), ("Natalia", "F"), ("Tomasz", "M"), ("Aleksandra", "F"), ("Andrei", "M"), ("Andrzej", "M"), ("Rafal", "M"), ("Pavel", "M"), ("Cristina", "F"), ("Ioana", "F"), ("Maria", "F"), ("Michal", "M"), ("Kamil", "M"), ("Ionut", "M"), ("Katarina", "F"), ("Mihaela", "F"), ("Adrian", "M")]},
    **{n: ("west_african", g) for n, g in [("Kwame", "M"), ("Amara", "F"), ("Adekunle", "M"), ("Kofi", "M"), ("Adeola", "F"), ("Chisom", "F"), ("Akosua", "F"), ("Nia", "F")]},
    **{n: ("irish_scottish", g) for n, g in [("Niamh", "F"), ("Aoife", "F"), ("Siobhan", "F"), ("Ciaran", "M"), ("Iona", "F"), ("Patrick", "M"), ("Liam", "M")]},
}
BRITISH_F = {"Sophie", "Sarah", "Amelia", "Rachel", "Catherine", "Emma", "Charlotte", "Claire", "Victoria", "Hannah",
             "Eleanor", "Olivia", "Rebecca", "Laura", "Sofia", "Fiona", "Emily", "Grace", "Megan", "Chloe", "Lucy"}

# ── companies ─────────────────────────────────────────────────────────────────
BRAND_WORDS = ["Kestrel", "Cobalt", "Ironbridge", "Halcyon", "Bluefin", "Stratus", "Tidewater", "Copperleaf",
               "Fenwick", "Oakridge", "Silverstream", "Lumen", "Arclight", "Harbourside", "Westgate", "Greystone",
               "Fairhaven", "Kingsmere", "Ravenscroft", "Thistle", "Wren", "Aldgate", "Beacon", "Calder", "Elmstead",
               "Foxglove", "Granite", "Hollis", "Juniper", "Kinross", "Lockhart", "Marlow", "Norbury", "Orchard",
               "Pennant", "Rowan", "Severn", "Thornbury", "Upland", "Vantage", "Wexford", "Yarrow", "Ashgrove",
               "Brightwater", "Castlegate", "Dunmore", "Evergreen", "Falconer", "Glenbrook", "Highcroft", "Ingleby",
               "Keswick", "Larkspur", "Millbank", "Newhaven", "Oakhurst", "Pemberton", "Quayside", "Riverstone",
               "Stonebridge", "Tamar", "Whitecliff", "Albion", "Bramley", "Carrick", "Dovetail", "Elgin", "Fernhill",
               "Gainsford", "Hawthorn", "Islay", "Kelvin", "Linden", "Moorgate", "Northcote", "Ormond", "Pinewood",
               "Redbrook", "Sable", "Trident", "Verity", "Willow", "Axiom", "Clearwater", "Meadowbank", "Saltire"]
# invented compound brand words, e.g. "Ashford", "Ravenmere" -> several hundred unique options
BRAND_WORDS += sorted({p + s for p in ["Ash", "Birch", "Copper", "Elm", "Fox", "Glen", "Haw", "Iron", "Kings", "Lark",
                                       "Mill", "North", "Oak", "Raven", "Silver", "Stone", "West", "White", "Wolf",
                                       "Red", "Black", "Green", "High", "Brook", "Hart", "Bell"]
                       for s in ["field", "bridge", "gate", "wood", "stone", "ford", "mere", "haven", "croft",
                                 "wick", "ridge", "vale", "bury", "ley", "worth"]} - set(BRAND_WORDS))
SURNAMES_LEGAL = ["Pemberton", "Hale", "Whitlock", "Carver", "Ainsley", "Brooke", "Thorne", "Lyall", "Grant",
                  "Fairbairn", "Mercer", "Sutcliffe", "Kendrick", "Ogilvie", "Prescott", "Rowntree", "Abernethy",
                  "Blakemore", "Chalmers", "Dalton", "Everard", "Forsyth", "Gresham", "Holloway", "Iredale",
                  "Jarvis", "Kingsley", "Lambert", "Montague", "Napier", "Osborne", "Pryor", "Radcliffe",
                  "Selwyn", "Tennant", "Underwood", "Vickers", "Waddington", "Yorke", "Ashby"]
INDUSTRY_NOUNS = {
    "Technology": ["Data", "Digital", "Software", "Cloud", "Analytics", "Systems", "Technologies", "Labs", "Networks", "Consulting"],
    "Finance": ["Capital", "Asset Management", "Wealth", "Investments", "Financial", "Insurance", "Securities", "Partners"],
    "Healthcare": ["Health", "Care", "Medical", "Healthcare", "Diagnostics", "Pharma", "Clinical Services", "Life Sciences"],
    "Engineering": ["Engineering", "Infrastructure", "Industrial", "Aerospace", "Energy", "Rail"],
    "Logistics": ["Logistics", "Freight", "Supply Chain", "Distribution"],
    "Education": ["Learning Trust", "Education", "College"],
}
SUFFIX = ["Ltd"] * 6 + ["PLC", "Group", "Group Ltd", ""] * 1 + [""] * 2

# ── addresses ─────────────────────────────────────────────────────────────────
CITY_STREETS = {
    "London": (["EC1", "EC2", "EC3", "EC4", "WC1", "WC2", "W1", "SE1", "E1", "E14", "N1", "SW1"],
               ["Cheapside", "Moorgate", "Fenchurch Street", "Holborn", "Farringdon Road", "Old Street", "Borough High Street",
                "Gracechurch Street", "Queen Victoria Street", "Gray's Inn Road", "Southwark Street", "Great Portland Street",
                "City Road", "Leadenhall Street", "Aldersgate Street", "Theobalds Road", "Victoria Street", "Marsh Wall"]),
    "Birmingham": (["B1", "B2", "B3", "B4", "B5", "B15", "B16"],
                   ["Colmore Row", "Newhall Street", "Broad Street", "Corporation Street", "Hagley Road", "Waterloo Street",
                    "Great Charles Street", "Edmund Street", "Bull Street", "Holloway Head", "Livery Street"]),
    "Manchester": (["M1", "M2", "M3", "M4", "M15", "M50"],
                   ["King Street", "Mosley Street", "Portland Street", "Oxford Road", "Quay Street", "Princess Street",
                    "Spring Gardens", "Peter Street", "Whitworth Street", "Piccadilly", "Chapel Street", "Lever Street"]),
    "Edinburgh": (["EH1", "EH2", "EH3", "EH8", "EH12"],
                  ["George Street", "Queen Street", "Lothian Road", "Leith Walk", "Morrison Street", "Melville Street",
                   "Haymarket Terrace", "Rose Street", "Canongate"]),
    "Reading": (["RG1", "RG2", "RG30"], ["Friar Street", "Kings Road", "Forbury Road", "London Street", "Oxford Road", "Station Road"]),
    "Bristol": (["BS1", "BS2", "BS8"], ["Victoria Street", "Queen Square", "Baldwin Street", "Temple Way", "Whiteladies Road", "Redcliff Street"]),
    "Glasgow": (["G1", "G2", "G3"], ["St Vincent Street", "West George Street", "Bothwell Street", "Hope Street", "Buchanan Street", "Ingram Street"]),
    "Cambridge": (["CB1", "CB2", "CB4"], ["Hills Road", "Station Road", "Regent Street", "Milton Road", "Cowley Road", "Trumpington Street"]),
    "Leeds": (["LS1", "LS2", "LS11"], ["Park Row", "Wellington Street", "Albion Street", "The Headrow", "Whitehall Road", "East Parade"]),
    "Sheffield": (["S1", "S2", "S3"], ["Fargate", "Division Street", "Leopold Street", "Arundel Gate", "Charter Row"]),
}
POSTCODE_LETTERS = [c for c in string.ascii_uppercase if c not in "CIKMOV"]


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def brand_key(name: str) -> str:
    words = re.sub(r"[^\w\s&]", "", name).split()
    return " ".join(words[:2]).lower()


def brand_stem(name: str) -> str:
    return re.sub(r"\s+(Ltd|Limited|PLC|plc|LLP|Group|Partners|Solutions|Systems|Services|Management)\b.*$", "", name).strip() or name


def run(read_csv, write_csv, columns: dict[str, list[str]]) -> list[str]:
    rng = random.Random(SEED)
    log = []

    # ── accounts ──────────────────────────────────────────────────────────────
    accounts = read_csv("Accounts")
    addresses = read_csv("Addresses")
    addr_by_id = {a["AddressID"]: a for a in addresses}
    seen_brands, renamed = set(), 0
    used_words = {re.sub(r"[^\w]", "", a["Account_name"].split()[0]).lower() for a in accounts if a["Account_name"]}

    def new_company(industry: str) -> str:
        for _ in range(20000):
            if industry == "Legal":
                a, b = rng.sample(SURNAMES_LEGAL, 2)
                name = rng.choice([f"{a} {b} LLP", f"{a} & {b} LLP", f"{a} Law LLP", f"{a} Solicitors"])
            else:
                w = rng.choice(BRAND_WORDS)
                noun = rng.choice(INDUSTRY_NOUNS.get(industry, INDUSTRY_NOUNS["Technology"]))
                name = f"{w} {noun} {rng.choice(SUFFIX)}".strip()
            key = brand_key(name)
            first = slug(name.split()[0])
            # the first word must be unique too, so unrelated firms never look like the same brand
            if key not in seen_brands and first not in used_words:
                used_words.add(first)
                return name
        raise RuntimeError("ran out of unique company names; extend BRAND_WORDS")

    for acc in accounts:
        key = brand_key(acc["Account_name"])
        if not key or key not in seen_brands:
            seen_brands.add(key)
            continue
        old, new = acc["Account_name"], new_company(acc["Industry"])
        seen_brands.add(brand_key(new))
        old_stem, new_stem = brand_stem(old), brand_stem(new)
        old_first = old.split()[0]
        for col in ("About", "Note"):
            text = acc[col]
            text = text.replace(old, new).replace(old_stem, new_stem)
            if len(old_first) >= 5 and old_first not in ("Crown", "Trinity", "Vital", "Bridge", "NHS"):
                text = re.sub(rf"\b{re.escape(old_first)}\b", new.split()[0], text)
            acc[col] = text
        domain = slug(" ".join(new_stem.split()[:2])) + ".co.uk"
        acc["Website"] = f"https://www.{domain}"
        acc["Account_name"] = new
        addr = addr_by_id.get(acc["AddressID"])
        if addr and "@" in addr["Email"]:
            addr["Email"] = addr["Email"].split("@")[0] + "@" + domain
        renamed += 1
    if renamed:
        write_csv("Accounts", accounts, columns["Accounts"])
        log.append(f"Accounts: {renamed} repeated brands given new company identities")

    # ── addresses ─────────────────────────────────────────────────────────────
    seen_addr = set()
    readdressed = 0
    for a in addresses:
        key = (a["Address_line1"].strip().lower(), a["ZipCode"].replace(" ", "").upper())
        if key not in seen_addr:
            seen_addr.add(key)
            continue
        districts, streets = CITY_STREETS.get(a["City"], CITY_STREETS["London"])
        while True:
            line1 = f"{rng.randint(1, 240)} {rng.choice(streets)}"
            pc = f"{rng.choice(districts)} {rng.randint(1, 9)}{rng.choice(POSTCODE_LETTERS)}{rng.choice(POSTCODE_LETTERS)}"
            k = (line1.lower(), pc.replace(" ", ""))
            if k not in seen_addr:
                seen_addr.add(k)
                break
        a["Address_line1"], a["ZipCode"] = line1, pc
        a["Address_line2"] = rng.choice(["", "", f"Floor {rng.randint(1, 12)}", f"Suite {rng.randint(100, 900)}"])
        for c, d in (("Latitude", 6), ("Longitude", 6)):
            if a[c]:
                a[c] = f"{float(a[c]) + rng.uniform(-0.008, 0.008):.{d}f}"
        for c in ("Phone", "WorkPhone"):
            if a[c] and re.search(r"\d{4}$", a[c]):
                a[c] = a[c][:-4] + f"{rng.randint(1000, 9999)}"
        readdressed += 1
    if readdressed or renamed:
        write_csv("Addresses", addresses, columns["Addresses"])
    if readdressed:
        log.append(f"Addresses: {readdressed} repeated street addresses re-addressed within the same city")

    # ── people ────────────────────────────────────────────────────────────────
    persons = read_csv("Person")
    seen_names = set()
    renamed_p = 0
    seen_dobs = {p["DOB"] for p in persons}
    for p in persons:
        key = (p["First_Name"].strip().lower(), p["Last_Name"].strip().lower())
        if key not in seen_names:
            seen_names.add(key)
            continue
        group, gender = FIRST_NAME_GROUP.get(p["First_Name"], ("british", "F" if p["First_Name"] in BRITISH_F else "M"))
        pool = GROUPS[group]
        for _ in range(500):
            fn, ln = rng.choice(pool[gender]), rng.choice(pool["L"])
            if (fn.lower(), ln.lower()) not in seen_names and fn != p["Middle_name"]:
                break
        seen_names.add((fn.lower(), ln.lower()))
        p["First_Name"], p["Last_Name"] = fn, ln
        # the repeats were copies, DOB included; give the new person their own birthday
        if p["DOB"]:
            base = datetime.strptime(p["DOB"], "%Y-%m-%d")
            for _ in range(100):
                dob = (base + timedelta(days=rng.choice([-1, 1]) * rng.randint(40, 1500))).strftime("%Y-%m-%d")
                if dob not in seen_dobs:
                    break
            seen_dobs.add(dob)
            p["DOB"] = dob
        renamed_p += 1
    if renamed_p:
        write_csv("Person", persons, columns["Person"])
        log.append(f"Person: {renamed_p} repeated names replaced (same cultural group and gender)")

    # ── employee profile notes start with the person's name ───────────────────
    names = {p["Person_ID"]: f"{p['First_Name']} {p['Last_Name']}" for p in persons}
    profiles, fixed = read_csv("Emp_Profile"), 0
    for e in profiles:
        m = re.match(r"^([A-Z][\w'’-]+(?: [A-Z][\w'’-]+){1,2}) - ", e["Profile_Notes"])
        real = names.get(e["Person_ID"])
        if m and real and m.group(1) != real:
            e["Profile_Notes"] = real + e["Profile_Notes"][len(m.group(1)):]
            fixed += 1
    if fixed:
        write_csv("Emp_Profile", profiles, columns["Emp_Profile"])
        log.append(f"Emp_Profile: {fixed} profile notes re-headed with the correct person's name")
    return log
