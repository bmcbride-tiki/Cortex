# =============================================================================
# import_marks_correlation.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A zero-input Task: picks up pending "Marks Correlation" .xlsx reports
#   (their "Section Scores Details" sheet) from `01_inbox/reports/`,
#   derives training classes / exam attempts / per-section scores from
#   the raw rows (including detecting re-written exam attempts by
#   chronologically ranking each student's attempts per class), and loads
#   all three into their matching tables. Archives each processed file
#   into `01_inbox/processed/`.
#
# WHAT IT INTERACTS WITH
#   - `01_inbox/reports/` (or a caller-supplied override folder via
#     `reports_dir_override`), read for pending `.xlsx` files;
#     `01_inbox/processed/`, where they're archived.
#   - `00_System/database.py`'s `get_db_connection()`, writing to
#     `training_classes`, `apprentice_exam_attempts`, and
#     `apprentice_section_scores`.
#   - `pandas`/`numpy`, for reading, cleaning, and rank-computing over the
#     Excel sheet.
# =============================================================================

import sys
import shutil
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parents[1]
CORE_DIR = PARENT_DIR / "00_System"

if str(CORE_DIR) not in sys.path:
    sys.path.append(str(CORE_DIR))

from database import get_db_connection

class MarksCorrelationImporter:
    def __init__(self, reports_dir_override: Optional[str] = None):
        self.root_dir = PARENT_DIR
        self.using_override = bool(reports_dir_override)
        self.reports_dir = Path(reports_dir_override) if reports_dir_override else (self.root_dir / "01_inbox" / "reports")
        self.processed_dir = self.root_dir / "01_inbox" / "processed"

    def _robust_extract_period(self, exam_name: Any) -> int:
        """Parses the training Period out of Exam Name fields."""
        if pd.isna(exam_name):
            return 0
        name_str = str(exam_name).strip()
        parts = name_str.split('/') if '/' in name_str else name_str.split('-')
        
        if len(parts) >= 2:
            p_str = parts[1].strip()
            if len(p_str) == 2 and p_str.startswith('0'):
                return int(p_str[1])
            elif p_str.isdigit():
                return int(p_str)
        return 0

    def run(self) -> Dict[str, Any]:
        report = {"success": True, "files_processed": 0, "classes_loaded": 0, "attempts_loaded": 0, "scores_loaded": 0, "errors": []}

        if self.using_override:
            if not self.reports_dir.exists():
                report["errors"].append(f"Reports folder does not exist: {self.reports_dir}")
                report["success"] = False
                return report
        else:
            self.reports_dir.mkdir(parents=True, exist_ok=True)

        self.processed_dir.mkdir(parents=True, exist_ok=True)

        files = [f for f in self.reports_dir.iterdir() if f.suffix == ".xlsx" and not f.name.startswith("~$")]

        if not files:
            report["errors"].append(f"No pending Marks Correlation .xlsx files found in {self.reports_dir}.")
            report["success"] = False
            return report

        conn = get_db_connection()
        cursor = conn.cursor()

        for file_path in files:
            try:
                # 🔒 Context manager 'with' block opens AND releases the file lock immediately after loading
                with pd.ExcelFile(str(file_path)) as xls:
                    if 'Section Scores Details' not in xls.sheet_names:
                        report["errors"].append(f"Missing sheet 'Section Scores Details' in {file_path.name}")
                        continue

                    scores_df = pd.read_excel(xls, 'Section Scores Details')
                
                # File lock is now officially RELEASED by python. We can safely clean and manipulate the data.
                scores_clean = scores_df.dropna(subset=['Trade', 'Class Code', 'AITID']).copy()
                if scores_clean.empty:
                    continue

                scores_clean['Class Code'] = scores_clean['Class Code'].astype(int)
                scores_clean['AITID'] = scores_clean['AITID'].astype(int)
                scores_clean['Section'] = scores_clean['Section'].astype(float)
                scores_clean['Period'] = scores_clean['Exam Name'].apply(self._robust_extract_period)
                scores_clean['Exam Session End Date'] = pd.to_datetime(scores_clean['Exam Session End Date']).dt.strftime('%Y-%m-%d')

                # 2. Extract unique training classes
                classes_df = scores_clean[['Class Code', 'Training Provider', 'Trade', 'Period', 'Exam Name', 'Ref/Ver']].drop_duplicates(subset=['Class Code'])

                # 3. Chronologically sort and process rewrites
                scores_clean = scores_clean.sort_values(by=['Class Code', 'AITID', 'Exam Session End Date'])
                attempts_df = scores_clean[['Class Code', 'AITID', 'Exam Session End Date', 'Class Mark', 'AIT Exam Mark']].drop_duplicates()
                
                # Calculate attempts rank chronologically per class/student
                attempts_df['attempt_rank'] = attempts_df.groupby(['Class Code', 'AITID'])['Exam Session End Date'].rank(method='first').astype(int)
                attempts_df['is_rewrite'] = np.where(attempts_df['attempt_rank'] > 1, 1, 0)

                # 4. Transact Bulk Database Writes
                # Write Classes
                classes_data = [
                    (int(r["Class Code"]), str(r["Training Provider"]), str(r["Trade"]), int(r["Period"]), str(r["Exam Name"]), str(r["Ref/Ver"]))
                    for _, r in classes_df.iterrows()
                ]
                cursor.executemany("""
                    INSERT OR REPLACE INTO training_classes (class_code, training_provider, trade, period, exam_name, ref_ver)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, classes_data)

                # Write Attempts
                attempts_data = [
                    (int(r["Class Code"]), int(r["AITID"]), str(r["Exam Session End Date"]), 
                     float(r["Class Mark"]) if not pd.isna(r["Class Mark"]) else None,
                     float(r["AIT Exam Mark"]) if not pd.isna(r["AIT Exam Mark"]) else None,
                     int(r["is_rewrite"]))
                    for _, r in attempts_df.iterrows()
                ]
                cursor.executemany("""
                    INSERT OR REPLACE INTO apprentice_exam_attempts (class_code, ait_id, exam_date, class_mark, ait_exam_mark, is_rewrite)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, attempts_data)

                # Write Scores
                scores_data = [
                    (int(r["Class Code"]), int(r["AITID"]), str(r["Exam Session End Date"]), float(r["Section"]),
                     str(r["Class Section Name"]), str(r["Exam Section Name"]),
                     float(r["Class Section Mark"]) if not pd.isna(r["Class Section Mark"]) else None,
                     float(r["Exam Section Mark"]) if not pd.isna(r["Exam Section Mark"]) else None)
                    for _, r in scores_clean.iterrows()
                ]
                cursor.executemany("""
                    INSERT OR REPLACE INTO apprentice_section_scores (class_code, ait_id, exam_date, section, class_section_name, exam_section_name, class_section_mark, exam_section_mark)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, scores_data)

                conn.commit()

                # 🛡️ 5. Collision-Proof File Archive Move
                dest_path = self.processed_dir / file_path.name
                if dest_path.exists():
                    # If file_name already exists in processed, append a timestamp to prevent OS error
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    dest_path = self.processed_dir / f"{file_path.stem}_{timestamp}{file_path.suffix}"

                shutil.move(str(file_path), str(dest_path))
                
                report["files_processed"] += 1
                report["classes_loaded"] += len(classes_data)
                report["attempts_loaded"] += len(attempts_data)
                report["scores_loaded"] += len(scores_data)

            except Exception as e:
                conn.rollback()
                report["errors"].append(f"Failure processing {file_path.name}: {str(e)}")
                report["success"] = False

        conn.close()
        return report

if __name__ == "__main__":
    override_dir = sys.argv[1] if len(sys.argv) > 1 else None
    importer = MarksCorrelationImporter(override_dir)
    print(importer.run())