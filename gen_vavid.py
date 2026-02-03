from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import base64

# Generate private key
private_key = ec.generate_private_key(ec.SECP256R1())

# Get public key
public_key = private_key.public_key()

# Encode public key in URL-safe base64
public_numbers = public_key.public_numbers()
x = public_numbers.x.to_bytes(32, 'big')
y = public_numbers.y.to_bytes(32, 'big')
public_key_bytes = b'\x04' + x + y
public_key_b64 = base64.urlsafe_b64encode(public_key_bytes).decode('utf-8')

# Encode private key in URL-safe base64
private_value = private_key.private_numbers().private_value
private_key_bytes = private_value.to_bytes(32, 'big')
private_key_b64 = base64.urlsafe_b64encode(private_key_bytes).decode('utf-8')

print("Public Key (Base64):", public_key_b64)
print("Private Key (Base64):", private_key_b64)
