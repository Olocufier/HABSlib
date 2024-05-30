import os
import base64
import requests
import json
import jsonschema
from jsonschema import validate
from jsonschema import exceptions
# from bson import json_util

from datetime import datetime
import uuid
import asyncio

from . import BASE_URL, VERSION
from . import BoardManager

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from . import store_public_key, load_public_key, generate_aes_key, encrypt_aes_key_with_rsa, encrypt_message, decrypt_message


############################
# BrainOS - HABSlib - TODO #
############################
# 
# - Encryption:
#       - Client side:
#           2.    Client starts handshake (GET)
#           4.    Client receives the public RSA and stores it.
#           5.    Client encrypts the AES key using the server's RSA public key and sends it to the server.
#           7.    All subsequent communications use the AES key for encryption and decryption, ensuring fast and secure data exchange.
# 
# - Unit Test:
#       - the file client.py is the base for testing habslib
#       - Low level unit test: for single-use function in this file, and BoradManager
#       - High level unit test: fixtures for creating the session, sending data and retrieving
#       - Tests are on demand, not necessarily for every commit. But for each major change yes.
# 
# - Code coverage
# 
# - Reviewer:
#       Human
#       Automated (unit test passing GitLab Ops)



######################################################
# validate the metadata against a specified schema
def validate_metadata(metadata, schema_name, schemafile='metadata.json'):

    try:
        with open(os.path.join(os.path.dirname(__file__), schemafile), 'r') as file:
            content = file.read()
            schemas = json.loads(content)
        schema = schemas[schema_name]
        validate(instance=metadata, schema=schema) #, format_checker=FormatChecker())
        print("Metadata validation successful!")
        return True

    except json.JSONDecodeError as e:
        print("Failed to decode JSON:", e)
        return False

    except exceptions.ValidationError as e:
        print("Validation error:", e)
        return False

    except FileNotFoundError:
        print(f"No such file: {schemafile}")
        return False

    except Exception as e:
        print("A general error occurred:", e)
        return False



######################################################
def handshake(base_url):  
    global BASE_URL
    BASE_URL = base_url
    url = f"{BASE_URL}/api/{VERSION}/handshake_rsa"
    response = requests.get(url)

    if response.status_code == 200:
        print("Handshake (RSA) successful.")
        api_public_key_pem = response.json().get('api_public_key')
        api_public_key = serialization.load_pem_public_key(
            api_public_key_pem.encode(),
            backend=default_backend()
        )
        os.environ['API_PUBLIC_KEY'] = api_public_key_pem

        # Then we generate and store the AES key
        aes_key = generate_aes_key()
        # print("aes_key", aes_key)
        os.environ['AES_KEY'] = base64.b64encode( aes_key ).decode('utf-8')

        encrypted_aes_key = encrypt_aes_key_with_rsa(aes_key, api_public_key)
        encrypted_aes_key_b64 = base64.b64encode(encrypted_aes_key).decode('utf-8')
        # print("encrypted_aes_key_b64",encrypted_aes_key_b64)
        aes_key_payload = {
            "encrypted_aes_key": encrypted_aes_key_b64
        }
        response = requests.post(f"{BASE_URL}/api/{VERSION}/handshake_aes", json=aes_key_payload)

        if response.status_code == 200:
            print("Handshake (AES) successful.")
            return True
        else:
            print("Handshake (AES) failed:", response.text)
            return None
    else:
        print("Handshake (RSA) failed:", response.text)
        return None



######################################################
def set_user(first_name=None, last_name=None, email=None, age=None, weight=None, sex=None):
    url = f"{BASE_URL}/api/{VERSION}/users"

    # user_id = search_user_by_mail(email)
    # if user_id:
    #     print("User already exists, with id:", user_id)
    #     return user_id

    user_data = {
        "first_name": first_name, 
        "last_name": last_name, 
        "email": email, 
        "age": age, 
        "weight": weight, 
        "sex": sex
    }
    if validate_metadata(user_data, "userSchema", ):
        _user = {
            "user_data": user_data
        }
        _user = json.dumps(_user).encode('utf-8')
        aes_key_b64 = os.environ.get('AES_KEY')
        aes_key_bytes = base64.b64decode(aes_key_b64)
        response = requests.post(
            url,
            data=encrypt_message(_user, aes_key_bytes),
            headers={'Content-Type': 'application/octet-stream'}
        )

        if response.status_code == 200:
            print("User successfully created.")
            user_id = response.json().get('user_id')
            return user_id
        else:
            print("User creation failed:", response.text)
            return None
    else:
        print("User creation failed.")


