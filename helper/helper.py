import jwt
import datetime

def generate_token(user_id,scret_key):
    expiration_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    token = jwt.encode({'user_id': user_id, 'exp': expiration_time}, scret_key, algorithm='HS256')
    return token



def decode_token(token,scret_key):
    try:
        return jwt.decode(token, scret_key, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    

def allowed_file(filename,allowed_file_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_file_extensions