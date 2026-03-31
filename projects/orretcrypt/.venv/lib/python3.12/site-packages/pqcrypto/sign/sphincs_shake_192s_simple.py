import struct
from .._sign.sphincs_shake_192s_simple import ffi as __ffi, lib as __lib

ALGORITHM = "sphincs_shake_192s_simple"
PUBLIC_KEY_SIZE = __lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_PUBLICKEYBYTES
SECRET_KEY_SIZE = __lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_SECRETKEYBYTES
SIGNATURE_SIZE = __lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_BYTES

def sign_generate_keypair_factory(ffi, lib):
    def generate_keypair():
        public_key_buf = ffi.new("uint8_t [{}]".format(lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_PUBLICKEYBYTES))
        secret_key_buf = ffi.new("uint8_t [{}]".format(lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_SECRETKEYBYTES))
        if 0 != lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_crypto_sign_keypair(public_key_buf, secret_key_buf):
            raise RuntimeError("Keypair generation failed")
        public_key = bytes(ffi.buffer(public_key_buf, lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_PUBLICKEYBYTES))
        secret_key = bytes(ffi.buffer(secret_key_buf, lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_SECRETKEYBYTES))
        return public_key, secret_key
    return generate_keypair

def sign_sign_factory(ffi, lib):
    def sign(secret_key, message):
        if not isinstance(secret_key, bytes):
            raise TypeError("'secret_key' must be of type 'bytes'")
        if not isinstance(message, bytes):
            raise TypeError("'message' must be of type 'bytes'")
        if len(secret_key) != lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_SECRETKEYBYTES:
            raise ValueError(f"'secret_key' must be of length '{lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_SECRETKEYBYTES}'")
        signature_buf = ffi.new("uint8_t [{}]".format(lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_BYTES))
        signature_len = ffi.new("size_t *", lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_BYTES)
        if 0 != lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_crypto_sign_signature(signature_buf, signature_len, message, len(message), secret_key):
            raise RuntimeError("Signature generation failed")
        signature_len = struct.unpack("Q", ffi.buffer(signature_len, 8))[0]
        return bytes(ffi.buffer(signature_buf, signature_len))
    return sign

def sign_verify_factory(ffi, lib):
    def verify(public_key, message, signature):
        if not isinstance(public_key, bytes):
            raise TypeError("'public_key' must be of type 'bytes'")
        if not isinstance(message, bytes):
            raise TypeError("'message' must be of type 'bytes'")
        if not isinstance(signature, bytes):
            raise TypeError("'signature' must be of type 'bytes'")
        if len(public_key) != lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_PUBLICKEYBYTES:
            raise ValueError(f"'public_key' must be of length '{lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_PUBLICKEYBYTES}'")
        if len(signature) > lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_BYTES:
            raise ValueError(f"'signature' must be of length at most '{lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_CRYPTO_BYTES}'")
        return 0 == lib.PQCLEAN_SPHINCSSHAKE192SSIMPLE_CLEAN_crypto_sign_verify(signature, len(signature), message, len(message), public_key)
    return verify

generate_keypair = sign_generate_keypair_factory(__ffi, __lib)
sign = sign_sign_factory(__ffi, __lib)
verify = sign_verify_factory(__ffi, __lib)