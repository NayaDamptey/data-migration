"""
sample_data/generate_addresses.py

Runs AFTER generate_ai.py. Reads every Person and Account record,
generates a realistic UK address for each one using Claude, writes
them all to Addresses.csv, then updates every FK that references
an address across all affected tables.

Address assignments:
  Addresses 1–200       → one per Account (company office)
  Addresses 201–700     → one per Person  (home/work address)
  Addresses 701+        → job location addresses (one per Req, derived from Account)

FK columns updated:
  Accounts.AddressID              → company office address
  Accounts.InvoiceAddressID       → same as company office
  Associates.Associate_AddressID  → address of the company they work at
  Req.Address_ID                  → address of the account that raised the req

Run: python sample_data/generate_addresses.py
"""

import csv
import json
import os
import re
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

load_dotenv()

SOURCE_DIR = Path(__file__).parent / "source"
console    = Console()
client     = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ── helpers ───────────────────────────────────────────────────────────────────

def read_csv(name: str) -> list[dict]:
    path = SOURCE_DIR / f"{name}.csv"
    if not path.exists():
        console.print(f"[red]Missing: {path}[/red]")
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(name: str, rows: list[dict]):
    if not rows:
        return
    path = SOURCE_DIR / f"{name}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    console.print(f"  [green]OK[/green]   {name}.csv  ({len(rows)} rows)")


def ask(prompt: str, max_tokens: int = 4000) -> list | dict:
    """Call Claude, parse JSON. Returns [] on failure — never raises."""
    full = (
        "You are a data consultant populating a UK recruitment database with realistic addresses.\n\n"
        + prompt
        + "\n\nRespond with valid JSON only. No markdown, no code fences."
    )
    token_limit = max_tokens
    for attempt in range(3):
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=min(token_limit, 8096),
                messages=[{"role": "user", "content": full}],
            )
            text = msg.content[0].text.strip()
            text = re.sub(r"^```[a-z]*\n?|```$", "", text, flags=re.MULTILINE).strip()
            return json.loads(text)
        except json.JSONDecodeError:
            token_limit = min(token_limit * 2, 8096)
            console.print(f"  [yellow]JSON truncated — retry {attempt+1}/3 with {token_limit} tokens[/yellow]")
            time.sleep(1)
        except Exception as e:
            console.print(f"  [yellow]API error (attempt {attempt+1}/3): {type(e).__name__}[/yellow]")
            time.sleep(3)
    console.print("  [red]Batch failed — skipping[/red]")
    return []


# ── city → postcode prefix + lat/lon centre ──────────────────────────────────

CITY_DATA = {
    "London (City)":       ("EC2",  51.5155, -0.0922),
    "London (Canary Wharf)":("E14", 51.5054, -0.0235),
    "London (West End)":   ("W1",   51.5140, -0.1410),
    "London (Shoreditch)": ("E1",   51.5247, -0.0761),
    "London (South Bank)": ("SE1",  51.5033, -0.1145),
    "Manchester":          ("M1",   53.4808, -2.2426),
    "Birmingham":          ("B1",   52.4862, -1.8904),
    "Leeds":               ("LS1",  53.7996, -1.5491),
    "Bristol":             ("BS1",  51.4545, -2.5879),
    "Edinburgh":           ("EH1",  55.9533, -3.1883),
    "Glasgow":             ("G1",   55.8642, -4.2518),
    "Liverpool":           ("L1",   53.4084, -2.9916),
    "Sheffield":           ("S1",   53.3811, -1.4701),
    "Nottingham":          ("NG1",  52.9548, -1.1581),
    "Reading":             ("RG1",  51.4543, -0.9781),
    "Cambridge":           ("CB1",  52.2053,  0.1218),
    "Oxford":              ("OX1",  51.7520, -1.2577),
}

CITIES = list(CITY_DATA.keys())


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — COMPANY ADDRESSES (one per Account)
# ══════════════════════════════════════════════════════════════════════════════