######################################################
def search_user_by_mail(email):
    url = f"{BASE_URL}/api/{VERSION}/users?email={email}"

    response = requests.get(url)

    if response.status_code == 200:
        user_id = response.json().get('user_id')
        print("User found:", user_id)
        return user_id
    else:
        print("User not found.", response.text)
        return None


######################################################
def get_user_by_id(user_id):
    url = f"{BASE_URL}/api/{VERSION}/users/{user_id}"

    response = requests.get(url)

    if response.status_code == 200:
        print("User found.")
        encrypted_data = response.content 
        aes_key_b64 = os.environ.get('AES_KEY')
        aes_key_bytes = base64.b64decode(aes_key_b64)
        decrypted_json_string = decrypt_message(encrypted_data, aes_key_bytes)
        user_data = json.loads(decrypted_json_string)['user_data']
        return user_data
    else:
        print("User not found:", response.text)
        return None


######################################################
def set_session(metadata):
    url = f"{BASE_URL}/api/{VERSION}/sessions"
    _session = metadata
    _session = json.dumps(_session).encode('utf-8')
    aes_key_b64 = os.environ.get('AES_KEY')
    aes_key_bytes = base64.b64decode(aes_key_b64)
    response = requests.post(
        url,
        data=encrypt_message(_session, aes_key_bytes),
        headers={'Content-Type': 'application/octet-stream'}
    )

    if response.status_code == 200:
        print("Session successfully created.")
        # Extract the unique identifier for the uploaded data
        session_id = response.json().get('session_id')

        # print(session_id)
        return session_id
    else:
        print("Session failed:", response.text)
        return None


######################################################
def get_data_by_id(data_id):
    get_url = f"{BASE_URL}/api/{VERSION}/rawdata/{data_id}"
    
    response = requests.get(get_url)
    
    if response.status_code == 200:
        print("Retrieved data successfully.")
        # decrypt
        return response.json().get('rawData')
    else:
        print("Failed to retrieve data:", response.text)


######################################################
def get_data_by_session(session_id):
    get_url = f"{BASE_URL}/api/{VERSION}/sessions/{session_id}/rawdata"
    
    response = requests.get(get_url)
    
    if response.status_code == 200:
        print("Retrieved data successfully.")
        # decrypt
        return response.json().get('data')
    else:
        print("Failed to retrieve data:", response.text)


######################################################
def get_data_ids_by_session(session_id):
    get_url = f"{BASE_URL}/api/{VERSION}/sessions/{session_id}/ids"
    
    response = requests.get(get_url)
    
    if response.status_code == 200:
        print("Retrieved ids successfully.")
        # decrypt
        return response.json().get('ids')
    else:
        print("Failed to retrieve ids:", response.text)



######################################################
def upload_data(metadata, data, timestamps):
    url = f"{BASE_URL}/api/{VERSION}/rawdata"
    _data = {
        "metadata": metadata,
        "data": data,
        "timestamps": timestamps,
    }
    _data = json.dumps(_data).encode('utf-8')

    # response = requests.post(url, json=_data)
    aes_key_b64 = os.environ.get('AES_KEY')
    aes_key_bytes = base64.b64decode(aes_key_b64)
    response = requests.post(
        url,
        data=encrypt_message(_data, aes_key_bytes),
        headers={'Content-Type': 'application/octet-stream'}
    )

    if response.status_code == 200:
        print('.', end='', flush=True)
        # Extract the unique identifier for the uploaded data
        data_id = response.json().get('data_id')
        return data_id, None
    else:
        print("Upload failed:", response.text)
        return None



######################################################
def acquire_send_raw(user_id, date, board, stream_duration, buffer_duration):
    session_id = asyncio.run( _acquire_send_raw(user_id, date, board, stream_duration, buffer_duration) )
    return session_id

async def _acquire_send_raw(user_id, date, board, stream_duration, buffer_duration):
    # get board
    board_manager = BoardManager(enable_logger=False, board_id=board)
    board_manager.connect()
    # set session for the data
    # We set a session id for the current interaction with the API (even if we fail to get the board, it will be important to store the failure)
    session_metadata = {
      "user_id": user_id, # add user to the session for reference
      "session_date": date
    }
    if validate_metadata(session_metadata, "sessionSchema"):        
        session_id = set_session(metadata={**session_metadata, **board_manager.metadata})
        board_manager.metadata['session_id'] = session_id # add session to the data for reference

        # stream_duration sec, buffer_duration sec
        await board_manager.data_acquisition_loop(
            stream_duration=stream_duration, 
            buffer_duration=buffer_duration, 
            service=upload_data
        )

        return session_id
    else:
        return False



