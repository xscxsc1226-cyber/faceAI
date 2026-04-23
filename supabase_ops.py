import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    from supabase import Client, create_client

    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = Any  # type: ignore


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_supabase_configured(url: str, anon_key: str, enabled: bool) -> bool:
    return bool(enabled and SUPABASE_AVAILABLE and url and anon_key)


def get_admin_client(url: str, anon_key: str) -> Optional[Client]:
    if not SUPABASE_AVAILABLE:
        return None
    if not url or not anon_key:
        return None
    return create_client(url, anon_key)


def sign_up_with_password(url: str, anon_key: str, email: str, password: str) -> Dict[str, str]:
    client = get_admin_client(url, anon_key)
    if not client:
        raise RuntimeError("Supabase 未配置或未安装 supabase 依赖。")
    result = client.auth.sign_up({"email": email, "password": password})
    if not result.user:
        raise RuntimeError("注册失败，请检查邮箱与密码。")
    return {
        "user_id": result.user.id,
        "email": result.user.email or email,
        "access_token": (result.session.access_token if result.session else ""),
        "refresh_token": (result.session.refresh_token if result.session else ""),
    }


def sign_in_with_password(url: str, anon_key: str, email: str, password: str) -> Dict[str, str]:
    client = get_admin_client(url, anon_key)
    if not client:
        raise RuntimeError("Supabase 未配置或未安装 supabase 依赖。")
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    if not result.user or not result.session:
        raise RuntimeError("登录失败，请检查账号密码。")
    return {
        "user_id": result.user.id,
        "email": result.user.email or email,
        "access_token": result.session.access_token,
        "refresh_token": result.session.refresh_token,
    }


def get_user_client(url: str, anon_key: str, access_token: str) -> Optional[Client]:
    client = get_admin_client(url, anon_key)
    if not client or not access_token:
        return None
    client.postgrest.auth(access_token)
    return client


def save_cloud_report(
    url: str,
    anon_key: str,
    access_token: str,
    user_id: str,
    report: Dict[str, Any],
) -> Optional[str]:
    client = get_user_client(url, anon_key, access_token)
    if not client:
        return None
    payload = {
        "user_id": user_id,
        "created_at": now_ts(),
        "interview_mode": report.get("interview_mode", ""),
        "started_at": report.get("started_at", ""),
        "ended_at": report.get("ended_at", ""),
        "summary": report.get("summary", ""),
        "scores_json": json.dumps(report.get("scores", {}), ensure_ascii=False),
        "highlights_json": json.dumps(report.get("highlights", []), ensure_ascii=False),
        "raw_transcript_json": json.dumps(report.get("raw_transcript", []), ensure_ascii=False),
        "qa_playback_json": json.dumps(report.get("qa_playback", []), ensure_ascii=False),
        "audio_objects_json": json.dumps(report.get("audio_objects", []), ensure_ascii=False),
    }
    response = client.table("interview_reports").insert(payload).execute()
    if not response.data:
        return None
    return str(response.data[0].get("id", ""))


def list_cloud_reports(
    url: str,
    anon_key: str,
    access_token: str,
    user_id: str,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    client = get_user_client(url, anon_key, access_token)
    if not client:
        return []
    response = (
        client.table("interview_reports")
        .select("id,created_at,interview_mode,ended_at,summary")
        .eq("user_id", user_id)
        .order("id", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def get_cloud_report(
    url: str, anon_key: str, access_token: str, user_id: str, report_id: str
) -> Optional[Dict[str, Any]]:
    client = get_user_client(url, anon_key, access_token)
    if not client:
        return None
    response = (
        client.table("interview_reports")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", report_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    data = response.data[0]
    data["scores"] = json.loads(data.get("scores_json", "{}"))
    data["highlights"] = json.loads(data.get("highlights_json", "[]"))
    data["raw_transcript"] = json.loads(data.get("raw_transcript_json", "[]"))
    data["qa_playback"] = json.loads(data.get("qa_playback_json", "[]"))
    data["audio_objects"] = json.loads(data.get("audio_objects_json", "[]"))
    return data


def upload_audio_blob(
    url: str,
    anon_key: str,
    access_token: str,
    bucket_name: str,
    user_id: str,
    audio_bytes: bytes,
    object_name: str,
) -> Optional[str]:
    client = get_user_client(url, anon_key, access_token)
    if not client:
        return None
    path = f"{user_id}/{object_name}"
    client.storage.from_(bucket_name).upload(
        path,
        audio_bytes,
        {"content-type": "application/octet-stream", "upsert": "true"},
    )
    return path


def purge_cloud_reports_older_than(
    url: str, anon_key: str, access_token: str, user_id: str, days: int
) -> None:
    client = get_user_client(url, anon_key, access_token)
    if not client:
        return
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    (
        client.table("interview_reports")
        .delete()
        .eq("user_id", user_id)
        .lt("ended_at", cutoff)
        .execute()
    )


def delete_user_cloud_data(
    url: str, anon_key: str, access_token: str, user_id: str, bucket_name: str
) -> None:
    client = get_user_client(url, anon_key, access_token)
    if not client:
        return
    client.table("interview_reports").delete().eq("user_id", user_id).execute()
    file_list = client.storage.from_(bucket_name).list(path=user_id)
    paths = [f"{user_id}/{item['name']}" for item in file_list] if file_list else []
    if paths:
        client.storage.from_(bucket_name).remove(paths)