def gen_company_addresses(accounts: list[dict]) -> dict[str, int]:
    """
    Generates one office address per account.
    Returns {Account_ID: AddressID}.
    """
    console.print("\n[bold cyan]Phase 1 — Company addresses (one per Account)[/bold cyan]")

    all_addresses = []
    account_address_map: dict[str, int] = {}
    addr_id = 1

    for batch_start in range(0, len(accounts), 10):
        batch = accounts[batch_start:batch_start + 10]

        items = [
            {
                "account_id": a["Account_ID"],
                "company_name": a.get("Account_name", ""),
                "industry": a.get("Industry", ""),
            }
            for a in batch
        ]

        data = ask(f"""
Generate one realistic UK office address for each company below.
The address must match the company's name and industry:
- Finance/Legal companies: prefer London City (EC/WC postcodes), Canary Wharf (E14)
- Tech companies: London (EC/E1/N1), Manchester (M1/M2), Bristol (BS1), Cambridge (CB)
- Healthcare: anywhere, including smaller cities
- Construction/Engineering: Birmingham, Leeds, Sheffield, Manchester
- Media: London (W1, SE1, Shoreditch E1)

Address rules:
- Address_line1: building number + street name (real UK street names)
- Address_line2: floor/suite or blank
- ZipCode: MUST be a valid UK postcode matching the city
  London EC: EC2N 4AJ, EC1A 1BB etc.
  Manchester: M1 1AE, M2 3BQ etc.
  Birmingham: B1 1BB, B2 4QA etc.
- Phone: main office phone matching city area code
  London: +44 20 XXXX XXXX, Manchester: +44 161 XXX XXXX, Birmingham: +44 121 XXX XXXX
- Email: info@companyname.co.uk (derived from company name, lowercase, no spaces)
- Longitude/Latitude: accurate for the city

Companies: {json.dumps(items)}

Return JSON array — one object per company in the same order:
{{
  "account_id": "1",
  "Address_line1": "40 Gresham Street",
  "Address_line2": "Floor 5",
  "City": "London",
  "ZipCode": "EC2V 7HH",
  "Province": "Greater London",
  "Country": "United Kingdom",
  "Email": "info@apexsystems.co.uk",
  "Phone": "+44 20 7600 1234",
  "OtherPhone": "",
  "WorkPhone": "+44 20 7600 1235",
  "Longitude": -0.0922,
  "Latitude": 51.5155,
  "CreatedAt": "2020-01-15 09:00:00",
  "CreatedBy": 1
}}
""", max_tokens=4000)

        for i, item in enumerate(data or []):
            account_id = batch[i]["Account_ID"] if i < len(batch) else None
            if not account_id:
                continue
            row = {
                "AddressID":     addr_id,
                "Address_line1": item.get("Address_line1", "1 Business Park"),
                "Address_line2": item.get("Address_line2", ""),
                "City":          item.get("City", "London"),
                "ZipCode":       item.get("ZipCode", "EC1A 1BB"),
                "Province":      item.get("Province", "Greater London"),
                "Country":       "United Kingdom",
                "Email":         item.get("Email", ""),
                "Phone":         item.get("Phone", ""),
                "OtherPhone":    item.get("OtherPhone", ""),
                "WorkPhone":     item.get("WorkPhone", ""),
                "Longitude":     item.get("Longitude", -0.09),
                "Latitude":      item.get("Latitude", 51.51),
                "CreatedAt":     "2020-01-15 09:00:00",
                "CreatedBy":     1,
            }
            all_addresses.append(row)
            account_address_map[str(account_id)] = addr_id
            addr_id += 1

        time.sleep(0.3)

    console.print(f"  Generated {len(all_addresses)} company addresses")
    return all_addresses, account_address_map, addr_id


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — CANDIDATE HOME ADDRESSES (one per Person)
# ══════════════════════════════════════════════════════════════════════════════

def gen_person_addresses(persons: list[dict], start_id: int) -> tuple[list[dict], dict[str, int]]:
    """
    Generates one home/work address per person.
    Returns (address_rows, {Person_ID: AddressID}).
    """
    console.print("\n[bold cyan]Phase 2 — Candidate home addresses (one per Person)[/bold cyan]")

    all_addresses = []
    person_address_map: dict[str, int] = {}
    addr_id = start_id

    for batch_start in range(0, len(persons), 15):
        batch = persons[batch_start:batch_start + 15]

        items = [
            {"person_id": p["Person_ID"], "first": p.get("First_Name",""), "last": p.get("Last_Name","")}
            for p in batch
        ]

        data = ask(f"""
Generate one realistic UK home address for each candidate below.
These are IT contractors and professionals who live across the UK.
Mix of cities: London (40%), Manchester (15%), Birmingham (10%), Leeds (8%),
Bristol (7%), Edinburgh (5%), Glasgow (5%), others (10%).

Address rules:
- Address_line1: house number + street name (residential streets, not office buildings)
- Address_line2: flat number if applicable, otherwise blank
- ZipCode: valid UK postcode matching the city
- Phone: UK mobile number (+44 7XXX XXXXXX) — this is their personal mobile
- Email: personal email (firstname.lastname@gmail.com or @outlook.com or @hotmail.co.uk)
  MUST be derived from their actual name: {items[0]['first']} {items[0]['last']} → firstname.lastname@gmail.com
- WorkPhone: blank for candidates (they don't have a work phone on file)
- OtherPhone: blank or a second mobile

Candidates: {json.dumps(items)}

Return JSON array — one object per candidate in the same order:
{{
  "person_id": "1",
  "Address_line1": "47 Maple Avenue",
  "Address_line2": "Flat 3",
  "City": "Manchester",
  "ZipCode": "M14 7EH",
  "Province": "Greater Manchester",
  "Country": "United Kingdom",
  "Email": "priya.sharma@gmail.com",
  "Phone": "+44 7891 234567",
  "OtherPhone": "",
  "WorkPhone": "",
  "Longitude": -2.2193,
  "Latitude": 53.4520,
  "CreatedAt": "2021-06-10 09:00:00",
  "CreatedBy": 1
}}
""", max_tokens=4000)

        for i, item in enumerate(data or []):
            person_id = batch[i]["Person_ID"] if i < len(batch) else None
            if not person_id:
                continue
            row = {
                "AddressID":     addr_id,
                "Address_line1": item.get("Address_line1", "1 High Street"),
                "Address_line2": item.get("Address_line2", ""),
                "City":          item.get("City", "London"),
                "ZipCode":       item.get("ZipCode", "E1 1AA"),
                "Province":      item.get("Province", "Greater London"),
                "Country":       "United Kingdom",
                "Email":         item.get("Email", ""),
                "Phone":         item.get("Phone", ""),
                "OtherPhone":    item.get("OtherPhone", ""),
                "WorkPhone":     item.get("WorkPhone", ""),
                "Longitude":     item.get("Longitude", -0.09),
                "Latitude":      item.get("Latitude", 51.51),
                "CreatedAt":     item.get("CreatedAt", "2021-06-10 09:00:00"),
                "CreatedBy":     1,
            }
            all_addresses.append(row)
            person_address_map[str(person_id)] = addr_id
            addr_id += 1

        time.sleep(0.3)

    console.print(f"  Generated {len(all_addresses)} candidate addresses")
    return all_addresses, person_address_map, addr_id


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — UPDATE ALL FK REFERENCES
# ══════════════════════════════════════════════════════════════════════════════

