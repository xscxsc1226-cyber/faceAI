import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'local',
                interview_mode TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                summary TEXT,
                scores_json TEXT NOT NULL,
                highlights_json TEXT NOT NULL,
                raw_transcript_json TEXT NOT NULL,
                qa_playback_json TEXT NOT NULL,
                audio_objects_json TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                user_id TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                request_chars INTEGER NOT NULL,
                response_chars INTEGER NOT NULL,
                estimated_cost_usd REAL NOT NULL
            )
            """
        )

        # 轻量迁移，兼容旧版 schema。
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(interview_reports)").fetchall()
        }
        if "user_id" not in columns:
            conn.execute(
                "ALTER TABLE interview_reports ADD COLUMN user_id TEXT NOT NULL DEFAULT 'local'"
            )
        if "audio_objects_json" not in columns:
            conn.execute(
                "ALTER TABLE interview_reports ADD COLUMN audio_objects_json TEXT NOT NULL DEFAULT '[]'"
            )
        conn.commit()
    finally:
        conn.close()


def save_report(db_path: str, report: Dict[str, Any], user_id: str = "local") -> int:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO interview_reports (
                created_at, user_id, interview_mode, started_at, ended_at, summary,
                scores_json, highlights_json, raw_transcript_json, qa_playback_json, audio_objects_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now(),
                user_id,
                report.get("interview_mode", ""),
                report.get("started_at", ""),
                report.get("ended_at", ""),
                report.get("summary", ""),
                json.dumps(report.get("scores", {}), ensure_ascii=False),
                json.dumps(report.get("highlights", []), ensure_ascii=False),
                json.dumps(report.get("raw_transcript", []), ensure_ascii=False),
                json.dumps(report.get("qa_playback", []), ensure_ascii=False),
                json.dumps(report.get("audio_objects", []), ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def list_reports(db_path: str, user_id: str = "local", limit: int = 30) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, created_at, interview_mode, ended_at, summary
            FROM interview_reports
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_report(db_path: str, report_id: int, user_id: str = "local") -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT *
            FROM interview_reports
            WHERE id = ? AND user_id = ?
            """,
            (report_id, user_id),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["scores"] = json.loads(data.pop("scores_json", "{}"))
        data["highlights"] = json.loads(data.pop("highlights_json", "[]"))
        data["raw_transcript"] = json.loads(data.pop("raw_transcript_json", "[]"))
        data["qa_playback"] = json.loads(data.pop("qa_playback_json", "[]"))
        data["audio_objects"] = json.loads(data.pop("audio_objects_json", "[]"))
        return data
    finally:
        conn.close()


def delete_user_reports(db_path: str, user_id: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("DELETE FROM interview_reports WHERE user_id = ?", (user_id,))
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def delete_user_all_data(db_path: str, user_id: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        report_deleted = conn.execute(
            "DELETE FROM interview_reports WHERE user_id = ?", (user_id,)
        ).rowcount or 0
        conn.execute("DELETE FROM api_usage WHERE user_id = ?", (user_id,))
        conn.commit()
        return int(report_deleted)
    finally:
        conn.close()


def purge_reports_older_than(db_path: str, days: int) -> int:
    conn = sqlite3.connect(db_path)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor = conn.execute(
            """
            DELETE FROM interview_reports
            WHERE COALESCE(ended_at, created_at) < ?
            """,
            (cutoff,),
        )
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def record_api_usage(
    db_path: str,
    user_id: str,
    endpoint: str,
    request_chars: int,
    response_chars: int,
    estimated_cost_usd: float,
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO api_usage (
                created_at, user_id, endpoint, request_chars, response_chars, estimated_cost_usd
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                _now(),
                user_id,
                endpoint,
                max(request_chars, 0),
                max(response_chars, 0),
                max(float(estimated_cost_usd), 0.0),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def count_recent_api_calls(db_path: str, user_id: str, seconds: int = 60) -> int:
    conn = sqlite3.connect(db_path)
    cutoff = (datetime.now() - timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM api_usage
            WHERE user_id = ? AND created_at >= ?
            """,
            (user_id, cutoff),
        ).fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def get_cost_summary(db_path: str, user_id: str, hours: int = 24) -> Dict[str, float]:
    conn = sqlite3.connect(db_path)
    cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS req_count,
                COALESCE(SUM(request_chars), 0) AS req_chars,
                COALESCE(SUM(response_chars), 0) AS res_chars,
                COALESCE(SUM(estimated_cost_usd), 0) AS total_cost
            FROM api_usage
            WHERE user_id = ? AND created_at >= ?
            """,
            (user_id, cutoff),
        ).fetchone()
        if not row:
            return {
                "request_count": 0,
                "request_chars": 0,
                "response_chars": 0,
                "estimated_cost_usd": 0.0,
            }
        return {
            "request_count": float(row[0]),
            "request_chars": float(row[1]),
            "response_chars": float(row[2]),
            "estimated_cost_usd": float(row[3]),
        }
    finally:
        conn.close()
