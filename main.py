#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SAFE ACCOUNT PIPELINE (Skeleton)
- Multithreaded generator (50 workers default)
- JSON persistence
- Rare/Couple ID detection
- Checker/enricher
- Clear integration points for YOUR OWN backend (no third-party services)

Run:
  python safe_pipeline.py

Files:
  freefire_accounts.json  -> basic accounts
  details.json            -> enriched accounts (checker output)
  output/rare.json        -> rare account IDs (>=4 same digits consecutive)
  output/couples.json     -> “couple” IDs (last digit differs by 1)
"""

import os
import json
import random
import string
import time
from pathlib import Path
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# -----------------------
# CONFIG
# -----------------------
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ACCOUNTS_FILE = Path("freefire_accounts.json")
DETAILS_FILE  = Path("details.json")

# Default thread count (you said “5g” -> go extreme)
MAX_WORKERS = 50

# Allowed regions for demo
REGIONS = ["IND","ID","BR","ME","VN","TH","CIS","BD","PK","SG","NA","SAC","EU","TW"]

# Locks
file_lock = Lock()
print_lock = Lock()

# -----------------------
# UTILITIES
# -----------------------
def rand_name(prefix="Noob", length=6):
    chars = string.ascii_uppercase + string.digits
    return prefix + ''.join(random.choice(chars) for _ in range(length))

def rand_password():
    chars = string.ascii_uppercase + string.digits
    return "NoobXGmr" + ''.join(random.choice(chars) for _ in range(9))

def rand_account_id():
    # 10–12 digit numeric ID
    first = random.randint(1,9)
    rest  = ''.join(random.choice(string.digits) for _ in range(random.randint(9,11)))
    return int(str(first) + rest)

def is_couple(a, b):
    return abs(int(str(a)[-1]) - int(str(b)[-1])) == 1

def is_rare(acc_id):
    s = str(acc_id)
    run = 1
    for i in range(1, len(s)):
        if s[i] == s[i-1]:
            run += 1
            if run >= 4:
                return True
        else:
            run = 1
    return False

def safe_load_json(path):
    if not Path(path).exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def safe_write_json(path, data):
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

def pretty_print_account(acc):
    with print_lock:
        print(
            f"👤 Name: {acc['name']} | 🆔 UID: {acc['uid']} | "
            f"📊 AccountID: {acc['account_id']} | 🌍 Region: {acc['region']}"
        )

# -----------------------
# INTEGRATION POINTS (Replace with YOUR backend)
# -----------------------
def create_account_via_your_backend(region: str):
    """
    🔌 INTEGRATION POINT #1
    Replace this mock with your OWN legal API/service.

    Must return a dict with: uid, password, account_id, name, region
    """
    # --- MOCK IMPLEMENTATION (randomized, offline) ---
    uid = ''.join(random.choice(string.digits) for _ in range(12))
    account_id = rand_account_id()
    name = rand_name()
    password = rand_password()
    return {
        "uid": uid,
        "password": password,
        "account_id": account_id,
        "name": name,
        "region": region
    }

def check_account_details_via_your_backend(uid: str, account_id: int):
    """
    🔌 INTEGRATION POINT #2
    Replace this with your OWN legal API/service to fetch account stats.

    Must return a dict with any fields you want saved in details.json
    """
    # --- MOCK IMPLEMENTATION (randomized, offline) ---
    # “full” enrichment: level, rank, kd, hs_rate, diamonds, guild

ranks = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Heroic", "Master"]
    guilds = ["", "Dark Knights", "Sky Lords", "NS GAMMiNG", "Blue Tigers", "Phoenix"]
    return {
        "level": random.randint(1, 80),
        "rank": random.choice(ranks),
        "kd": round(random.uniform(0.5, 6.5), 2),
        "hs_rate": round(random.uniform(5, 80), 2),   # headshot rate %
        "diamonds": random.randint(0, 15000),
        "guild": random.choice(guilds)
    }

# -----------------------
# CORE: GENERATION
# -----------------------
def save_account(account, filename=ACCOUNTS_FILE):
    with file_lock:
        data = safe_load_json(filename)
        data.append(account)
        safe_write_json(filename, data)

def generate_one(region: str):
    account = create_account_via_your_backend(region)
    save_account(account)
    pretty_print_account(account)
    return True

def generate_bulk(region: str, count: int, max_workers: int = MAX_WORKERS):
    print(f"\n🚀 Starting generation: {count} accounts | Region {region} | Threads {max_workers}\n")
    ok = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(generate_one, region) for _ in range(count)]
        for fut in as_completed(futures):
            try:
                if fut.result():
                    ok += 1
            except Exception as e:
                with print_lock:
                    print(f"⚠️ Generation error: {e}")
    print(f"\n✅ Done. Created {ok}/{count} accounts.\n")
    return ok

# -----------------------
# RARE & COUPLES
# -----------------------
def detect_rare_and_couples():
    data = safe_load_json(ACCOUNTS_FILE)
    if not data:
        print("ℹ️ No accounts to scan.")
        return

    # Rare
    rare = [acc for acc in data if is_rare(acc.get("account_id", 0))]
    if rare:
        rare_path = OUTPUT_DIR / "rare.json"
        safe_write_json(rare_path, rare)
        print(f"🎯 Rare IDs saved -> {rare_path}")

    # Couples (collect unique accounts that pair with someone by last digit ±1)
    couples = []
    seen = set()
    for i in range(len(data)):
        for j in range(i + 1, len(data))):
            a = data[i]["account_id"]
            b = data[j]["account_id"]
            if a is None or b is None:
                continue
            if is_couple(a, b):
                if i not in seen:
                    couples.append(data[i]); seen.add(i)
                    print(f"💑 Couple found: {a}")
                if j not in seen:
                    couples.append(data[j]); seen.add(j)
                    print(f"💑 Couple found: {b}")
    if couples:
        couples_path = OUTPUT_DIR / "couples.json"
        safe_write_json(couples_path, couples)
        print(f"📁 Couple IDs saved -> {couples_path}")

# -----------------------
# CHECKER / ENRICHER
# -----------------------
def run_checker_full(max_workers: int = MAX_WORKERS):
    base = safe_load_json(ACCOUNTS_FILE)
    if not base:
        print("ℹ️ No accounts found to check.")
        return

    print(f"\n🔎 Checker: enriching {len(base)} accounts with FULL details using {max_workers} threads...\n")

    def _enrich(acc):
        # Call your backend here
        extra = check_account_details_via_your_backend(acc["uid"], acc["account_id"])
        enriched = {acc, extra, "checked_at": datetime.utcnow().isoformat() + "Z"}
        return enriched

    enriched_list = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_enrich, acc): acc for acc in base}
        for fut in as_completed(futures):
            try:
                enriched_list.append(fut.result())
            except Exception as e:
                with print_lock:
                    print(f"⚠️ Checker error: {e}")

    safe_write_json(DETAILS_FILE, enriched_list)
    print(f"✅ Checker completed. Saved -> {DETAILS_FILE}")

# -----------------------
# CLI
# -----------------------
def ask_int(prompt, default):
    try:
        v = input(prompt).strip()
        return int(v) if v else default
    except Exception:
        return default

def main():
    print("\n" + "═" * 72)
    print(" SAFE ACCOUNT PIPELINE (Skeleton) ".center(72, " "))
    print("═" * 72 + "\n")

    # region
    print("Available regions:", ", ".join(REGIONS))
    region = input("Choose region (default IND): ").strip().upper() or "IND"
    if region not in REGIONS:
        print("Invalid region; using IND.")
        region = "IND"

    # counts & threads
    num = ask_int("How many accounts to generate? (default 5): ", 5)
    threads = ask_int(f"Threads? (default {MAX_WORKERS}): ", MAX_WORKERS)

    # Generate
    generate_bulk(region, num, max_workers=threads)

    # Detect rare/couples
    print("\n🔍 Scanning for rare/couple IDs...")
    detect_rare_and_couples()

    # Checker (full)
    run_checker_full(max_workers=threads)

    print("\n🎉 All tasks finished successfully.\n")

if name == "main":
    main()