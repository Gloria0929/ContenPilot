"""敏感信息加密与日志脱敏。

见文档第 51、53 节：脱敏必须由代码层面强制执行的中间件完成，
而不是依赖开发者自觉。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re

SENSITIVE_KEY_RE = re.compile(
    r"(token|secret|password|cookie|storage_state|authorization|"
    r"access_token|refresh_token|client_secret|key|credential)",
    re.IGNORECASE,
)

# 敏感字段名（任何路由模式都屏蔽，包括 metadata 深层嵌套）
_SENSITIVE_FIELD_NAMES = {
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
    "secret",
    "password",
    "cookie",
    "cookies",
    "storage_state",
    "authorization",
    "credential",
    "credentials",
    "encrypted_credentials",
    "api_key",
    "key",
}

REDACTED = "***REDACTED***"


def redact_value(value: str) -> str:
    """对单个字符串值脱敏。"""
    if not isinstance(value, str):
        return value
    # 去掉可能的敏感字面量
    return value


def redact(obj: object, _key: str = "") -> object:
    """递归脱敏任意嵌套结构，按字段名屏蔽。"""
    if isinstance(obj, dict):
        return {
            k: REDACTED if _is_sensitive(k) else redact(v, k)
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [redact(v, _key) for v in obj]
    return obj


def _is_sensitive(key: str) -> bool:
    k = str(key).lower()
    if k in _SENSITIVE_FIELD_NAMES:
        return True
    return bool(SENSITIVE_KEY_RE.search(k))


def redact_json(metadata: object) -> str:
    """将 metadata 脱敏后序列化为 JSON 字符串用于日志存储。"""
    return json.dumps(redact(metadata), ensure_ascii=False, default=str)


# ---- 加密（对称，用于加密存储敏感信息）----

_LEGACY_DEFAULT_KEY = base64.urlsafe_b64encode(
    hashlib.sha256(b"publisher-default-key-v1").digest()
)


def _key_file_path():
    from ..config import settings

    return settings.data_dir / "secret.key"


def _load_or_create_key_file() -> bytes | None:
    """无显式密钥时：在数据目录生成并持久化一个随机密钥文件。

    密钥只生成一次，之后复用，保证加密数据跨重启可解密；
    文件权限 600（密钥视同密码，仅当前用户可读）。
    返回 None 表示无法读写数据目录（如只读环境），由调用方回退。
    """
    import secrets

    path = _key_file_path()
    try:
        if path.exists():
            raw = path.read_text().strip()
            if raw:
                key = raw.encode()
                if len(key) < 32:
                    key = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
                return key
        from ..config import settings

        settings.ensure_dirs()
        key = base64.urlsafe_b64encode(secrets.token_bytes(32))
        path.write_text(key.decode())
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return key
    except OSError:
        return None


def _fernet():
    from cryptography.fernet import Fernet

    env_key = os.environ.get("PUBLISHER_ENCRYPTION_KEY")
    if env_key:
        key = env_key.encode()
        if len(key) < 32:
            key = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
    else:
        # 数据目录下生成/复用随机密钥文件；不可用时回退内置默认密钥
        # （仅本地临时环境，不具备真实保密性）
        key = _load_or_create_key_file() or _LEGACY_DEFAULT_KEY
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()


def decrypt_legacy(ciphertext: str) -> str:
    """用旧内置默认密钥解密（仅用于历史数据迁移，勿用于新数据）。"""
    from cryptography.fernet import Fernet

    return Fernet(_LEGACY_DEFAULT_KEY).decrypt(ciphertext.encode()).decode()


def encrypt_json(obj: object) -> str:
    return encrypt(json.dumps(obj, ensure_ascii=False, default=str))


def decrypt_json(ciphertext: str) -> object:
    return json.loads(decrypt(ciphertext))


def hash_secret(secret: str) -> str:
    """API Key 只存哈希，永不存明文。"""
    return hashlib.sha256(secret.encode()).hexdigest()