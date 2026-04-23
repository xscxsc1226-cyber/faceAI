from typing import Optional

try:
    from cryptography.fernet import Fernet, InvalidToken

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    InvalidToken = Exception  # type: ignore


def can_encrypt(encryption_key: str) -> bool:
    return bool(CRYPTO_AVAILABLE and encryption_key)


def encrypt_bytes(data: bytes, encryption_key: str) -> bytes:
    if not can_encrypt(encryption_key):
        return data
    return Fernet(encryption_key.encode("utf-8")).encrypt(data)


def decrypt_bytes(data: bytes, encryption_key: str) -> bytes:
    if not can_encrypt(encryption_key):
        return data
    try:
        return Fernet(encryption_key.encode("utf-8")).decrypt(data)
    except InvalidToken as exc:
        raise RuntimeError("音频解密失败，密钥无效或数据损坏。") from exc


def get_privacy_notice(retention_days: int, encrypted: bool) -> str:
    encryption_text = "开启" if encrypted else "未开启"
    return (
        f"数据保留周期：{retention_days} 天；音频静态加密：{encryption_text}。"
        "你可以在侧边栏执行一键删除自己的历史数据。"
    )
