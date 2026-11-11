import base64
import os

# A secret key to make the encoding unique to your app. 
# Change this to your own random string!
SECRET_KEY = os.environ.get('ID_OBFUSCATION_KEY', 'marketplace_super_secret_2026')

def encode_product_id(product_id):
    """Converts a numerical ID into a short, unguessable alphanumeric string."""
    # 1. Convert the integer ID into bytes (8 bytes makes the token a nice length)
    id_bytes = product_id.to_bytes(8, byteorder='big')
    
    # 2. XOR it with our secret key to scramble the numbers
    key_bytes = SECRET_KEY.encode('utf-8')[:8] 
    scrambled = bytes(a ^ b for a, b in zip(id_bytes, key_bytes))
    
    # 3. Encode to URL-safe Base64 and remove the padding '=' signs
    token = base64.urlsafe_b64encode(scrambled).rstrip(b'=').decode('utf-8')
    
    return token

def decode_product_id(token):
    """Converts the scrambled string back into the original numerical ID."""
    try:
        # 1. Add the padding '=' signs back so Base64 can decode it
        padding = 4 - len(token) % 4
        if padding != 4:
            token += '=' * padding
            
        # 2. Decode Base64
        scrambled = base64.urlsafe_b64decode(token)
        
        # 3. XOR with the secret key again to unscramble it
        key_bytes = SECRET_KEY.encode('utf-8')[:8]
        id_bytes = bytes(a ^ b for a, b in zip(scrambled, key_bytes))
        
        # 4. Convert bytes back to an integer
        product_id = int.from_bytes(id_bytes, byteorder='big')
        return product_id
    except Exception:
        return None


SECRET_KEY = os.environ.get('ID_OBFUSCATION_KEY', 'marketplace_secret_key_2026_adebayo')

def encode_id(entity_id):
    """Converts any numerical ID into a short, unguessable alphanumeric token"""
    id_bytes = int(entity_id).to_bytes(8, byteorder='big')
    key_bytes = SECRET_KEY.encode('utf-8')[:8]
    scrambled = bytes(a ^ b for a, b in zip(id_bytes, key_bytes))
    token = base64.urlsafe_b64encode(scrambled).rstrip(b'=').decode('utf-8')
    return token

def decode_id(token):
    """Converts the token back into the original numerical ID"""
    try:
        padding = 4 - len(token) % 4
        if padding != 4:
            token += '=' * padding
        scrambled = base64.urlsafe_b64decode(token)
        key_bytes = SECRET_KEY.encode('utf-8')[:8]
        id_bytes = bytes(a ^ b for a, b in zip(scrambled, key_bytes))
        entity_id = int.from_bytes(id_bytes, byteorder='big')
        return entity_id
    except Exception:
        return None