def update_fk_references(account_address_map: dict, person_address_map: dict):
    console.print("\n[bold cyan]Phase 3 — Updating FK references[/bold cyan]")

    # Accounts: AddressID + InvoiceAddressID → company office address
    accounts = read_csv("Accounts")
    for row in accounts:
        aid = str(row.get("Account_ID", ""))
        if aid in account_address_map:
            row["AddressID"]        = account_address_map[aid]
            row["InvoiceAddressID"] = account_address_map[aid]
    write_csv("Accounts", accounts)

    # Associates: Associate_AddressID → address of the company they work at
    # Look up via AccountAssociates junction to find their company
    aa = read_csv("AccountAssociates")
    assoc_to_account: dict[str, str] = {
        str(row["AssociateID"]): str(row["AccountID"]) for row in aa
    }
    associates = read_csv("Associates")
    updated = 0
    for row in associates:
        assoc_id   = str(row.get("AssociateID", ""))
        account_id = assoc_to_account.get(assoc_id)
        if account_id and account_id in account_address_map:
            row["Associate_AddressID"] = account_address_map[account_id]
            updated += 1
    write_csv("Associates", associates)
    console.print(f"  [dim]Associates: updated {updated} address references[/dim]")

    # Req: Address_ID → address of the account that raised the req
    reqs = read_csv("Req")
    updated = 0
    for row in reqs:
        account_id = str(row.get("AccountID", ""))
        if account_id in account_address_map:
            row["Address_ID"] = account_address_map[account_id]
            updated += 1
    write_csv("Req", reqs)
    console.print(f"  [dim]Req: updated {updated} address references[/dim]")

    # Schedules: no direct address FK — skip
    # Leads: inline address fields, not a FK — skip


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[red]ANTHROPIC_API_KEY not set in .env[/red]")
        return

    console.print(Panel(
        "[bold]Address Generator[/bold]\n\n"
        "Generates a realistic address for every Account and Person record,\n"
        "then updates all FK references across the database.",
        style="blue",
    ))

    accounts = read_csv("Accounts")
    persons  = read_csv("Person")

    if not accounts:
        console.print("[red]No Accounts found — run generate_ai.py first[/red]")
        return
    if not persons:
        console.print("[red]No Persons found — run generate_ai.py first[/red]")
        return

    console.print(f"\n  Accounts: {len(accounts)}  |  Persons: {len(persons)}")

    # Phase 1 — company addresses
    company_addrs, account_address_map, next_id = gen_company_addresses(accounts)

    # Phase 2 — candidate home addresses
    person_addrs, person_address_map, _ = gen_person_addresses(persons, next_id)

    # Write combined Addresses.csv
    all_addresses = company_addrs + person_addrs
    write_csv("Addresses", all_addresses)
    console.print(f"\n  Total addresses written: {len(all_addresses)}")
    console.print(f"  Company addresses (1–{len(company_addrs)}): {len(company_addrs)}")
    console.print(f"  Candidate addresses ({len(company_addrs)+1}–{len(all_addresses)}): {len(person_addrs)}")

    # Phase 3 — update all FK references
    update_fk_references(account_address_map, person_address_map)

    console.print(Panel(
        "[green]Done — Addresses.csv written and all FK references updated.[/green]\n\n"
        "Next step: [bold]python mapping/reviewer.py[/bold]",
        style="green",
    ))


if __name__ == "__main__":
    main()
