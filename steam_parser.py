"""
steam_parser.py

Educational Steam inventory parser for Dota 2 profiles.

Features:
- Reads a list of SteamIDs from steamids.txt
- Fetches Dota 2 inventories via Steam's public inventory endpoint
- Caches responses for CACHE_TTL_DAYS
- Extracts interesting items based on:
  - Quality: Auspicious, Genuine, Unusual, Corrupted, Autographed, Inscribed
  - Rarity: Arcana
  - Type: Courier
  - Slot: Summoned Unit
  - Gem flag: items whose text suggests a meaningful gem modifier
    (ignoring empty sockets and purely statistical counters)
  - Hero filter: only 13 heroes with valuable gems + Couriers

Output:
- Prints CSV to stdout AND saves to steam_output.csv
"""

import asyncio
import aiohttp
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timedelta


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("steam-parser")


STEAM_INVENTORY_URL = "https://steamcommunity.com/inventory/{steamid}/570/2?l=english&count=2000"
CACHE_FILE = Path("steam_cache.json")
OUTPUT_FILE = Path("steam_output.csv")
CACHE_TTL_DAYS = 7


INTERESTING_QUALITIES = {
    "auspicious",
    "genuine",
    "unusual",
    "corrupted",
    "autographed",
    "inscribed",
}


COURIER_TYPE_KEYWORDS = ("courier",)
SUMMONED_SLOT_KEYWORDS = ("summoned unit", "призванное существо")
TARGET_ITEM_NAMES = {
    "almond the frondillo",
}
ARCANA_RARITY_KEYWORDS = ("arcana", "rarity_arcana")


# Empty sockets
IGNORE_GEM_PATTERNS = (
    "empty socket general",
    "empty socket",
    "socket empty",
)


# Pure stat gems (run counters, first blood stats, etc.)
IGNORE_GEM_STAT_PATTERNS = (
    "team first blood, tower or roshan",
    "ti8 rune",
    "ti7 rune",
    "ti rune",
    "games watched:",
    "omnislash kills:",
    "rune of the bladeform legacy",
)


# Meaningful gem modifiers
INTERESTING_GEM_PATTERNS = (
    "kinetic gem",
    "prismatic gem",
    "corrupted gem",
    "inscribed gem",
)


# 12 heroes with valuable gems
GEM_HEROES = {
    "doom",
    "juggernaut",
    "kunkka",
    "phantom lancer",
    "puck",
    "pudge",
    "sven",
    "techies",
    "terrorblade",
    "tusk",
    "wraith king",
    "dragon knight",
}


