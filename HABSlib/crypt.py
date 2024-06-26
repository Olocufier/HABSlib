import base64

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import padding

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from cryptography.hazmat.backends import default_backend

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

import os



######################################################
# Encryption
# 
# We want a procedure that can be reiterated multiple times seamlessly
# 
# 1.    Key Generation and Exchange
# 2.    Client starts handshake (GET)
# 3.    Server creates and securely send public key (over HTTPS when available on Azure).
# 4.    Client receives the public RSA and stores it.
# 5.    Client encrypts the AES key using the server's RSA public key and sends it to the server.
# 6.    Server uses its RSA private key to decrypt the received AES key.
# 7.    All subsequent communications use the AES key for encryption and decryption, ensuring fast and secure data exchange.



# Client only encrypts AES key
def encrypt_aes_key_with_rsa(aes_key, public_key):
    encrypted_key = public_key.encrypt(
        aes_key,
        rsa_padding.OAEP(
            mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return encrypted_key




def store_public_key(key, env_name='SERVER_PUBLIC_KEY'):
    pem = key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    os.environ[env_name] = str(pem) # there is only one. Each time it is called, will be overwritten



def load_public_key(env_name='SERVER_PUBLIC_KEY'):
    server_public_key_pem = os.environ.get(env_name)
    return serialization.load_pem_public_key(
        server_public_key_pem.encode(),
        backend=default_backend()
    )



# def generate_aes_key(length=32):  # AES key for AES-256
def generate_aes_key(length=16):  # AES key for AES-256
    return os.urandom(length)



def pad_message(message):
    padder = padding.PKCS7(128).padder()  # 128 bit = 16 bytes block size
    # padder = padding.PKCS7(256).padder()  # 256 bit = 32 bytes block size
    padded_data = padder.update(message) + padder.finalize()
    return padded_data



def unpad_message(padded_message):
    unpadder = padding.PKCS7(128).unpadder()  # 128 bit = 16 bytes block size
    # unpadder = padding.PKCS7(256).unpadder()  # 256 bit = 32 bytes block size
    data = unpadder.update(padded_message) + unpadder.finalize()
    return data



def encrypt_message(message, aes_key):
    # Generate a random Initialization Vector (IV)
    iv = os.urandom(16)
    # Pad the message
    padded_message = pad_message(message)
    # Create cipher instance
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    # Encrypt the padded message
    ciphertext = encryptor.update(padded_message) + encryptor.finalize()
    # Prepend the IV for easy retrieval at decryption time
    message_with_iv = iv + ciphertext
    return message_with_iv



def decrypt_message(encrypted_message, aes_key):
    # Extract the IV
    iv = encrypted_message[:16]
    # The remaining bytes are the ciphertext
    ciphertext = encrypted_message[16:]
    # Decrypt the ciphertext
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_message = decryptor.update(ciphertext) + decryptor.finalize()
    # Remove padding
    message = unpad_message(padded_message)
    return message


