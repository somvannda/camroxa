from __future__ import annotations

import base64
import hashlib
import os
import platform as _platform


def _get_machine_key() -> bytes:
    """Derive a machine-specific key for token encryption."""
    ident = f"{os.getlogin()}-{_platform.node()}-{os.getuid()}"
    return hashlib.sha256(ident.encode()).digest()


def _fernet_encrypt(data: bytes) -> bytes:
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(_get_machine_key())
    return Fernet(key).encrypt(data)


def _fernet_decrypt(data: bytes) -> bytes:
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(_get_machine_key())
    return Fernet(key).decrypt(data)


if _platform.system() == "Windows":
    import ctypes
    from ctypes import wintypes

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _CryptProtectData = _crypt32.CryptProtectData
    _CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(_DATA_BLOB),
        wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(_DATA_BLOB),
    ]
    _CryptProtectData.restype = wintypes.BOOL

    _CryptUnprotectData = _crypt32.CryptUnprotectData
    _CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(_DATA_BLOB),
        wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(_DATA_BLOB),
    ]
    _CryptUnprotectData.restype = wintypes.BOOL

    _LocalFree = _kernel32.LocalFree
    _LocalFree.argtypes = [wintypes.HLOCAL]
    _LocalFree.restype = wintypes.HLOCAL

    def _raise_last_win_error() -> None:
        code = ctypes.get_last_error()
        raise OSError(code, ctypes.FormatError(code))

    def dpapi_encrypt(data: bytes) -> bytes:
        raw = bytes(data or b"")
        if not raw:
            return b""
        buf = (ctypes.c_byte * len(raw)).from_buffer_copy(raw)
        in_blob = _DATA_BLOB(cbData=len(raw), pbData=ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
        out_blob = _DATA_BLOB()
        ok = _CryptProtectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob))
        if not ok:
            _raise_last_win_error()
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            if out_blob.pbData:
                _LocalFree(out_blob.pbData)

    def dpapi_decrypt(data: bytes) -> bytes:
        raw = bytes(data or b"")
        if not raw:
            return b""
        buf = (ctypes.c_byte * len(raw)).from_buffer_copy(raw)
        in_blob = _DATA_BLOB(cbData=len(raw), pbData=ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
        out_blob = _DATA_BLOB()
        desc = wintypes.LPWSTR()
        ok = _CryptUnprotectData(ctypes.byref(in_blob), ctypes.byref(desc), None, None, None, 0, ctypes.byref(out_blob))
        if not ok:
            _raise_last_win_error()
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            if out_blob.pbData:
                _LocalFree(out_blob.pbData)
            if desc:
                _LocalFree(desc)

else:
    def dpapi_encrypt(data: bytes) -> bytes:
        raw = bytes(data or b"")
        if not raw:
            return b""
        return _fernet_encrypt(raw)

    def dpapi_decrypt(data: bytes) -> bytes:
        raw = bytes(data or b"")
        if not raw:
            return b""
        return _fernet_decrypt(raw)


def dpapi_encrypt_to_base64(text: str) -> str:
    plain = str(text or "")
    if not plain:
        return ""
    enc = dpapi_encrypt(plain.encode("utf-8"))
    return base64.b64encode(enc).decode("ascii")


def dpapi_decrypt_from_base64(text: str) -> str:
    b64 = str(text or "").strip()
    if not b64:
        return ""
    raw = base64.b64decode(b64.encode("ascii"))
    dec = dpapi_decrypt(raw)
    return dec.decode("utf-8", errors="replace")