class SteamProfileParser:
    """
    Main parser class:
    - fetches inventories
    - extracts interesting items
    """


    def __init__(self) -> None:
        self.cache: Dict[str, Any] = {}


    # -------------------------- Cache management -------------------------- #


    def _load_cache(self) -> None:
        if CACHE_FILE.exists():
            try:
                data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
                self.cache = data.get("profiles", {})
                log.info("Loaded cache with %d profiles", len(self.cache))
            except Exception as e:
                log.warning("Failed to load cache: %s", e)
                self.cache = {}


    def _save_cache(self) -> None:
        try:
            CACHE_FILE.write_text(
                json.dumps(
                    {"profiles": self.cache, "updated_at": datetime.now().isoformat()},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            log.warning("Failed to save cache: %s", e)


    def _is_cache_valid(self, profile_data: Dict[str, Any]) -> bool:
        cached_at = profile_data.get("cached_at")
        if not cached_at:
            return False


        try:
            cached_time = datetime.fromisoformat(cached_at)
            return datetime.now() - cached_time < timedelta(days=CACHE_TTL_DAYS)
        except Exception:
            return False


    # -------------------------- HTTP fetching -------------------------- #


    async def fetch_profile(
        self, session: aiohttp.ClientSession, steamid: str
    ) -> Dict[str, Any] | None:
        """
        Returns inventory profile for given SteamID.

        Logic:
        - If profile is cached and still valid, return it.
        - Otherwise, request Steam inventory endpoint.
        - On HTTP 429 (Too Many Requests), waits and retries up to 3 times.
        - On success, cache the profile and return it.
        """

        url = STEAM_INVENTORY_URL.format(steamid=steamid)
        retry_pause = 80  # seconds to wait on 429 before retrying
        max_retries = 3

        for attempt in range(max_retries):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 429:
                        if attempt < max_retries - 1:
                            log.warning(
                                "HTTP 429 for profile %s (attempt %d/%d), waiting %d seconds",
                                steamid,
                                attempt + 1,
                                max_retries,
                                retry_pause,
                            )
                            await asyncio.sleep(retry_pause)
                            continue  # Retry
                        else:
                            log.warning(
                                "HTTP 429 for profile %s: all %d retries exhausted, skipping",
                                steamid,
                                max_retries,
                            )
                            return None

                    elif resp.status == 403:
                        log.debug("Profile %s returned 403 (private/banned), skipping", steamid)
                        return None

                    elif resp.status != 200:
                        log.warning(
                            "Failed to fetch profile %s: status=%s",
                            steamid,
                            resp.status,
                        )
                        return None
                    else:
                        data = await resp.json()
                        break  # Success!

            except asyncio.TimeoutError:
                log.warning("Timeout fetching profile %s (attempt %d/%d)", steamid, attempt + 1, max_retries)
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_pause)
                    continue
                return None
            except Exception as e:
                log.exception("Error fetching profile %s: %s", steamid, e)
                return None

        profile_data = {
            "steamid": steamid,
            "cached_at": datetime.now().isoformat(),
            "assets": data.get("assets", []),
            "descriptions": data.get("descriptions", []),
        }

        log.info(
            "Fetched and cached profile: %s (assets=%d, descriptions=%d)",
            steamid,
            len(profile_data["assets"]),
            len(profile_data["descriptions"]),
        )
        return profile_data


    # -------------------------- Helpers for tags -------------------------- #


    @staticmethod
    def _build_desc_map(descriptions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {
            f"{d.get('classid')}_{d.get('instanceid')}": d
            for d in descriptions
        }


    @staticmethod
    def _extract_tags(desc: Dict[str, Any]) -> List[Dict[str, Any]]:
        return desc.get("tags") or []


    @staticmethod
    def _extract_quality(tags: List[Dict[str, Any]]) -> str:
        for tag in tags:
            category = str(tag.get("category", "")).lower()
            name = str(
    tag.get("localized_tag_name")
    or tag.get("name")
    or ""
).lower()
            internal = str(tag.get("internal_name", "")).lower()


            if "quality" in category:
                for q in INTERESTING_QUALITIES:
                    if q in name or q in internal:
                        return q.capitalize()


        return ""


    @staticmethod
    def _extract_rarity(tags: List[Dict[str, Any]]) -> str:
        for tag in tags:
            category = str(tag.get("category", "")).lower()
            name = str(
    tag.get("localized_tag_name")
    or tag.get("name")
    or ""
).lower()
            internal = str(tag.get("internal_name", "")).lower()


            if "rarity" in category:
                if any(kw in name for kw in ARCANA_RARITY_KEYWORDS) or any(
                    kw in internal for kw in ARCANA_RARITY_KEYWORDS
                ):
                    return "Arcana"


        return ""


    @staticmethod
    def _extract_type(tags: List[Dict[str, Any]]) -> str:
        for tag in tags:
            category = str(tag.get("category", "")).lower()
            name = str(
    tag.get("localized_tag_name")
    or tag.get("name")
    or ""
).lower()
            internal = str(tag.get("internal_name", "")).lower()


            if "type" in category:
                if any(marker in name for marker in COURIER_TYPE_KEYWORDS) or any(
                    marker in internal for marker in COURIER_TYPE_KEYWORDS
                ):
                    return "Courier"


        return ""


    @staticmethod
    def _extract_slot(tags: List[Dict[str, Any]]) -> str:
        for tag in tags:
            category = str(tag.get("category", "")).lower()
            internal = str(tag.get("internal_name", "")).lower()
            localized_name = str(
                tag.get("localized_tag_name")
                or tag.get("name")
                or ""
            ).lower()


            if category == "slot" and (
                internal == "summon"
                or localized_name == "summoned unit"
            ):
                return "Summoned Unit"


        return ""
    
    @staticmethod
    def _is_target_item(desc: Dict[str, Any]) -> bool:
        names_to_check = (
            desc.get("name"),
            desc.get("market_hash_name"),
        )


        for value in names_to_check:
            if not isinstance(value, str):
                continue


            normalized_name = " ".join(value.lower().split())


            if normalized_name in TARGET_ITEM_NAMES:
                return True


        return False
    
    @staticmethod
    def _extract_gem_flag(desc: Dict[str, Any]) -> bool:
        """
        Gem flag with priority:


        1. Build blob from name, market_hash_name, descriptions.
        2. If blob contains any INTERESTING_GEM_PATTERNS -> True.
        3. Else if blob contains IGNORE_GEM_PATTERNS or IGNORE_GEM_STAT_PATTERNS -> False.
        4. Else if blob contains 'gem' -> True.
        5. Else -> False.
        """
        parts: List[str] = []


        for key in ("name", "market_hash_name"):
            value = desc.get(key)
            if isinstance(value, str):
                parts.append(value)


        extra_desc = desc.get("descriptions") or []
        for entry in extra_desc:
            if isinstance(entry, dict):
                value = entry.get("value")
                if isinstance(value, str):
                    parts.append(value)


        blob = " ".join(parts).lower()


        if any(pattern in blob for pattern in INTERESTING_GEM_PATTERNS):
            return True


        if any(ignore in blob for ignore in IGNORE_GEM_PATTERNS):
            return False
        if any(ignore in blob for ignore in IGNORE_GEM_STAT_PATTERNS):
            return False


        return "gem" in blob


    @staticmethod
    def _extract_hero(desc: Dict[str, Any]) -> str:
        """
        Extract hero name from item description.
        """
        # Check in tags
        tags = desc.get("tags") or []
        for tag in tags:
            category = str(tag.get("category", "")).lower()
            name = str(
                tag.get("localized_tag_name")
                or tag.get("name")
                or ""
            ).lower()
            internal = str(tag.get("internal_name", "")).lower()


            if "hero" in category or "class" in category:
                # Return first word (hero name)
                hero_name = name.split()[0] if name else ""
                if hero_name:
                    return hero_name.capitalize()


        # Check in name/market_hash_name
        for key in ("name", "market_hash_name"):
            value = desc.get(key)
            if isinstance(value, str):
                # Try to extract hero name from item name
                # Example: "Juggernaut's Blade" -> "Juggernaut"
                parts = value.lower().split()
                if parts:
                    hero_candidate = parts[0].capitalize()
                    if hero_candidate.lower() in GEM_HEROES:
                        return hero_candidate


        return ""


    # -------------------------- Trade info -------------------------- #


    @staticmethod
    def _extract_trade_info(asset: Dict[str, Any]) -> Dict[str, str]:
        restriction = asset.get("market_tradable_restriction")
        tradable_after = asset.get("tradable_after")


        flags = []
        if restriction is not None:
            flags.append(f"restriction={restriction}")


        return {
            "trade_flags": ",".join(flags),
            "tradable_after": str(tradable_after) if tradable_after is not None else "",
        }


    # -------------------------- Main extraction -------------------------- #


    def extract_interesting_items(
        self, profile_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        assets = profile_data.get("assets", [])
        descriptions = profile_data.get("descriptions", [])


        desc_map = self._build_desc_map(descriptions)
        results: List[Dict[str, Any]] = []


        for asset in assets:
            classid = asset.get("classid")
            instanceid = asset.get("instanceid")
            if not classid:
                continue


            desc_key = f"{classid}_{instanceid}"
            desc = desc_map.get(desc_key, {})


            item_name = desc.get("name", "Unknown")
            is_target_item = self._is_target_item(desc)


            tags = self._extract_tags(desc)


            quality = self._extract_quality(tags)
            rarity = self._extract_rarity(tags)
            item_type = self._extract_type(tags)
            slot = self._extract_slot(tags)
            has_gem = self._extract_gem_flag(desc)
            hero = self._extract_hero(desc)


            if is_target_item:
                slot = "Summoned Unit"


            # Filter: only 13 heroes with gems OR couriers
            should_include = False


            # Couriers (by type)
            if item_type == "Courier":
                should_include = True


            # Heroes with gems (only 13 specified)
            elif has_gem and hero.lower() in GEM_HEROES:
                should_include = True


            # Target items (Almond, etc.)
            elif is_target_item:
                should_include = True


            # Other interesting items (quality, rarity, slot)
            elif any([quality, rarity, slot]):
                should_include = True


            if not should_include:
                continue


            trade_info = self._extract_trade_info(asset)


            results.append(
                {
                    "steamid": profile_data.get("steamid"),
                    "name": item_name,
                    "quality": quality,
                    "rarity": rarity,
                    "type": item_type,
                    "slot": slot,
                    "hero": hero,
                    "has_gem": "yes" if has_gem else "",
                    "trade_flags": trade_info["trade_flags"],
                    "tradable_after": trade_info["tradable_after"],
                }
            )


        return results


    # -------------------------- Parsing profiles -------------------------- #


    async def parse_profiles(
        self, steamids: List[str], max_concurrent: int = 1, delay: float = 4.0
    ) -> List[Dict[str, Any]]:
        async def fetch_with_delay(
            steamid: str, semaphore: asyncio.Semaphore, session: aiohttp.ClientSession
        ) -> Dict[str, Any] | None:
            async with semaphore:
                profile = await self.fetch_profile(session, steamid)
                await asyncio.sleep(delay)
                return profile


        async with aiohttp.ClientSession() as session:
            semaphore = asyncio.Semaphore(max_concurrent)
            tasks = [
                fetch_with_delay(steamid, semaphore, session)
                for steamid in steamids
            ]
            profiles = await asyncio.gather(*tasks, return_exceptions=True)


        all_items: List[Dict[str, Any]] = []


        for profile_data in profiles:
            if isinstance(profile_data, Exception):
                continue
            if profile_data is None:
                continue


            items = self.extract_interesting_items(profile_data)
            all_items.extend(items)


        log.info(
            "Parsed %d profiles, found %d interesting items",
            len([p for p in profiles if not isinstance(p, Exception)]),
            len(all_items),
        )


        return all_items


# -------------------------- Script entrypoint -------------------------- #


async def main() -> None:
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    steamids_file = Path("steamids.txt")
    
    if not steamids_file.exists():
        log.error("steamids.txt not found. Create it with one SteamID64 per line.")
        return
    
    steamids = [
        line.strip()
        for line in steamids_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    
    if not steamids:
        log.error("No SteamIDs found in steamids.txt")
        return
    
    log.info("Loaded %d SteamIDs from steamids.txt", len(steamids))
    
    parser = SteamProfileParser()
    items = await parser.parse_profiles(steamids, max_concurrent=1, delay=4.0)
    
    # CSV header
    csv_header = "SteamID;Name;Quality;Rarity;Type;Slot;Hero;HasGem;TradeFlags;TradableAfter;ProfileURL"
    csv_lines = [csv_header]
    
    for item in items:
        steamid = item["steamid"]
        name = item["name"].replace(";", ",")
        quality = item["quality"]
        rarity = item["rarity"]
        item_type = item["type"]
        slot = item["slot"]
        hero = item["hero"]
        has_gem = item["has_gem"]
        trade_flags = item["trade_flags"]
        tradable_after = item["tradable_after"]
        profile_url = f"https://steamcommunity.com/profiles/{steamid}/inventory"
        
        csv_line = (
            f"{steamid};{name};{quality};{rarity};{item_type};{slot};{hero};"
            f"{has_gem};{trade_flags};{tradable_after};{profile_url}"
        )
        csv_lines.append(csv_line)
    
    # Save to file
    try:
        OUTPUT_FILE.write_text("\n".join(csv_lines), encoding="utf-8")
        log.info("Saved %d items to %s", len(items), OUTPUT_FILE)
    except PermissionError:
        log.error("File %s is open in another program. Close it and run again.", OUTPUT_FILE)
    
    # Also print to stdout
    print(csv_header)
    for line in csv_lines[1:]:
        print(line)
    
    log.info("Total interesting items: %d", len(items))


if __name__ == "__main__":
    asyncio.run(main())
