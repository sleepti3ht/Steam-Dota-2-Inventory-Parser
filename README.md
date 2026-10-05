
<div align="center">
    
# steam-dota2-inventory-parser

[![python](https://img.shields.io/badge/Python-3.10+-blue?style=flat&color=3776ab)](https://python.org)
[![status](https://img.shields.io/badge/status-active-success?style=flat&color=2ea043)](#)
[![steam](https://img.shields.io/badge/Steam-API-1b2838?style=flat&logo=steam)](https://steamcommunity.com)
[![license](https://img.shields.io/badge/license-MIT-black?style=flat&color=18181b)](LICENSE)

</div>

> ⚡ Sequentially parse public Dota 2 Steam inventories and export filtered items to CSV, respecting rate limits and API constraints.

Reads SteamID64s, requests public inventories via Steam Community API, and saves only items matching specific filters (Quality, Rarity, Hero + Gem, Slot). Built for reliability and data integrity, not raw speed.

## Get started

```bash
git clone https://github.com/YOUR_USERNAME/steam-dota2-inventory-parser.git
cd steam-dota2-inventory-parser
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## After setup

1. Create `steamids.txt` in the root folder (one 17-digit SteamID64 per line, `#` for comments).
2. Run the parser:
   ```bash
   python steam_parser.py
   ```
3. Check `steam_output.csv` for results.

- tweak filters: modify `TARGET_HEROES`, `QUALITIES`, and `RARITIES` lists in `steam_parser.py`
- adjust rate limits: change `delay` and `max_concurrent` in `main()`
- cache location: responses are cached in `steam_cache.json` (TTL 7 days)

## 🔋 Batteries Included

**🛡️ Rate Limiting & Reliability**

- empirical 80-second backoff on HTTP `429 Too Many Requests` (tested against 70/90/120s variants)
- immediate skip on HTTP `403 Forbidden` (private inventory or restricted profile)
- sequential processing (`max_concurrent=1`) to minimize ban risk
- 7-day TTL JSON cache to reduce redundant API calls on script reruns

**🎯 Smart Item Filtering**

- detects `Summoned Unit` slot via `localized_tag_name` (works even if the item is renamed by the owner, e.g., *Maraxiform's Fallen*)
- hero + gem validation: only includes items from 12 specific heroes if they contain valuable gem modifiers
- override targets: specific items like *Almond the Frondillo* are matched by name regardless of hero

**📊 Excel-Ready Output**

- semicolon-separated (`;`) CSV to prevent scientific notation corruption of 17-digit SteamID64 in RU/DE Excel locales
- comprehensive columns: `SteamID`, `Name`, `Quality`, `Rarity`, `Type`, `Slot`, `Hero`, `HasGem`, `TradeFlags`, `TradableAfter`, `ProfileURL`

## Why steam-dota2-inventory-parser

Most inventory scrapers are either too aggressive (triggering immediate 429/403 bans) or too naive (failing on renamed items or custom slots). 

This script prioritizes **stability** over speed. It treats the Steam API with respect, uses empirical backoff strategies, and relies on technical API tags (`localized_tag_name`) rather than fragile display names.

**🦾 Better for long-running tasks:** predictable memory footprint, no external browser overhead (pure HTTP requests via `aiohttp`), and safe for low-end VPS environments.

## How it works

```text
read steamids.txt
  → check steam_cache.json (TTL 7 days)
  → request Steam Community Inventory API (sequential, 4.0s delay)
  → handle 429 (wait 80s, retry x3) or 403 (skip immediately)
  → parse items against filter rules (Quality, Rarity, Slot, Hero+Gem)
  → append valid matches to steam_output.csv
```

## ⚠️ Architecture & Limits

- **Rate Limiting**: Hardcoded 80s backoff on `429`. Do not decrease `delay` below `4.0` or increase `max_concurrent` above `1` without empirical testing on your specific IP range.
- **Race Conditions**: Running multiple instances of this script concurrently sharing the same `steam_cache.json` may cause file write collisions. Use separate working directories or implement file locking (`fcntl` / `msvcrt`) if parallel execution is strictly required.
- **Memory**: The script processes profiles sequentially and yields results, keeping memory footprint minimal (~20-40MB). No memory leaks expected under normal operation.

## Important Notes

- **SteamID64 only**: The script requires 17-digit numeric IDs, not profile URLs or custom URLs.
- **Excel Import**: When opening `steam_output.csv`, ensure the `SteamID` column is formatted as **Text** to prevent precision loss.
- **Public Data Only**: This tool only accesses publicly available inventory data. It does not interact with accounts, trade, or bypass authentication.

---

📖 Full filter configuration and column details are documented in the source code comments.

## Disclaimer

Use this project at your own risk. Comply with Steam's Terms of Service, public endpoint limitations, and applicable platform regulations. The author is not responsible for account restrictions resulting from API abuse.
