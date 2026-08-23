# Steam Dota 2 Inventory Parser

A small Python script for sequentially checking public Dota 2 Steam inventories and exporting items of interest to CSV.

The script reads a list of SteamID64 from `steamids.txt`, requests public Dota 2 inventory, and saves only items that match at least one specified filter to a table.

> This project is intended to work only with publicly available Steam data.  
> The script does not buy, sell, or exchange items or accounts.

## Features

- Reads SteamID64 from `steamids.txt`
- Checks public Dota 2 inventories via Steam Community Inventory API
- Works sequentially with configurable pause between profiles
- On HTTP `429 Too Many Requests`, waits 90 seconds and retries the request once
- On HTTP `403 Forbidden`, skips the profile immediately
- Exports results to CSV for Excel
- Finds items based on the following conditions:
  - **Quality**: `Auspicious`, `Genuine`, `Unusual`, `Corrupted`, `Autographed`, `Inscribed`
  - **Rarity**: `Arcana`
  - **Type**: `Courier`
  - **Slot**: `Summoned Unit`
  - **Hero + Gem**: Only 13 heroes with valuable gems (Doom, Juggernaut, Kunkka, Phantom Lancer, Puck, Pudge, Sven, Techies, Terrorblade, Tusk, Wraith King)
  - **Target Items**: `YOUR ITEM` and similar
- Correctly detects items with `Summoned Unit` slot, including **Maraxiform's Fallen**
- Independent of displayed item name: renaming an instance doesn't interfere with slot determination

## Requirements

- Python 3.10+
- Access to public Steam Community inventories
- `aiohttp` library

## Installation

Clone the repository:

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

Install dependencies:

```bash
pip install aiohttp
```

## Preparing SteamID List

Create a file `steamids.txt` in the script folder.

One SteamID64 per line:

```text
76561198000000001
76561198000000002
76561198000000003
```

Lines starting with `#` are ignored:

```text
# Test profiles
76561198000000001
76561198000000002
```

Use SteamID64 specifically, not a profile link or account short name.

## Running

### Windows PowerShell

```powershell
.\.venv\Scripts\python.exe .\steam_parser.py > steam_output.csv
```

### Regular Run

```bash
python steam_parser.py > steam_output.csv
```

After completion, a file will appear:

```text
steam_output.csv
```

## CSV Columns

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
| `TradableAfter` | Time when the item becomes tradable again, if provided by Steam |
| `ProfileURL` | Link to the profile inventory |

## Hero + Gem Filter

The script now filters items by **13 heroes with valuable gems**:

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

Only items from these heroes **with gems** are included in the results.

Couriers and target items (e.g. `Not stated`) are still included regardless of hero.

## Summoned Unit Filtering

For items in the `Summoned Unit` slot, the Steam API tag is used:

```text
category = Slot
internal_name = summon
localized_tag_name = Summoned Unit
```

For example, `Maraxiform's Fallen` is identified by slot, not just by name. Therefore, even if the owner has renamed the item, filtering should still work.

In the Steam API, the display name of the tag is usually in the field:

```python
localized_tag_name
```

not necessarily in the `name` field.

For handling tags, it's recommended to use:

```python
name = str(
    tag.get("localized_tag_name")
    or tag.get("name")
    or ""
).lower()
```

## Request Rate Limiting

The script does not attempt to bypass Steam's limitations.

Current behavior:

| HTTP Code | Meaning | Script Action |
|---|---|---|
| `200` | Inventory successfully retrieved | Processes items |
| `403` | Access to inventory forbidden | Skips profile immediately |
| `429` | Too many requests | Waits 120 seconds and retries the request once |
| Other code | Request/server error | Logs and skips profile |

Sequential checking parameters are set in `main()`:

```python
items = await parser.parse_profiles(
    steamids,
    max_concurrent=1,
    delay=4.0,
)
```

It's recommended to keep:

```python
max_concurrent=1
```

This reduces the likelihood of getting `429 Too Many Requests`.

## Excel and SteamID64

SteamID64 consists of 17 digits. Excel might display it in scientific notation, for example:

```text
7.65612E+16
```

and lose precision when saving again.

When importing CSV, specify **Text** format for the `SteamID` column.

To enable filtering in Excel:

1. Open `steam_output.csv`
2. Select any cell in the table
3. Open the **Data** tab
4. Click **Filter**
5. When sorting, enable the option **My data has headers**

## Screenshots

### Successful Scan Log

<img width="1087" height="346" alt="pHUqBBEqGR" src="https://github.com/user-attachments/assets/bb14b1a3-ac54-4736-a540-3378b3405532" />


### CSV Output Example



## Notes

- The script only sees public inventories.
- HTTP `403` might mean private inventory, access restriction, or unavailable profile; it's not necessarily an account ban.
- Item states are current only at the time of request: an item might be bought, sold, or traded after scanning.
- Custom item names might display incorrectly with encoding issues, but filtering by technical Steam tags isn't affected by this.
- Don't publish personal SteamID lists, tokens, cookies, or other private data in GitHub repositories.

## Project Structure

```text
steam-dota2-inventory-parser/
├── steam_parser.py
├── steamids.txt.example
├── requirements.txt
├── README.md
├── .gitignore
└── screenshots/
    ├── successful_scan_log.png
    └── csv_output_example.png
```

## requirements.txt

Create a `requirements.txt` file:

```text
aiohttp>=3.9
```

Installing dependencies would then look like:

```bash
pip install -r requirements.txt
```

## .gitignore

Create a `.gitignore` to avoid committing personal data and scan results to GitHub:

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
venv/
# Local input/output
steamids.txt
steam_output.csv
steam_cache.json
# Logs
*.log
# IDE
.vscode/
.idea/
# Screenshots (optional)
screenshots/*.png
```

## License

Use the project at your own risk and comply with Steam rules, public endpoint limitations, and applicable platform regulations.
