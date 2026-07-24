import sys
import shutil
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parents[1]
CORE_DIR = PARENT_DIR / "00_System"

if str(CORE_DIR) not in sys.path:
    sys.path.append(str(CORE_DIR))

from database import get_db_connection

class ExamPassFailImporter:
    def __init__(self):
        self.root_dir = PARENT_DIR
        self.reports_dir = self.root_dir / "01_inbox" / "reports"
        self.processed_dir = self.root_dir / "01_inbox" / "processed"

    def run(self) -> Dict[str, Any]:
        report = {"success": True, "files_processed": 0, "records_loaded": 0, "errors": []}

        # Create directories if they are missing
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        # Grab pending Excel files containing "pass" or "fail" in the name
        files = [
            f for f in self.reports_dir.iterdir() 
            if f.suffix == ".xlsx" 
            and not f.name.startswith("~$") 
            and ("pass" in f.name.lower() or "fail" in f.name.lower())
        ]

        if not files:
            report["errors"].append("No pending 'Exam Pass Fail' .xlsx files found in 01_inbox/reports/.")
            report["success"] = False
            return report

        conn = get_db_connection()
        cursor = conn.cursor()

        for file_path in files:
            try:
                # Open with self-releasing context manager
                with pd.ExcelFile(str(file_path)) as xls:
                    df = pd.read_excel(xls, sheet_name=xls.sheet_names[0])

                # 1. Isolate row content (data starts at row index 5)
                data_rows = df.iloc[5:].copy()

                # 2. Extract relative column positions
                col_indices = [0, 3, 4, 7, 9, 11, 13, 14, 15, 16, 17]
                df_subset = data_rows.iloc[:, col_indices].copy()
                df_subset.columns = [
                    "trade", "period", "classification", "exam_type", 
                    "exam_name", "ref_ver", "supp", "pass_count", 
                    "fail_count", "no_stat_count", "total_count"
                ]

                # 3. Clean trailing metadata and report summary lines
                df_subset = df_subset[
                    ~df_subset['trade'].astype(str).str.contains('Report Total|ATOMS Management Reports|Requested by:', case=False, na=True)
                ]

                # 4. Filter out nested sub-total summary rows
                df_subset = df_subset[
                    ~df_subset['period'].astype(str).str.contains('Total', case=False, na=True)
                ]

                # 5. Forward-fill nested merged structural cell groups
                df_subset['trade'] = df_subset['trade'].ffill().str.strip()
                df_subset['period'] = pd.to_numeric(df_subset['period'], errors='coerce').ffill().astype(int)
                df_subset['classification'] = df_subset['classification'].ffill().str.strip()
                df_subset['exam_type'] = df_subset['exam_type'].ffill().str.strip()

                # 6. Normalize numerical counts
                for col in ["supp", "pass_count", "fail_count", "no_stat_count", "total_count"]:
                    df_subset[col] = pd.to_numeric(df_subset[col], errors='coerce').fillna(0).astype(int)

                # 7. Execute bulk database transactions
                records_to_insert = []
                for _, r in df_subset.iterrows():
                    records_to_insert.append((
                        str(r["trade"]), int(r["period"]), str(r["classification"]), 
                        str(r["exam_type"]), str(r["exam_name"]), str(r["ref_ver"]),
                        int(r["supp"]), int(r["pass_count"]), int(r["fail_count"]), 
                        int(r["no_stat_count"]), int(r["total_count"])
                    ))

                cursor.executemany("""
                    INSERT OR REPLACE INTO exam_pass_fail_aggregates (
                        trade, period, classification, exam_type, exam_name, ref_ver,
                        supp_count, pass_count, fail_count, no_stat_count, total_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, records_to_insert)

                conn.commit()

                # 8. Archive the completed sheet with timestamp protection
                dest_path = self.processed_dir / file_path.name
                if dest_path.exists():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    dest_path = self.processed_dir / f"{file_path.stem}_{timestamp}{file_path.suffix}"

                shutil.move(str(file_path), str(dest_path))

                report["files_processed"] += 1
                report["records_loaded"] += len(records_to_insert)

            except Exception as e:
                conn.rollback()
                report["errors"].append(f"Error processing {file_path.name}: {str(e)}")
                report["success"] = False

        conn.close()
        return report


if __name__ == "__main__":
    importer = ExamPassFailImporter()
    print(importer.run())