"""AES in ECB, CTR and XTS modes through OpenSSL's libcrypto. Decky's Python has no AES of its own,
but it ships libcrypto for its ssl module."""
import ctypes
import os
import sys

LIBRARIES = ("libcrypto.so.3", "libcrypto.so", "/opt/homebrew/lib/libcrypto.dylib", "/usr/local/lib/libcrypto.dylib")
_lib = None


class Unavailable(Exception):
    pass


def lib():
    global _lib
    if _lib is None:
        # PyInstaller unpacks Decky's libraries next to its Python.
        names = [os.path.join(sys._MEIPASS, "libcrypto.so.3")] if hasattr(sys, "_MEIPASS") else []
        for name in names + list(LIBRARIES):
            try:
                found = ctypes.CDLL(name)
                found.EVP_CIPHER_CTX_new
            except (OSError, AttributeError):
                continue
            found.EVP_CIPHER_CTX_new.restype = ctypes.c_void_p
            found.EVP_CIPHER_CTX_free.argtypes = [ctypes.c_void_p]
            for mode in ("EVP_aes_128_ecb", "EVP_aes_128_ctr", "EVP_aes_128_xts"):
                getattr(found, mode).restype = ctypes.c_void_p
            found.EVP_DecryptInit_ex.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                                 ctypes.c_char_p, ctypes.c_char_p]
            found.EVP_EncryptInit_ex.argtypes = found.EVP_DecryptInit_ex.argtypes
            found.EVP_CIPHER_CTX_set_padding.argtypes = [ctypes.c_void_p, ctypes.c_int]
            found.EVP_DecryptUpdate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int),
                                                ctypes.c_char_p, ctypes.c_int]
            found.EVP_EncryptUpdate.argtypes = found.EVP_DecryptUpdate.argtypes
            _lib = found
            break
        else:
            _lib = False
    if not _lib:
        raise Unavailable("OpenSSL's libcrypto is missing")
    return _lib


def _run(mode, key, iv, data, encrypt=False):
    c = lib()
    ctx = c.EVP_CIPHER_CTX_new()
    if not ctx:
        raise Unavailable("EVP_CIPHER_CTX_new failed")
    try:
        init, update = (c.EVP_EncryptInit_ex, c.EVP_EncryptUpdate) if encrypt else (c.EVP_DecryptInit_ex, c.EVP_DecryptUpdate)
        if not init(ctx, getattr(c, mode)(), None, key, iv):
            raise ValueError(f"{mode} refused the key")
        c.EVP_CIPHER_CTX_set_padding(ctx, 0)
        out = ctypes.create_string_buffer(len(data) + 32)
        n = ctypes.c_int(0)
        if not update(ctx, out, ctypes.byref(n), data, len(data)):
            raise ValueError(f"{mode} failed")
        return out.raw[:n.value]
    finally:
        c.EVP_CIPHER_CTX_free(ctx)


def ecb(key, data, encrypt=False):
    return _run("EVP_aes_128_ecb", key, None, data, encrypt)


def ctr(key, counter, data):
    return _run("EVP_aes_128_ctr", key, counter, data)


def xts(key, data, sector, sector_size=0x200, encrypt=False):
    """Run Nintendo's XTS: one tweak per sector, the sector number in big-endian order."""
    out = bytearray()
    for i in range(0, len(data), sector_size):
        out += _run("EVP_aes_128_xts", key, (sector + i // sector_size).to_bytes(16, "big"),
                    data[i:i + sector_size], encrypt)
    return bytes(out)
