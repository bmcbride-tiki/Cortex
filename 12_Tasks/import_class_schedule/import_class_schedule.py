import sys
import re
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from lxml import html

CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parents[1]
CORE_DIR = PARENT_DIR / "00_System"

if str(CORE_DIR) not in sys.path:
    sys.path.append(str(CORE_DIR))

from database import get_db_connection

CATALOGUE_URL = "https://tradesecrets.alberta.ca/apprentice-services/classroom-instruction/training-catalogue/"


class ClassScheduleScraper:
    def __init__(self, school_year: str):
        self.school_year = school_year.strip()
        self.start_year = self._parse_start_year(self.school_year)
        self.output_dir = CURRENT_DIR / "output"

    @staticmethod
    def _parse_start_year(school_year: str) -> int:
        match = re.match(r"^(\d{4})-(\d{4})$", school_year)
        if not match:
            raise ValueError(f"School year must be in 'YYYY-YYYY' format, got '{school_year}'")
        start, end = int(match.group(1)), int(match.group(2))
        if end != start + 1:
            raise ValueError(f"'{school_year}' is not a consecutive school year range")
        return start

    @staticmethod
    def _parse_date_range(raw_text: str) -> Optional[Dict[str, str]]:
        parts = [p.strip() for p in raw_text.split(" - ")]
        if len(parts) != 2:
            return None
        try:
            start_date = datetime.strptime(parts[0], "%B %d, %Y").strftime("%Y-%m-%d")
            end_date = datetime.strptime(parts[1], "%B %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            return None
        return {"start_date": start_date, "end_date": end_date}

    def _get_trade_catalogue(self) -> List[Dict[str, str]]:
        """Scrape the base catalogue page for the full {trade name -> trade code} listing."""
        resp = requests.get(CATALOGUE_URL, timeout=30)
        resp.raise_for_status()
        tree = html.fromstring(resp.text)

        trades = []
        seen_codes = set()
        for row in tree.xpath("//tr"):
            cells = row.xpath("./td")
            if len(cells) < 2:
                continue
            name = cells[0].text_content().strip()
            if not name:
                continue

            code = None
            for href in row.xpath(".//a/@href"):
                match = re.search(r"Trade=(\w+)&Year=\d+", href)
                if match:
                    code = match.group(1)
                    break

            if code and code not in seen_codes:
                seen_codes.add(code)
                trades.append({"trade": name, "trade_code": code})

        return trades

    def _scrape_trade(self, trade: str, trade_code: str) -> List[Dict[str, Any]]:
        url = f"{CATALOGUE_URL}?Trade={trade_code}&Year={self.start_year}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        tree = html.fromstring(resp.text)

        records = []
        current_campus = None

        for provider_h1 in tree.xpath("//h1"):
            provider_name = provider_h1.text_content().strip()
            if not provider_name:
                continue
            current_campus = None

            for sib in provider_h1.itersiblings():
                if sib.tag == "h1":
                    break
                if sib.tag != "table":
                    continue

                if sib.get("class") == "class-schedule":
                    rows = sib.xpath(".//tr")
                    if not rows:
                        continue

                    headers = [th.text_content().strip().lower() for th in rows[0].xpath("./th")]
                    col = {name: i for i, name in enumerate(headers) if name}
                    period_idx = col.get("period", 1)
                    date_idx = col.get("class date", 2)
                    code_idx = col.get("class code", 4)

                    for row in rows[1:]:
                        cells = row.xpath("./td")
                        needed = max(period_idx, date_idx, code_idx)
                        if len(cells) <= needed:
                            continue

                        period_match = re.search(r"(\d+)", cells[period_idx].text_content())
                        class_code_text = cells[code_idx].text_content().strip()
                        date_range = self._parse_date_range(cells[date_idx].text_content().strip())

                        if not period_match or not date_range or not class_code_text.isdigit():
                            continue

                        records.append({
                            "school_year": self.school_year,
                            "trade": trade,
                            "trade_code": trade_code,
                            "training_provider": provider_name,
                            "campus": current_campus or "Main Campus",
                            "period": int(period_match.group(1)),
                            "class_code": int(class_code_text),
                            "start_date": date_range["start_date"],
                            "end_date": date_range["end_date"],
                        })
                else:
                    campus_text = sib.xpath(".//h2//a/text()")
                    if campus_text:
                        current_campus = campus_text[0].strip()

        return records

    def run(self) -> Dict[str, Any]:
        report = {"success": True, "school_year": self.school_year, "trades_scraped": 0, "classes_found": 0, "errors": []}

        trade_catalogue = self._get_trade_catalogue()
        if not trade_catalogue:
            report["success"] = False
            report["errors"].append("No trades found on the training catalogue page.")
            return report

        all_records: List[Dict[str, Any]] = []
        for entry in trade_catalogue:
            try:
                records = self._scrape_trade(entry["trade"], entry["trade_code"])
                all_records.extend(records)
                report["trades_scraped"] += 1
            except Exception as e:
                report["errors"].append(f"Failed to scrape '{entry['trade']}' ({entry['trade_code']}): {str(e)}")
            time.sleep(0.2)

        report["classes_found"] = len(all_records)

        # Write the scraped records to a JSON file for reference
        self.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.output_dir / f"{self.school_year}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_records, f, indent=2)
        report["json_path"] = str(json_path)

        # Load into brain_state.db
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            rows = [
                (r["school_year"], r["trade"], r["trade_code"], r["training_provider"], r["campus"],
                 r["period"], r["class_code"], r["start_date"], r["end_date"])
                for r in all_records
            ]
            cursor.executemany("""
                INSERT OR REPLACE INTO class_schedules
                (school_year, trade, trade_code, training_provider, campus, period, class_code, start_date, end_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, rows)
            conn.commit()
            report["classes_loaded"] = len(rows)
        except Exception as e:
            conn.rollback()
            report["success"] = False
            report["errors"].append(f"Database load failure: {str(e)}")
        finally:
            conn.close()

        if report["errors"]:
            report["success"] = False if not all_records else report["success"]

        return report


def _prompt_school_year() -> str:
    while True:
        value = input("Enter the school year (format YYYY-YYYY, e.g. 2026-2027): ").strip()
        try:
            ClassScheduleScraper._parse_start_year(value)
            return value
        except ValueError as e:
            print(f"  {e}. Try again.")


if __name__ == "__main__":
    school_year_input = sys.argv[1] if len(sys.argv) > 1 else _prompt_school_year()
    scraper = ClassScheduleScraper(school_year_input)
    print(scraper.run())
