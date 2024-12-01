import jwt
import datetime

def generate_token(user_id,scret_key):
    """
    Generates a JWT token for a user.

    **Purpose**:
    - Creates a secure token to authenticate users, valid for 1 hour.

    **Parameters**:
    - `user_id` (str): The unique identifier for the user.
    - `secret_key` (str): The secret key used to sign the JWT.

    **Process**:
    1. Sets the expiration time for the token to 1 hour from the current UTC time.
    2. Encodes the user ID and expiration time into a JWT token using the HS256 algorithm.

    **Returns**:
    - `token` (str): The generated JWT token.
    """

    expiration_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    token = jwt.encode({'user_id': user_id, 'exp': expiration_time}, scret_key, algorithm='HS256')
    return token



def decode_token(token,scret_key):
    """
    Decodes and validates a JWT token.

    **Purpose**:
    - Verifies the authenticity and validity of the token.

    **Parameters**:
    - `token` (str): The JWT token to be decoded.
    - `secret_key` (str): The secret key used to verify the JWT.

    **Process**:
    1. Attempts to decode the token using the provided secret key.
    2. Handles exceptions:
        - `ExpiredSignatureError`: The token has expired.
        - `InvalidTokenError`: The token is invalid for any other reason.

    **Returns**:
    - `decoded_payload` (dict): The decoded payload if the token is valid.
    - `None`: If the token is expired or invalid.
    """

    try:
        return jwt.decode(token, scret_key, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    

def allowed_file(filename,allowed_file_extensions):
    """
    Checks if a file has an allowed extension.

    **Purpose**:
    - Ensures that uploaded files match the accepted formats.

    **Parameters**:
    - `filename` (str): The name of the file to be checked.
    - `allowed_file_extensions` (set): A set of allowed file extensions.

    **Process**:
    1. Splits the filename to extract the extension.
    2. Checks if the extension matches one of the allowed extensions.

    **Returns**:
    - `True`: If the file extension is allowed.
    - `False`: If the file extension is not allowed.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_file_extensions