######################################################
######################################################
def set_pipe(metadata, pipeline, params):
    url = f"{BASE_URL}/api/{VERSION}/sessions/pipe/{pipeline}"
    _session = {
        "metadata": metadata,
        "processing_params": params,
    }
    _session = json.dumps(_session).encode('utf-8')
    aes_key_b64 = os.environ.get('AES_KEY')
    aes_key_bytes = base64.b64decode(aes_key_b64)
    response = requests.post(
        url,
        data=encrypt_message(_session, aes_key_bytes),
        headers={'Content-Type': 'application/octet-stream'}
    )

    if response.status_code == 200:
        print("Session successfully created.")
        # Extract the unique identifier for the uploaded data
        session_id = response.json().get('session_id')
        # print(session_id)
        return session_id
    else:
        print("Session failed:", response.text)
        return None


######################################################
def upload_pipedata(metadata, data, timestamps):
    url = f"{BASE_URL}/api/{VERSION}/pipedata/{metadata['session_id']}" # the metadata contain session_id to consistently pass it with each upload

    _data = {
        "metadata": metadata,
        "data": data,
        "timestamps": timestamps,
    }
    _data = json.dumps(_data).encode('utf-8')
    aes_key_b64 = os.environ.get('AES_KEY')
    aes_key_bytes = base64.b64decode(aes_key_b64)
    response = requests.post(
        url,
        data=encrypt_message(_data, aes_key_bytes),
        headers={'Content-Type': 'application/octet-stream'}
    )

    if response.status_code == 200:
        print('.', end='', flush=True)
        # Extract the unique identifier for the uploaded data
        data_id = response.json().get('data_id')
        # Retrieve the processed data
        data = response.json().get('pipeData')
        print(data)
        return data_id, data
    else:
        print("Upload failed:", response.text)
        return None


######################################################
def acquire_send_pipe(pipeline, params, user_id, date, board, stream_duration, buffer_duration):
    session_id = asyncio.run( _acquire_send_pipe(pipeline, params, user_id, date, board, stream_duration, buffer_duration) )
    return session_id

async def _acquire_send_pipe(pipeline, params, user_id, date, board, stream_duration, buffer_duration):
    # get board
    board_manager = BoardManager(enable_logger=False, board_id=board)
    board_manager.connect()

    # set session for the data
    # We set a session id for the current interaction with the API (even if we fail to get the board, it will be important to store the failure)
    session_metadata = {
      "user_id": user_id, # add user to the session for reference
      "session_date": date
    }
    if validate_metadata(session_metadata, "sessionSchema"):
        session_id = set_pipe(metadata={**session_metadata, **board_manager.metadata}, pipeline=pipeline, params=params)
        board_manager.metadata['session_id'] = session_id # add session to the data for reference

        # stream_duration sec, buffer_duration sec
        await board_manager.data_acquisition_loop(
            board=board,
            stream_duration=stream_duration, 
            buffer_duration=buffer_duration, 
            service=upload_pipedata
        )
        # use the processed data
        # print(board_manager.processed_data)

        return session_id
    else:
        return False


######################################################
def train(session_id, params):
    url = f"{BASE_URL}/api/{VERSION}/train/{session_id}"
    _params = {
        "params": params,
    }
    _params = json.dumps(_params).encode('utf-8')
    aes_key_b64 = os.environ.get('AES_KEY')
    aes_key_bytes = base64.b64decode(aes_key_b64)
    response = requests.post(
        url,
        data=encrypt_message(_params, aes_key_bytes),
        headers={'Content-Type': 'application/octet-stream'}
    )

    if response.status_code == 200:
        task_id = response.json().get('task_id')
        print("Published. For future interactions, use task_id:",task_id)
        return task_id
    else:
        print("Publish failed:", response.text)
        return None


######################################################
def infer(data_id, params):
    url = f"{BASE_URL}/api/{VERSION}/infer/{data_id}"
    _params = {
        "params": params,
    }
    _params = json.dumps(_params).encode('utf-8')
    # response = requests.post(url, json=_params)
    aes_key_b64 = os.environ.get('AES_KEY')
    aes_key_bytes = base64.b64decode(aes_key_b64)
    response = requests.post(
        url,
        data=encrypt_message(_params, aes_key_bytes),
        headers={'Content-Type': 'application/octet-stream'}
    )
    
    if response.status_code == 200:
        task_id = response.json().get('task_id')
        print("Published. For future interactions, use task_id:",task_id)
        return task_id
    else:
        print("Publish failed:", response.text)
        return None

