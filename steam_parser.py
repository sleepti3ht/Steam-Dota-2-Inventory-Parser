# Steam Dota 2 Inventory Parser

> Small Python script for sequentially checking public Dota 2 Steam inventories and exporting items of interest to CSV.

![python](https://img.shields.io/badge/Python-3.10%2B-blue)
![status](https://img.shields.io/badge/status-active-success)
![steam](https://img.shields.io/badge/Steam-public%20inventories-1b2838)

The script reads a list of SteamID64 from `steamids.txt`, requests public Dota 2 inventories, and saves only items that match at least one specified filter to a table.

> This project is intended to work only with publicly available Steam data.  
> The script does not buy, sell, or exchange items or accounts.

---

## ✨ Features

- Reads SteamID64 from `steamids.txt`
- Checks public Dota 2 inventories via Steam Community Inventory API
- Works sequentially with configurable pause between profiles
- On HTTP `429 Too Many Requests`, waits **80 seconds** and retries up to 3 times
- On HTTP `403 Forbidden`, skips the profile immediately
- Caches ответы to `steam_cаche.json` (TTL 7 days) — меньше 429 при повтortных запусках
- Exports results to CSV (semicolon-separated, `;`) for Excel
- Correctly detects items with `Summoned Unit` slot, including **Maraxiform's Fallen**
- Independent of displayed item name: renaming an instance doesn't interfere with slot determination

### Item Filters

- **Quality**: `Auspicious`, `Genuine`, `Unusual`, `Corrupted`, `Autographed`, `Inscribed`
- **Rarity**: `Arcana`
- **Type**: `Courier`
- **Slot**: `Summoned Unit`
- **Hero + Gem**: only `11` heroes with valuable gems (see below)
- **Target Items**: `Almond the Frondillo` (override — matched by name regardless of hero)

---

## 🛠 Requirements

- Python 3.10+
- Access to public Steam Community inventories
- `aiohttp` library

## 📦 Installation

```bash
git clone https://github.com/YOUR_USERNAME/steam-dota2-inventory-parser.git
cd steam-dota2-inventory-parser
```

Create and activate a virtual environment.

### Windows PowerShell
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Windows CMD
```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

### Install dependencies
```bash
pip install -r requirements.txt
```

---

## 📄 Preparing SteamID List

Create `steamids.txt` in the script folder. One SteamID64 per line:

```
76561198000000001
76561198000000002
76561198000000003
```

Lines starting with `#` are ignored:

```
# Test profiles
76561198000000001
76561198000000002
```

Use **SteamID64 specifically**, not a profile link or account short name.

---

## 🚀 Running

### Windows PowerShell
```powershell
.\.venv\Scripts\python.exe .\steam_parser.py
```

### Regular run (output to file only)
```bash
python steam_parser.py > steam_output.csv 2>&1
```

After completion, a file appears: `steam_output.csv`

---

## 📊 CSV Columns

| Column | Description |
|---|---|
| `SteamID` | SteamID64 of the inventory owner |
| `Name` | Display name of the item |
| `Quality` | Matching quality if found |
| `Rarity` | Matching rarity if found |
| `Type` | Item type, e.g. `Courier` |
| `Slot` | Item slot, e.g. `Summoned Unit` |
| `Hero` | Hero name if detected (e.g. `Pudge`, `Juggernaut`) |
| `HasGem` | `yes` if a matching gem modifier is found |
| `TradeFlags` | Trading restrictions from inventory data |
| `TradableAfter` | Time when the item becomes tradable again |
| `ProfileURL` | Link to the profile inventory |

> The CSV uses `;` as separator — double-click opens correctly in Excel (RU/DE locales).

---

## 🎯 Hero + Gem Filter

The script filters items by **12 heroes with valuable gems**:

- `Doom`
- `Juggernaut`
- `Kunkka`
- `Phantom Lancer`
- `Puck`
- `Pudge`
- `Sven`
- `Techies`
- `Terrorblade`
- `Tusk`
- `Wraith King`

Only items from these heroes **with gems** are included. Couriers and target items (e.g. `Almond the Frondillo`) are included regardless of hero.

---

## 🔍 Summoned Unit Filtering

For items in the `Summoned Unit` slot, the Steam API tag is used:

```
category = Slot
internal_name = summon
localized_tag_name = Summoned Unit
```

For example, `Maraxiform's Fallen` is identified by slot, not just by name. Even if the owner renamed the item, filtering still works.

In the Steam API, the display name of the tag is usually in:

```python
localized_tag_name
```

not necessarily in the `name` field. For handling tags, it's recommended to use:

```python
name = str(
    tag.get("localized_tag_name")
    or tag.get("name")
    or ""
).lower()
)
```

---

## ⏱ Request Rate Limiting

The script does not attempt to bypass Steam limitations.

| HTTP Code | Meaning | Script Action |
|---|---|---|
| `200` | Inventory successfully retrieved | Processes items |
| `403` | Access to inventory forbidden | Skips profile immediately |
| `429` | Too many requests | Waits **80 seconds**, retries (up to 3 attempts total) |
| Other | Request/server error | Logs and skips profile |

Sequential checking parameters are set in `main()`:

```python
items = await parser.parse_profiles(
    steamids,
    max_concurrent=1,
    delay=4.0,
)
```

It's recommended to keep `max_concurrent=1` — reduces the likelihood of `429`.

> **Why 80 seconds?** This pause was tested against various values (120/90/70/80) — 80s is the sweet spot to reliably bypass the 429 limit.

---

## 🧮 Excel and SteamID64

SteamID64 consists of 17 digits. Excel might display it in scientific notation:

```
7.65612E+16
```

and lose precision when saving again.

When importing CSV, specify **Text** format for the `SteamID` column.

To enable filtering in Excel:
1. Open `steam_output.csv`
2. Select any cell in the table
3. Open the **Data** tab
4. Click **Filter**
5. When sorting, enable **My data has headers**

---

## 📸 Screenshots

### Successful Scan Log

<table>
  <tr>
    <td align="center"><img src="screenshots/successful_scan_log_1.png" width="460"/></td>
    <td align="center"><img src="screenshots/successful_scan_log_2.png" width="460"/></td>
  </tr>
</table>

### CSV Output Example

<p align="center"><img src="screenshots/csv_output_example.png" width="700"/></p>

---

## 📁 Project Structure

```text
steam-dota2-inventory-parser/
├── steam_parser.py
├── steamids.txt.example
├── requirements.txt
├── README.md
├── .gitignore
└── screenshots/
    ├── successful_scan_log_1.png
    ├── successful_scan_log_2.png
    └── csv_output_example.png
```

Generated at runtime (not committed):

```text
steam_output.csv
steam_cache.json
```

---

## 📝 Notes

- The script only sees public inventories.
- HTTP `403` might mean private inventory, access restriction, or unavailable profile; it's not necessarily an account ban.
- Item states are current only at scan time: an item might be bought, sold, or traded afterwards.
- Custom item names might display incorrectly with encoding issues, but filtering by technical Steam tags isn't affected.
- Don't publish personal SteamID lists, tokens, cookies, or other private data in GitHub repositories.

---

## ⚠️ Disclaimer

Use the project at your own risk and comply with Steam rules, public endpoint limitations, and applicable platform regulations.
