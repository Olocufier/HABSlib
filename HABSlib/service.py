######################################################
# INTRO

r"""
# HABSlib: Python Library for EEG Analysis and Biomarker Evaluation

HABSlib is a versatile Python library designed to facilitate interaction with the HABS BrainOS API for comprehensive EEG data analysis and biomarker evaluation. 
Developed to support neuroscientific research and clinical applications, HABSlib simplifies the process of fetching, processing, and analyzing EEG data through a user-friendly interface.

Key Features:
- **API Integration**: Connects with the BrainOS HABS API, allowing users to access EEG data and related services effortlessly.
- **Data Management**: Provides a robust interface for managing EEG datasets, including storage on the HABS servers.
- **Biomarker Evaluation**: Enables the analysis of EEG biomarkers, essential for diagnosing and monitoring neurological conditions.
- **Customizable Pipelines**: Users can create custom analysis pipelines tailored to specific research needs, ensuring flexibility and adaptability in various use cases.

## Sessions

The communications between the user and HABS BrainOS is based on a RESTful API (see doc) and structured into sessions.    

A *Session* with the HABS BrainOS iinitiates with an handshake during which encryption keys are exchanged for the security of any following communication between the user and the server.

### Simple sessions

There are two general types of session: *real-time* and *off-line*.

In setting a either a real-time or off-line session, the user provides the session metadata, such as their user_id, session_date, session type (all required), and additional notes depending on the nature of recordings.

Then, in a real-time session, the user specifies the type of EEG DEVICE ('board') used, the duration of the EEG recording, and the frequency of server update. 

In an off-line session, the user specifies a session id (referring to data already exisiting, either acquired live at some point in time, or from an uploaded file).    
The HABSlib can read EDF files (EDF file type only, for now, but it's growing) and sends it to the server.

In these simple types of session, after the real-time or offline uploading, the data can be selected via the session_id for further processing.

### Piped sessions

There is another type of session, called *piped* session. This type of session is meant to help you organize the flow of analysis and make it reproducible.     
Usually, an analysis implies several steps over the raw data. BrainOS allows you to perform a growing number of predefined and parametrizable functions over the data, to filter, remove artifacts, and extract features. 
And you can do it without taking the output of one function and passing it to another. You can pipe (|) the output of one function into the next.

This session type also is available as *real-time* and *off-line*. In the *real-time* version the EEG data is processed as per pipe by the server as soon as it is received, and the results are sent back to the user as soon as they are processed.    
"""

import sys
import os
import base64
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from functools import wraps

import json
import jsonschema
from jsonschema import validate
from jsonschema import exceptions

import numpy as np

import time
from datetime import datetime as dt

import uuid
import asyncio
import webbrowser

from . import BASE_URL, VERSION
from . import BoardManager

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from . import store_public_key, load_public_key, generate_aes_key, encrypt_aes_key_with_rsa, encrypt_message, decrypt_message

from pyedflib import highlevel

from importlib.metadata import version


######################################################
# Global retry strategy
retry_strategy = Retry(
    total=5,  # Total number of retries for all errors
    connect=5,  # Number of retries for connection-related errors
    read=5,  # Number of retries for read-related errors (e.g., timeouts)
    backoff_factor=1,  # Wait 1s, 2s, 4s, etc. between retries
    status_forcelist=[429, 500, 502, 503, 504],  # Retry on these HTTP status codes
    raise_on_status=False,  # Avoid raising exceptions on retries
    allowed_methods=["POST", "GET"],  # Retry for these HTTP methods
)

# Function to create a session with the retry strategy
def get_retry_session():
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


######################################################
# decorator encryption
def encrypt_request_data(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        try:
            # Get the user_id from args or kwargs (depending on how it's passed)
            user_id = kwargs.get('user_id') or args[2]  # Assuming user_id is always the 3rd argument
            aes_key_b64 = os.environ.get(f"AES_KEY_{str(user_id)}")

            if not aes_key_b64:
                raise Exception('Missing encryption key')

            aes_key_bytes = base64.b64decode(aes_key_b64)

            # Encrypt the data before sending the request
            data = kwargs.get('data')
            if data:
                # JSON encode and then encrypt
                encrypted_data = encrypt_message(json.dumps(data).encode('utf-8'), aes_key_bytes)
                kwargs['data'] = encrypted_data

            # Add the required headers for the request
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers'].update({
                'Content-Type': 'application/octet-stream',
                'X-User-ID': user_id
            })

            # Call the original function with encrypted data
            return func(*args, **kwargs)

        except Exception as e:
            print(f"Error encrypting request data: {e}")
            return None

    return decorated_function


######################################################
# validate the metadata against a specified schema
def validate_metadata(metadata, schema_name, schemafile='metadata.json'):
    """
    Validate metadata against a given JSON schema.

    Args:    
        **metadata** (*dict*): The metadata to be validated.    
        **schema_name** (*str*): The name of the schema to validate against. HABSlib currently supports the validation of Session metadata and User data.    
        **schemafile** (*str*, optional): The path to the JSON file containing the schemas. Defaults to 'metadata.json'.    

    Returns:    
        *bool*: True if validation is successful, False otherwise.

    Raises:    
        **FileNotFoundError**: If the schema file does not exist.     
        **json.JSONDecodeError**: If there is an error decoding the JSON schema file.     
        **exceptions.ValidationError**: If the metadata does not conform to the schema.     
        **Exception**: For any other errors that occur during validation.     

    Example:
    ```
    metadata = {"name": "example", "type": "data"}
    schema_name = "example_schema"
    is_valid = validate_metadata(metadata, schema_name)
    if is_valid:
        print("Metadata is valid.")
    else:
        print("Metadata is invalid.")
    ```
    """
    print(metadata)
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


def convert_datetime_in_dict(data):
    """
    Recursively converts all datetime objects in a dictionary to strings in ISO format.

    Args:     
        **data** (*dict*): The dictionary containing the data.

    Returns:     
        *dict*: The dictionary with datetime objects converted to strings.
    """
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, dict):
            data[key] = convert_datetime_in_dict(value)
    return data


def head():
    """
    Every library should have a nice ASCII art :)
    Propose yours, there is a prize for the best one!
    """
    print()
    print("       HUMAN        AUGMENTED        BRAIN         SYSTEMS    ")
    print("   ---------------------------------------------------------- ")
    print("   ▒▒▒▒     ▒▒▒▒     ░▒▒▒▒▒░     ▒▒▒▒▒▒▒▒▒▒▒▒░   ░▒▒▒▒▒▒▒▒▒░  ")
    print("   ▒▒▒▒     ▒▒▒▒    ░▒▒▒▒▒▒▒░             ░▒▒▒▒ ░▒▒▒░     ░▒░ ")
    print("   ▒▒▒▒▒▒▒▒▒▒▒▒▒   ░▒▒▒▒ ▒▒▒▒░   ▒▒▒▒▒▒▒▒▒▒▒▒▒   ░▒▒▒▒▒▒▒▒▒░  ")
    print("   ▒▒▒▒     ▒▒▒▒  ░▒▒▒▒   ▒▒▒▒░  ▒▒▒▒     ░▒▒▒▒ ░▒░     ░▒▒▒░ ")
    print("   ▒▒▒▒     ▒▒▒▒ ░▒▒▒▒     ▒▒▒▒░ ▒▒▒▒▒▒▒▒▒▒▒▒░   ░▒▒▒▒▒▒▒▒▒░  ")
    print("   ---------------------------------------------------------- ")
    print("   HABSlib version:", version("HABSlib"))
    print()




######################################################
def singleton_init(board, serial_number, serial_port):
    board_manager = BoardManager(enable_logger=False, board_id=board, serial_number=serial_number, serial_port=serial_port)
    # board_manager.connect()
    # board_manager.disconnect()




######################################################
def handshake(base_url, user_id):  
    """
    Perform a handshake with the server to exchange encryption keys for the current session.

    This function performs the following steps:
    0. Performs login to the HABS server.
    1. Sends a GET request to the server to initiate an RSA handshake.
    2. Retrieves the server's public RSA key from the response.
    3. Generates a local AES key and stores it in the environment.
    4. Encrypts the AES key with the server's RSA key.
    5. Sends the encrypted AES key to the server to complete the AES handshake.

    Args:      
        **base_url** (*str*): The base URL of the server's API.
        **user_id** (*str*): The user id (obtained through free registration with HABS)

    Returns:     
        *bool*: True if the handshake is successful, None otherwise.

    Raises:      
        **requests.RequestException**: If a request to the server fails.

    Example:
    ```
    success = handshake("https://example.com")
    if success:
        print("Handshake completed successfully.")
    else:
        print("Handshake failed.")
    ```
    """
    head()
    global BASE_URL
    BASE_URL = base_url
    url = f"{BASE_URL}/api/{VERSION}/handshake_rsa"
    # response = requests.get(url)
    response = requests.get(url, headers={'X-User-ID':user_id}) # mongo _id for the user document. Communicated at user creation.

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
        response = requests.post(f"{BASE_URL}/api/{VERSION}/handshake_aes", json=aes_key_payload, headers={'X-User-ID':user_id})

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
def set_user(user_id, first_name=None, last_name=None, role=None, group=None, email=None, age=None, weight=None, gender=None):
    """
    Creates a user by sending user data to the server.

    This function performs the following steps:
    1. Constructs the user data dictionary.
    2. Validates the user data against the "userSchema".
    3. Encrypts the user data using the stored AES key.
    4. Sends the encrypted user data to the server.
    5. Handles the server's response.

    Args:     
    **user_id** (*str*): The user id (obtained through free registration with HABS)
    **first_name** (*str*, optional): The user's first name.      
    **last_name** (*str*, optional): The user's last name.     
    **role** (*str*, required): The user's role (Admin, Developer, ... established at registration).     
    **group** (*str*, optional): The user's group (laboratory name, company name, ...).     
    **email** (*str*, required): The user's email address.     
    **age** (*int*, optional): The user's age.     
    **weight** (*float*, optional): The user's weight.     
    **gender** (*str*, optional): The user's gender.      

    Returns:       
        *str*: The user ID if the user is successfully created/retrieved, None otherwise.

    Example:
    ```
    user_id = set_user(first_name="John", last_name="Doe", email="john.doe@example.com", age=30, weight=70.5, gender="X")
    if user_id:
        print(f"User created/retrieved with ID: {user_id}")
    else:
        print("User creation failed.")

    **NOTE**: In order to use this function, your role should be `Admin`
    ```
    """
    url = f"{BASE_URL}/api/{VERSION}/users"
    user_data = {
        "first_name": first_name, 
        "last_name": last_name, 
        "role": role, 
        "group": group, 
        "email": email, 
        "age": age, 
        "weight": weight, 
        "gender": gender
    }
    if validate_metadata(user_data, "userSchema"):
        _user = {
            "user_data": user_data
        }
        _user = json.dumps(_user).encode('utf-8')
        aes_key_b64 = os.environ.get('AES_KEY')
        aes_key_bytes = base64.b64decode(aes_key_b64)
        response = requests.post(
            url,
            data=encrypt_message(_user, aes_key_bytes),
            headers={'Content-Type': 'application/octet-stream', 'X-User-ID':user_id}
        )

        if response.status_code == 201 or response.status_code == 208:
            print("User successfully created/retrieved.")
            user_id = response.json().get('user_id')
            return user_id
        else:
            print("User creation failed:", response.text)
            return None
    else:
        print("User creation failed.")



######################################################
def search_user_by_mail(user_id, email):
    """
    Search for a user by email.

    This function sends a GET request to the server to search for a user by the provided email address.

    Args:     
        **user_id** (*str*): The user id (obtained through free registration with HABS)
        **email** (*str*): The email address of the user to search for.

    Returns:     
        *str*: The user ID if the user is found, None otherwise.

    Example:
    ```
    user_id = search_user_by_mail("john.doe@example.com")
    if user_id:
        print(f"User found with ID: {user_id}")
    else:
        print("User not found.")
    ```
    """
    url = f"{BASE_URL}/api/{VERSION}/users/find?email={email}"

    response = requests.get(url, headers={'X-User-ID':user_id}) # mongo _id for the user document. Communicated at user creation.

    if response.status_code == 200:
        found_user_id = response.json().get('user_id')
        print("User found:", found_user_id)
        return found_user_id
    else:
        print("User not found.", response.text)
        return None



######################################################
def get_user_by_id(user_id):
    """
    Retrieve user data by user ID.

    This function sends a GET request to the server to retrieve user data for the specified user ID.     
    The response data is decrypted using AES before returning the user data.

    Args:     
        **user_id** (*str*): The unique identifier of the user to retrieve.

    Returns:     
        *dict*: The user data if the user is found, None otherwise.

    Example:
    ```
    user_data = get_user_by_id("1234567890")
    if user_data:
        print(f"User data: {user_data}")
    else:
        print("User not found.")
    ```
    """
    url = f"{BASE_URL}/api/{VERSION}/users/{user_id}"

    response = requests.get(url, headers={'X-User-ID':user_id}) # mongo _id for the user document. Communicated at user creation.

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
def list_users(user_id):
    """
    List all users.

    This function sends a GET request to the server to list all users.

    Args:     
        **user_id** (*str*): The user id (obtained through free registration with HABS)

    Returns:     
        list: A list of user data dictionaries, or None if an error occurs.

    Example:
    ```
    users = list_users(user_id)
    if users:
        for user in users:
            print(f"User ID: {user['user_id']}, Username: {user['username']}")
    ```
    """
    url = f"{BASE_URL}/api/{VERSION}/users"

    response = requests.get(url, headers={'X-User-ID': user_id})  # mongo _id for the user document. Communicated at user creation.

    if response.status_code == 200:
        users = response.json().get('users')
        print("Users retrieved.")
        return users
    else:
        print("Error:", response.text)
        return None



######################################################
def set_session(metadata, user_id):
    """
    Create a new simple session.

    This function sends a POST request to the server to create a new simple session using the provided metadata.
    The metadata is encrypted using AES before being sent to the server.

    Args:     
        **metadata** (*dict*): A dictionary containing the session metadata. The only required metadata for the simple session are the user_id and a date.
        **user_id** (*str*): The user id (obtained through free registration with HABS)

    Returns:      
        *str*: The unique identifier of the created session if successful, None otherwise.

    Example:
    ```
    session_metadata = {
        "user_id": "1076203852085",
        "session_date": "2024-05-30T12:00:00Z"
    }
    session_id = set_session(session_metadata)
    if session_id:
        print(f"Session created with ID: {session_id}")
    else:
        print("Failed to create session.")
    ```
    """
    url = f"{BASE_URL}/api/{VERSION}/sessions"
    _session = metadata
    _session = json.dumps(_session).encode('utf-8')
    aes_key_b64 = os.environ.get('AES_KEY')
    aes_key_bytes = base64.b64decode(aes_key_b64)
    response = requests.post(
        url,
        data=encrypt_message(_session, aes_key_bytes),
        headers={'Content-Type': 'application/octet-stream', 'X-User-ID':user_id}
    )

    if response.status_code == 200:
        print("Session successfully created.")
        # Extract the unique identifier for the uploaded data
        session_id = response.json().get('session_id')

        # print("session_id: ",session_id)
        return session_id
    else:
        print("Session failed:", response.text)
        return None



######################################################
def end_session(session_id, user_id):
    """
    Notify the end of a session.

    This function sends a POST request to notify the server the session (of the provided id) is ended.
    The metadata is encrypted using AES before being sent to the server.

    Args:     
        **session_id** (*str*): The session identifier.
        **user_id** (*str*): The user id (obtained through free registration with HABS)

    Returns:      
        *str*: The unique identifier of the ended session if successful, None otherwise.
    """
    url = f"{BASE_URL}/api/{VERSION}/sessions/{session_id}/end"
    response = requests.post(url, headers={'X-User-ID': user_id})  # mongo _id for the user document. Communicated at user creation.

    if response.status_code == 200:
        print("Session successfully ended.")
        return session_id
    else:
        print("Session ending failed:", response.text)
        return None



######################################################
def get_data_by_id(data_id, user_id):
    """
    Retrieve raw data by its unique identifier from the server.

    This function sends a GET request to fetch raw data associated with a specific identifier. It
    assumes that the data, if retrieved successfully, does not require decryption and is directly accessible.

    Args:      
        **data_id** (*str*): The unique identifier for the data to be retrieved.
        **user_id** (*str*): The user id (obtained through free registration with HABS)

    Returns:       
        **dict**: The raw data if retrieval is successful, None otherwise.

    Example:
    ```
    data_id = "1234"
    raw_data = get_data_by_id(data_id)
    ... use the data
    ```
    """
    url = f"{BASE_URL}/api/{VERSION}/rawdata/{data_id}"
    
    # response = requests.get(url)
    response = requests.get(url, headers={'X-User-ID':user_id}) # mongo _id for the user document. Communicated at user creation.

    if response.status_code == 200:
        print("Retrieved data successfully.")
        # decrypt
        return response.json().get('rawData')
    else:
        print("Failed to retrieve data:", response.text)



######################################################
def find_sessions_by_user(user_id):
    """
    Retrieve session IDs associated with a given user.

    This function sends a GET request to the API to retrieve all session IDs for a specified user.
    It expects the user ID to be passed as an argument and uses the user ID for authentication.

    Args:
        user_id (str): The user ID (obtained through free registration with HABS).

    Returns:
        list: A list of session IDs if the request is successful.

    Raises:
        Exception: If the request fails or if there is an error in the response.

    Example:
        >>> sessions = find_sessions_by_user("12345")
        >>> print(sessions)
        ["session1", "session2", "session3"]

    Notes:
        Ensure that the environment variable `AES_KEY` is set to the base64 encoded AES key.
    """
    url = f"{BASE_URL}/api/{VERSION}/sessions/{user_id}"

    response = requests.get(url, headers={'X-User-ID':user_id}) # mongo _id for the user document. Communicated at user creation.

    if response.status_code == 200:
        print("User found.")
        encrypted_data = response.content 
        aes_key_b64 = os.environ.get('AES_KEY')
        aes_key_bytes = base64.b64decode(aes_key_b64)
        decrypted_json_string = decrypt_message(encrypted_data, aes_key_bytes)
        session_ids = json.loads(decrypted_json_string)['session_ids']
        return session_ids
    else:
        print("Failed to retrieve data:", response.text)



######################################################
def get_data_by_session(session_id, user_id):
    """
    Retrieve raw data associated with a specific session identifier from the server.

    This function sends a GET request to fetch all raw data linked to the given session ID. The data
    is returned in its raw form assuming it does not require decryption for usage.

    Args:      
        **session_id** (*str*): The session identifier whose associated data is to be retrieved.
        **user_id** (*str*): The user id (obtained through free registration with HABS)

    Returns:       
        *dict*: The raw data linked to the session if retrieval is successful, None otherwise.

    Example:
    ```
    session_id = "abcd1234"
    session_data = get_data_by_session(session_id)
    if session_data:
        print("Data retrieved:", session_data)
    else:
        print("Failed to retrieve data.")
    ```
    """
    if session_id:
        url = f"{BASE_URL}/api/{VERSION}/sessions/{session_id}/rawdata"
        
        # response = requests.get(url)
        response = requests.get(url, headers={'X-User-ID':user_id}) # mongo _id for the user document. Communicated at user creation.
        
        if response.status_code == 200:
            print("Retrieved data successfully.")
            # decrypt
            return response.json().get('data')
        else:
            print("Failed to retrieve data:", response.text)
    else:
        print("Invalid session_id.")



######################################################
def get_data_ids_by_session(session_id, user_id):
    """
    Retrieve a list of data IDs associated with a specific session from the server.

    This function sends a GET request to fetch the IDs of all data entries linked to a specified session ID.
    The IDs are returned as a list. The function assumes the data does not require decryption for usage.

    Args:      
        **session_id** (*str*): The session identifier for which data IDs are to be retrieved.
        **user_id** (*str*): The user id (obtained through free registration with HABS)

    Returns:       
        *list*: A list of data IDs if retrieval is successful, None otherwise.

    Example:
    ```
    session_id = "abcd1234"
    data_ids = get_data_ids_by_session(session_id)
    if data_ids:
        print("Data IDs retrieved:", data_ids)
    else:
        print("Failed to retrieve data IDs.")
    ```
    """
    if session_id:
        url = f"{BASE_URL}/api/{VERSION}/sessions/{session_id}/ids"
        
        # response = requests.get(url)
        response = requests.get(url, headers={'X-User-ID':user_id}) # mongo _id for the user document. Communicated at user creation.
        
        if response.status_code == 200:
            print("Retrieved ids successfully.")
            # decrypt
            return response.json().get('ids')
        else:
            print("Failed to retrieve ids:", response.text)
    else:
        print("Invalid session_id.")



######################################################
def upload_data(metadata, timestamps, user_id, data, ppg_red, ppg_ir):
    """
    Uploads EEG (and PPG) data to the server along with associated metadata.

    This function compiles different types of physiological data along with metadata into a single dictionary,
    encrypts the data, and then uploads it via a POST request. Upon successful upload, the server returns a
    unique identifier for the data which can then be used for future queries or operations.

    Args:     
        **metadata** (*dict*): Information about the data such as subject details and session parameters.     
        **timestamps** (*list*): List of timestamps correlating with each data point.     
        **user_id** (*str*): The user id (obtained through free registration with HABS)
        **data** (*list*): EEG data points.     
        **ppg_red** (*list*): Red photoplethysmogram data points.     
        **ppg_ir** (*list*): Infrared photoplethysmogram data points.      

    Returns:     
        *tuple*: A tuple containing the data ID of the uploaded data if successful, and None otherwise.

    Notes:
        Ensure that timestamps has the same length of data last dimension.

    Example:
    ```
    metadata = {"session_id": "1234", "subject_id": "001"}
    timestamps = [1597709184, 1597709185]
    data = [0.1, 0.2]
    ppg_red = [123, 124]
    ppg_ir = [125, 126]
    data_id, error = upload_data(metadata, timestamps, data, ppg_red, ppg_ir)
    if data_id:
        print("Data uploaded successfully. Data ID:", data_id)
    else:
        print("Upload failed with error:", error)
    ```
    """
    url = f"{BASE_URL}/api/{VERSION}/rawdata"
    _data = {
        "metadata": metadata,
        "timestamps": timestamps,
        "data": data,
        "ppg_red": ppg_red,
        "ppg_ir": ppg_ir
    }
    _data = json.dumps(_data).encode('utf-8')

    # response = requests.post(url, json=_data)
    aes_key_b64 = os.environ.get('AES_KEY')
    aes_key_bytes = base64.b64decode(aes_key_b64)
    response = requests.post(
        url,
        data=encrypt_message(_data, aes_key_bytes),
        headers={'Content-Type': 'application/octet-stream', 'X-User-ID':user_id}
    )
    # response = requests.get(url, headers={'X-User-ID':USERID}) # mongo _id for the user document. Communicated at user creation.

    if response.status_code == 200:
        # print('.', end='', flush=True)
        # Extract the unique identifier for the uploaded data
        data_id = response.json().get('data_id')
        return data_id, None
    else:
        print("Upload failed:", response.text)
        return None



######################################################
def acquire_send_raw(user_id, date, board, serial_number, serial_port, stream_duration, buffer_duration, session_type="", tags=[], callback=None, extra=None, session_callback=None):
    """
    Asynchronously acquires raw data from a specific EEG board and sends it to the server.

    This function connects to an EEG board, initiates a data acquisition session, and sends the collected data
    to the server in real-time or near real-time. It ensures that all the data handled during the session
    is associated with a unique session ID and metadata that includes user and session details. The function
    will validate the session metadata before proceeding with data acquisition and sending.

    Args:      
    **user_id** (*str*): The unique identifier of the user for whom the data is being collected.      
    **date** (*str*): The date of the session, used for metadata purposes.     
    **board** (*int*): Identifier for the EEG board from which data will be acquired.      
    **stream_duration** (*int*): Duration in seconds for which data will be streamed from the board.     
    **buffer_duration** (*int*): Time in seconds for how often the data is buffered and sent.     

    Returns:     
    *str* or *bool*: The session ID if the operation is successful; False otherwise.

    Raises:
    **ConnectionError**: If the board connection fails.      
    **ValidationError**: If the metadata does not comply with the required schema.

    Example:
    ```
    session = acquire_send_raw('user123', '2021-06-01', 'MUSE_S', 300, 10)
    if session:
        print(f"Session successfully started with ID: {session}")
    else:
        print("Failed to start session")
    ```
    """
    # set session for the data
    # We set a session id for the current interaction with the API (even if we fail to get the board, it will be important to store the failure)
    session_metadata = {
      "user_id": user_id, # add user to the session for reference
      "session_date": date,
      "session_type": session_type,
      "session_tags": tags
    }
    session_id = set_session(metadata={**session_metadata}, user_id=user_id)
    print("\nSession initialized. You can visualize it here:\n ", "https://habs.ai/live.html?session_id="+str(session_id), "\n")

    if session_id:
        if session_callback:
            session_callback(session_id)
            
        if validate_metadata(session_metadata, "sessionSchema"):
            asyncio.run( 
                _acquire_send_raw(user_id, session_id, board, serial_number, serial_port, stream_duration, buffer_duration, callback, extra) 
            )
            
            # Here send request to notify the endo of the session
            end_session(session_id=session_id, user_id=user_id)

            return session_id
        else:
            print("Session initialization failed.")
            return False
    else:
        print("Session initialization failed.")
        return False

# async appendage
async def _acquire_send_raw(user_id, session_id, board, serial_number, serial_port, stream_duration, buffer_duration, callback=None, extra=None):
    # get board
    board_manager = BoardManager(enable_logger=False, board_id=board, serial_number=serial_number, serial_port=serial_port, extra=extra)
    if board=="SYNTHETIC":
        board_manager.assign_extra(extra)
    board_manager.connect()

    board_manager.metadata['session_id'] = session_id # add session to the data for reference

    # stream_duration sec, buffer_duration sec
    await board_manager.data_acquisition_loop(
        stream_duration=stream_duration, 
        buffer_duration=buffer_duration, 
        service=upload_data,
        user_id=user_id,
        callback=callback
    )




######################################################
def retry_upload_data(metadata, timestamps, user_id, data, ppg_red, ppg_ir):
    """
    Uploads EEG (and PPG) data to the server along with associated metadata (retrying if timeout or connection error).

    This function compiles different types of physiological data along with metadata into a single dictionary,
    encrypts the data, and then uploads it via a POST request. Upon successful upload, the server returns a
    unique identifier for the data which can then be used for future queries or operations.

    Args:     
        **metadata** (*dict*): Information about the data such as subject details and session parameters.     
        **timestamps** (*list*): List of timestamps correlating with each data point.     
        **user_id** (*str*): The user id (obtained through free registration with HABS)
        **data** (*list*): EEG data points.     
        **ppg_red** (*list*): Red photoplethysmogram data points.     
        **ppg_ir** (*list*): Infrared photoplethysmogram data points.      

    Returns:     
        *tuple*: A tuple containing the data ID of the uploaded data if successful, and None otherwise.

    Notes:
        Ensure that timestamps has the same length of data last dimension.

    Example:
    ```
    metadata = {"session_id": "1234", "subject_id": "001"}
    timestamps = [1597709184, 1597709185]
    data = [0.1, 0.2]
    ppg_red = [123, 124]
    ppg_ir = [125, 126]
    data_id, error = upload_data(metadata, timestamps, data, ppg_red, ppg_ir)
    if data_id:
        print("Data uploaded successfully. Data ID:", data_id)
    else:
        print("Upload failed with error:", error)
    ```
    """
    url = f"{BASE_URL}/api/{VERSION}/rawdata"
    _data = {
        "metadata": metadata,
        "timestamps": timestamps,
        "data": data,
        "ppg_red": ppg_red,
        "ppg_ir": ppg_ir
    }
    _data = json.dumps(_data).encode('utf-8')

    # response = requests.post(url, json=_data)
    aes_key_b64 = os.environ.get('AES_KEY')
    aes_key_bytes = base64.b64decode(aes_key_b64)

    session = get_retry_session()
    try:
        response = session.post(
            url=url,
            data=encrypt_message(_data, aes_key_bytes),
            headers={'Content-Type': 'application/octet-stream', 'X-User-ID':user_id},
            timeout=10
        )
        response.raise_for_status()  # Raise error if request fails

        if response.status_code == 200:
            # print('.', end='', flush=True)
            # Extract the unique identifier for the uploaded data
            data_id = response.json().get('data_id')
            return data_id, None
        else:
            print("Upload failed:", response.text)
            return None

    except requests.exceptions.RequestException as e:
        print(f"Upload failed:: {e}")
    finally:
        session.close()


def acquire_eeg_data(user_id, session_id, board, serial_number, serial_port, stream_duration, buffer_duration, callback=None, extra=None):
    # get board
    board_manager = BoardManager(enable_logger=False, board_id=board, serial_number=serial_number, serial_port=serial_port, extra=extra)
    if board=="SYNTHETIC":
        board_manager.assign_extra(extra)
    board_manager.connect()

    board_manager.metadata['session_id'] = session_id # add session to the data for reference

    # stream_duration sec, buffer_duration sec
    board_manager.data_acquisition(
        stream_duration=stream_duration, 
        buffer_duration=buffer_duration, 
        service=retry_upload_data,
        user_id=user_id,
        callback=callback
    )





######################################################
def send_file(user_id, date, edf_file, ch_nrs=None, ch_names=None, session_type="", tags=[]):
    """
    Uploads EEG data from a file to the server along with associated metadata.

    This function compiles EEG data from an [EDF file](https://www.edfplus.info/downloads/index.html) along with metadata into a single dictionary,
    encrypts the data, and then uploads it via a POST request. Upon successful upload, the server returns a
    unique identifier for the session which can then be used for future queries or operations.

    Args:    
    **user_id** (*str*): The unique identifier of the user for whom the data is being collected.     
    **metadata** (*dict*): Information about the data such as subject details and session parameters.     
    **date** (*str*): The date of the session, used for metadata purposes.     
    **edf_file** (*str*): name of an EDF file.      
    **ch_nrs** (*list of int*, optional): The indices of the channels to read. The default is None.     
    **ch_names** (*list of str*, optional): The names of channels to read. The default is None.     

    Returns:     
        *tuple*: A tuple containing the session ID of the uploaded data if successful, and None otherwise.

    Example:
    ```
    session = send_file('user123', '2021-06-01', 'nameoffile.edf')
    if session:
        print(f"Session successfully started with ID: {session}")
    else:
        print("Failed to start session")
    ```
    """

    try:
        signals, signal_headers, header = highlevel.read_edf(edf_file, ch_nrs, ch_names)

        max_time = signals.shape[1] / signal_headers[0]['sample_frequency']
        timestamps = np.linspace(header['startdate'].timestamp(), max_time, signals.shape[1])

        session_metadata = {
          "user_id": user_id, # add user to the session for reference
          "session_date": str(header['startdate'].strftime("%m/%d/%Y, %H:%M:%S")),
          "session_type": session_type,
          "session_tags": tags
        }
        if validate_metadata(session_metadata, "sessionSchema"):
            session_id = set_session(metadata={**session_metadata}, user_id=user_id)
            header['startdate'] = str(header['startdate'])
            metadata = {'session_id':session_id, **session_metadata, **header, **signal_headers[0]}

            chunks = ((signals.size * signals.itemsize)//300000)+1
            timestamps_chunks = np.array_split(timestamps, chunks)
            signals_chunks = np.array_split(signals, chunks, axis=1)
            json_data = json.dumps(signals_chunks[0].tolist())
            size_in_bytes = sys.getsizeof(json_data)
            print("%d total bytes will be sent into %d chunks of %d bytes" % (signals.size * signals.itemsize, chunks, size_in_bytes))

            for timestamps_chunk,signals_chunk in zip(timestamps_chunks, signals_chunks):
                upload_data(metadata, timestamps_chunk.tolist(), user_id, signals_chunk.tolist(), [], [])

            return session_id
        else:
            return False
    except Exception as e:
        print("A general error occurred:", e)
        return False    



######################################################
######################################################
#   SERVICES
######################################################
######################################################

def acquire_send_service(service_name, user_id, date, board, serial_number, serial_port, stream_duration, buffer_duration, session_type="", tags=[], callback=None, extra=None):
    """
    Acquires data from a board, sends it to Cognitive OS, which processes it according to the specified service.
    This function handles setting up a session for data acquisition and processing, connects to a board, 
    and manages the data flow from acquisition through processing to uploading. It uses an asynchronous loop
    to handle the operations efficiently, suitable for real-time data processing scenarios.

    Args:
    **service_name** (*str*): Name of the service as from the Cognitive OS list.      
    **user_id** (*str*): The user ID to which the session will be associated.      
    **date** (*str*): Date of the session for tracking purposes.      
    **board** (*int*): Identifier for the hardware board to use for data acquisition.      
    **stream_duration** (*int*): Duration in seconds to stream data from the board.     
    **buffer_duration** (*int*): Duration in seconds to buffer data before processing.      
    **callback** (*function*): Optional callback function to execute with the processed data.

    Returns:    
        *str* or *bool*: The session ID if successful, False otherwise.

    """
    # set session for the data
    # We set a session id for the current interaction with the API (even if we fail to get the board, it will be important to store the failure)
    session_metadata = {
      "user_id": user_id, # add user to the session for reference
      "session_date": date,
      "session_type": session_type,
      "session_tags": tags
    }
    print("acquire_send_service:",session_metadata)
    if validate_metadata(session_metadata, "sessionSchema"):
        session_id = set_service(service_name=service_name, metadata={**session_metadata}, user_id=user_id)
        if session_id:
            print("\nSession initialized. You can visualize it here:\n ", "https://habs.ai/CognitiveOS/live.html?session_id="+str(session_id), "\n")

            asyncio.run( 
                _acquire_send_service(service_name, user_id, session_id, board, serial_number, serial_port, stream_duration, buffer_duration, callback, extra) 
            )
            
            # Here send request to notify the endo of the session
            end_session(session_id=session_id, user_id=user_id)

            return session_id
        else:
            print("Session initialization failed.")
            return False
    else:
        print("Session initialization failed.")
        return False

# async appendage
async def _acquire_send_service(service_name, user_id, session_id, board, serial_number, serial_port, stream_duration, buffer_duration, callback=None, extra=None):
    # get board
    board_manager = BoardManager(enable_logger=False, board_id=board, serial_number=serial_number, serial_port=serial_port, extra=extra)
    if board=="SYNTHETIC":
        board_manager.assign_extra(extra)
    board_manager.connect()

    board_manager.metadata['session_id'] = session_id # add session to the data for reference
    # stream_duration sec, buffer_duration sec
    await board_manager.data_acquisition_loop(
        stream_duration=stream_duration, 
        buffer_duration=buffer_duration, 
        service=upload_servicedata,
        user_id=user_id,
        callback=callback
    )



# @encrypt_request_data
def set_service(service_name, metadata, user_id):
    """
    Configures and initiates a session on the Cognitive OS for a service.

    This function sends metadata to a specified service endpoint to create a data processing session. 
    It encrypts the session data before sending to ensure security. 
    The function checks the server response to confirm the session creation.

    Args:     
    **service_name** (*str*): Name of the service as from the Cognitive OS list.      
    **metadata** (*dict*): A dictionary containing metadata about the session, including
                     details such as user ID and session date.       
    **user_id** (*str*): The user id (obtained through free registration with HABS)

    Returns:       
        *str* or *None*: The session ID if the session is successfully created, or None if the operation fails.

    Raises:     
        **requests.exceptions.RequestException**: An error from the Requests library when an HTTP request fails.      
        **KeyError**: If necessary keys are missing in the environment variables.

    Example:
    ```
    session_metadata = {"user_id": "123", "session_date": "2024-06-03"}
    processing_params = {"filter_type": "lowpass", "cutoff_freq": 30}
    session_id = set_service(session_metadata, user_id='3284682750346')
    if session_id:
        print(f"Service session created with ID: {session_id}")
    else:
        print("Failed to create service session")
    ```
    """
    url = f"{BASE_URL}/api/{VERSION}/services/{service_name}"

    _session = {
        "metadata": metadata,
        "user_id": user_id
    }

    # The _session data will be encrypted by the decorator
    response = requests.post(
        url,
        data=json.dumps(_session).encode('utf-8'),
        headers={'Content-Type': 'application/octet-stream', 'X-User-ID': user_id}
    )

    if response.status_code == 200:
        print("Session successfully created.")
        session_id = response.json().get('session_id')
        return session_id
    else:
        print("Session failed:", response.text)
        return None


# @encrypt_request_data
def upload_servicedata(metadata, timestamps, user_id, data, ppg_red, ppg_ir):
    """
    Uploads data to a specific session on the server.

    This function is responsible for uploading various data streams associated with a session, 
    including timestamps and physiological measurements. The data is encrypted before
    sending to ensure confidentiality and integrity.

    Args:        
    **metadata** (*dict*): Contains session-related metadata including the session ID.      
    **timestamps** (*list*): A list of timestamps corresponding to each data point.      
    **user_id** (*str*): The user id (obtained through free registration with HABS)
    **data** (*list*): The main data collected, e.g., EEG readings.      
    **ppg_red** (*list*): Red channel data from a PPG sensor.    
    **ppg_ir** (*list*): Infrared channel data from a PPG sensor.     

    Returns:     
    *tuple*: A tuple containing the data ID if the upload is successful and the processed data, or None if the upload fails.

    Raises:     
    **requests.exceptions.RequestException: An error from the Requests library when an HTTP request fails.
    **KeyError**: If necessary keys are missing in the environment variables.

    Example:
    ```
    session_metadata = {"session_id": "12345"}
    timestamps = [1597709165, 1597709166, ...]
    data = [0.1, 0.2, ...]
    ppg_red = [12, 15, ...]
    ppg_ir = [20, 22, ...]
    data_id, processed_data = upload_servicedata(session_metadata, timestamps, data, ppg_red, ppg_ir)
    if data_id:
        print(f"Data uploaded successfully with ID: {data_id}")
    else:
        print("Failed to upload data")
    ```
    """
    url = f"{BASE_URL}/api/{VERSION}/servicedata/{metadata['session_id']}" # the metadata contain session_id to consistently pass it with each upload

    _data = {
        "metadata": metadata,
        "timestamps": timestamps,
        "data": data,
        "ppg_red": ppg_red,
        "ppg_ir": ppg_ir
    }
    _data = json.dumps(_data).encode('utf-8')
    aes_key_b64 = os.environ.get('AES_KEY')
    aes_key_bytes = base64.b64decode(aes_key_b64)
    response = requests.post(
        url,
        data=_data,
        headers={'Content-Type': 'application/octet-stream', 'X-User-ID':user_id}
    )

    # subscribe to response
    if response.status_code == 200:
        print(':', end='', flush=True)
        task_id = response.json().get('task_id')
        # print("task_id: ",task_id)
        subscription_response = requests.get(f"{BASE_URL}/api/{VERSION}/results/subscribe/{task_id}", headers={'X-User-ID': user_id}, stream=True)
        # if subscription_response.status_code == 200:
        #     if "error" in subscription_response.text:
        #         print("Session failed:", subscription_response.text)
        #         return task_id, None
        #     processed_data = subscription_response.json().get('pipeData')
        #     return task_id, processed_data
        if subscription_response.status_code == 200:
            processed_data = []
            # Stream the response line by line
            for line in subscription_response.iter_lines(decode_unicode=True):
                if line:  # Skip empty lines
                    if "success" in line:  
                        try:
                            # parse the JSON payload
                            event_data = json.loads(line)
                            if event_data.get('status') == 'success':
                                processed_data.extend( event_data.get('pipeData', []) )  # Append data progressively
                                print(f"Received page {event_data.get('page')} of {event_data.get('total_pages')}")
                            elif event_data.get('status') == 'completed':
                                print("Data streaming complete.")
                                break
                            elif event_data.get('status') == 'error':
                                print("Error in data stream:", event_data.get('error'))
                                return task_id, None
                        except json.JSONDecodeError as e:
                            print("JSON decode error:", e)
            return task_id, processed_data
    else:
        print("Upload failed:", response.text)
        return None




######################################################
######################################################
#   PROCESSING PIPE
######################################################
######################################################
def set_pipe(metadata, pipeline, params, user_id):
    """
    Configures and initiates a data processing pipeline for a session on the server.

    This function sends metadata and processing parameters to a specified pipeline endpoint
    to create a data processing session. It encrypts the session data before sending to ensure
    security. The function checks the server response to confirm the session creation.

    Args:     
    **metadata** (*dict*): A dictionary containing metadata about the session, typically including
                     details such as user ID and session date.       
    **pipeline** (*str*): The identifier for the processing pipeline to be used.      
    **params** (*dict*): Parameters specific to the processing pipeline, detailing how data should
                   be processed.      
    **user_id** (*str*): The user id (obtained through free registration with HABS)

    Returns:       
        *str* or *None*: The session ID if the session is successfully created, or None if the operation fails.

    Raises:     
        **requests.exceptions.RequestException**: An error from the Requests library when an HTTP request fails.      
        **KeyError**: If necessary keys are missing in the environment variables.

    Example:
    ```
    session_metadata = {"user_id": "123", "session_date": "2024-06-03"}
    processing_params = {"filter_type": "lowpass", "cutoff_freq": 30}
    session_id = set_pipe(session_metadata, 'eeg_smoothing', processing_params)
    if session_id:
        print(f"Pipeline session created with ID: {session_id}")
    else:
        print("Failed to create pipeline session")
    ```
    """
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
        headers={'Content-Type': 'application/octet-stream', 'X-User-ID':user_id}
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




def upload_pipedata(metadata, timestamps, user_id, data, ppg_red, ppg_ir):
    """
    Uploads data to a specific session on the server.

    This function is responsible for uploading various data streams associated with a session, including
    timestamps and physiological measurements such as PPG (Photoplethysmogram). The data is encrypted before
    sending to ensure confidentiality and integrity.

    Args:        
    **metadata** (*dict*): Contains session-related metadata including the session ID.      
    **timestamps** (*list*): A list of timestamps corresponding to each data point.      
    **user_id** (*str*): The user id (obtained through free registration with HABS)
    **data** (*list*): The main data collected, e.g., EEG readings.      
    **ppg_red** (*list*): Red channel data from a PPG sensor.    
    **ppg_ir** (*list*): Infrared channel data from a PPG sensor.     

    Returns:     
    *tuple*: A tuple containing the data ID if the upload is successful and the processed data, or None if the upload fails.

    Raises:     
    **requests.exceptions.RequestException: An error from the Requests library when an HTTP request fails.
    **KeyError**: If necessary keys are missing in the environment variables.

    Example:
    ```
    session_metadata = {"session_id": "12345"}
    timestamps = [1597709165, 1597709166, ...]
    data = [0.1, 0.2, ...]
    ppg_red = [12, 15, ...]
    ppg_ir = [20, 22, ...]
    data_id, processed_data = upload_pipedata(session_metadata, timestamps, data, ppg_red, ppg_ir)
    if data_id:
        print(f"Data uploaded successfully with ID: {data_id}")
    else:
        print("Failed to upload data")
    ```
    """
    url = f"{BASE_URL}/api/{VERSION}/pipedata/{metadata['session_id']}" # the metadata contain session_id to consistently pass it with each upload

    _data = {
        "metadata": metadata,
        "timestamps": timestamps,
        "data": data,
        "ppg_red": ppg_red,
        "ppg_ir": ppg_ir
    }
    _data = json.dumps(_data).encode('utf-8')
    aes_key_b64 = os.environ.get('AES_KEY')
    aes_key_bytes = base64.b64decode(aes_key_b64)
    response = requests.post(
        url,
        data=encrypt_message(_data, aes_key_bytes),
        headers={'Content-Type': 'application/octet-stream', 'X-User-ID':user_id}
    )

    # subscribe to response
    if response.status_code == 200:
        print('.', end='', flush=True)
        task_id = response.json().get('task_id')
        # print("task_id: ",task_id)
        subscription_response = requests.get(f"{BASE_URL}/api/{VERSION}/results/subscribe/{task_id}", headers={'X-User-ID': user_id}, stream=True)
        if subscription_response.status_code == 200:
            processed_data = []
            # Stream the response line by line
            for line in subscription_response.iter_lines(decode_unicode=True):
                if line:  # Skip empty lines
                    if "success" in line:  
                        try:
                            # parse the JSON payload
                            event_data = json.loads(line)
                            if event_data.get('status') == 'success':
                                processed_data.extend( event_data.get('pipeData', []) )  # Append data progressively
                                print(f"Received page {event_data.get('page')} of {event_data.get('total_pages')}")
                            elif event_data.get('status') == 'completed':
                                print("Data streaming complete.")
                                break
                            elif event_data.get('status') == 'error':
                                print("Error in data stream:", event_data.get('error'))
                                return task_id, None
                        except json.JSONDecodeError as e:
                            print("JSON decode error:", e)
            return task_id, processed_data
    else:
        print("Upload failed:", response.text)
        return None




def acquire_send_pipe(pipeline, params, user_id, date, board, serial_number, serial_port, stream_duration, buffer_duration, session_type="", tags=[], callback=None, extra=None):
    """
    Acquires data from a board, sends it to Cognitive OS, which processes it according to the specified pipeline.
    This function handles setting up a session for data acquisition and processing, connects to a board, 
    and manages the data flow from acquisition through processing to uploading. It uses an asynchronous loop
    to handle the operations efficiently, suitable for real-time data processing scenarios.

    Args:
    **pipeline** (*str*): Name of the processing pipeline to use.     
    **params** (*dict*): Parameters for the pipeline processing.      
    **user_id** (*str*): The user ID to which the session will be associated.      
    **date** (*str*): Date of the session for tracking purposes.      
    **board** (*int*): Identifier for the hardware board to use for data acquisition.      
    **stream_duration** (*int*): Duration in seconds to stream data from the board.     
    **buffer_duration** (*int*): Duration in seconds to buffer data before processing.      
    **callback** (*function*): Optional callback function to execute after data is sent.

    Returns:    
        *str* or *bool*: The session ID if successful, False otherwise.

    """
    # set session for the data
    # We set a session id for the current interaction with the API (even if we fail to get the board, it will be important to store the failure)
    session_metadata = {
      "user_id": user_id, # add user to the session for reference
      "session_date": date,
      "session_type": session_type,
      "session_tags": tags
    }
    print("acquire_send_pipe:",session_metadata)
    if validate_metadata(session_metadata, "sessionSchema"):
        session_id = set_pipe(metadata={**session_metadata}, pipeline=pipeline, params=params, user_id=user_id)
        if session_id:
            print("\nSession initialized. You can visualize it here:\n ", "https://habs.ai/bos/live.html?session_id="+str(session_id), "\n")

            asyncio.run( 
                _acquire_send_pipe(pipeline, params, user_id, session_id, board, serial_number, serial_port, stream_duration, buffer_duration, callback, extra) 
            )
            
            # Here send request to notify the endo of the session
            end_session(session_id=session_id, user_id=user_id)

            return session_id
        else:
            print("Session initialization failed.")
            return False
    else:
        print("Session initialization failed.")
        return False

# async appendage
async def _acquire_send_pipe(pipeline, params, user_id, session_id, board, serial_number, serial_port, stream_duration, buffer_duration, callback=None, extra=None):
    # get board
    board_manager = BoardManager(enable_logger=False, board_id=board, serial_number=serial_number, serial_port=serial_port, extra=extra)
    if board=="SYNTHETIC":
        board_manager.assign_extra(extra)
    board_manager.connect()

    board_manager.metadata['session_id'] = session_id # add session to the data for reference
    # stream_duration sec, buffer_duration sec
    await board_manager.data_acquisition_loop(
        stream_duration=stream_duration, 
        buffer_duration=buffer_duration, 
        service=upload_pipedata,
        user_id=user_id,
        callback=callback
    )




######################################################
######################################################
#   TAGGING
######################################################
######################################################
def create_tagged_interval(user_id, session_id, start_time, end_time, tags, channel_ids=None):
    """
    Creates a tagged interval by sending the interval data to the server.

    This function performs the following steps:
    1. Constructs the interval data dictionary.
    2. Validates the interval data against the "tagSchema".
    3. Sends the interval data to the server.

    Args:
    **session_id** (*str*): The session id.
    **start_time** (*str*): The start time of the interval in ISO 8601 format.
    **end_time** (*str*): The end time of the interval in ISO 8601 format.
    **tags** (*list*): List of tags, each tag is a dictionary containing a "tag" and "properties".
    **channel_ids** (*list*, optional): List of channel ids the tag applies to. If None, applies to all channels.

    Returns:
        *str*: The interval ID if the interval is successfully created, None otherwise.

    Example:
    ```
    interval_id = create_tagged_interval(
        session_id="session_123",
        start_time="2023-01-01T00:00:00Z",
        end_time="2023-01-01T00:05:00Z",
        tags=[{"tag": "seizure", "properties": {"severity": "high"}}]
    )
    if interval_id:
        print(f"Tagged interval created with ID: {interval_id}")
    else:
        print("Tagged interval creation failed.")
    ```
    """
    if session_id:
        url = f"{BASE_URL}/api/{VERSION}/session/{session_id}/tag"
        interval_data = {
            "user_id": user_id,
            "session_id": session_id,
            "start_time": start_time,
            "end_time": end_time,
            "tags": tags,
            "channel_ids": channel_ids if channel_ids else []
        }
        
        if validate_metadata(interval_data, "tagSchema"):
            response = requests.post(
                url,
                json=interval_data,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 201:
                print("Tagged interval successfully created.")
                interval_id = response.json().get('interval_id')
                return interval_id
            else:
                print("Tagged interval creation failed:", response.text)
                return None
        else:
            print("Tagged interval creation failed due to validation error.")
    else:
        print("Invalid session_id.")




def get_tagged_interval_data(user_id, session_id, tag):
    """
    Retrieves data for a specific tagged interval from the server.

    This function performs the following steps:
    1. Constructs the request URL with the session_id and tag.
    2. Sends a GET request to the server to retrieve the data.
    3. Parses the server's response.

    Args:
    **user_id** (*str*): The user id.
    **session_id** (*str*): The session id.
    **tag** (*str*): The tag associated with the interval.

    Returns:
        *dict*: The data corresponding to the tagged interval if successful, None otherwise.

    Example:
    ```
    data = get_tagged_interval_data(
        user_id="user_123",
        session_id="session_456",
        tag="seizure"
    )
    if data:
        print(f"Data retrieved for tag 'seizure': {data}")
    else:
        print("Failed to retrieve data for the specified tag.")
    ```
    """
    if session_id:
        url = f"{BASE_URL}/api/{VERSION}/session/{session_id}/tag/{tag}"

        response = requests.get(
            url,
            headers={'Content-Type': 'application/json', 'X-User-ID': user_id}
        )

        if response.status_code == 200:
            data = response.json().get('data')
            print(f"Successfully retrieved data for tag '{tag}'.")
            return data
        else:
            print(f"Failed to retrieve data: {response.text}")
            return None
    else:
        print("Invalid session_id.")




def get_tagged_intervals(user_id, session_id):
    """
    Retrieves all tagged intervals of a session.

    Args:
    **user_id** (*str*): The owner user id.
    **session_id** (*str*): The target session id.

    Returns:
        *dict*: The list of tagged intervals if successful, None otherwise.

    Example:
    ```
    data = get_tagged_intervals(
        user_id="user_123",
        session_id="session_456"
    )
    if data:
        print(f"Tags retrieved for session {session_id}")
    else:
        print("Failed to retrieve data for the specified session.")
    ```
    """
    if session_id:
        url = f"{BASE_URL}/api/{VERSION}/session/{session_id}/tags"

        try:
            response = requests.get(
                url,
                headers={'Content-Type': 'application/json', 'X-User-ID': user_id}
            )

            # Check if the request was successful
            if response.status_code == 200:
                # Extract the JSON data from the response
                data = response.json()
                
                if data.get('status') == 'success':
                    # Return the tagged intervals
                    return data.get('data', [])
                else:
                    print(f"Failed to retrieve tags: {data.get('message', 'Unknown error')}")
                    return None
            else:
                print(f"Error: Received status code {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None

    return None




def process_session_pipe(pipeline, params, user_id, date, existing_session_id, existing_tagged_interval=None, session_type="", tags=[]):
    """
    Process a session data using a pipeline with specified parameters and metadata.

    This function processes an existing session by applying a specified pipeline and parameters.
    It sends a POST request to the API with the session metadata and processing parameters,
    creating a new session based on the existing one.

    Args:
        **pipeline** (*str*): The pipeline to be applied to the session.
        **params** (*dict*): The processing parameters for the pipeline.
        **user_id** (*str*): The user ID (obtained through free registration with HABS).
        **date** (*str*): The date of the session.
        **existing_session_id** (*str*): The ID of the existing session to be processed.
        **existing_tag** (*str*, optional): The label of an existing tagged interval.
        **session_type** (*str*, optional): The type of the new session. Defaults to an empty string.
        **tags** (*list*, optional): A list of tags associated with the session. Defaults to an empty list.

    Returns:
        tuple: A tuple containing the new session ID and the processed data if the request is successful.
        None: If the session creation fails.
        bool: False if the session metadata is invalid.

    Example:
        >>> new_session_id, processed_data = process_session_pipe("my_pipeline", {"param1": "value1"}, "12345", "2023-07-03", "existing_session_001")
        >>> print(new_session_id, processed_data)

    Notes:
        Ensure that the environment variable `AES_KEY` is set to the base64 encoded AES key.

    Raises:
        Exception: If there is an error in the request or response.

    """
    if existing_session_id:
        session_metadata = {
            "user_id": user_id, 
            "session_date": date, 
            "existing_session_id": existing_session_id,
            "session_type": f"[On {existing_session_id}]: {session_type}", 
            "session_tags": tags
        }
        if validate_metadata(session_metadata, "sessionSchema"):
            url = f"{BASE_URL}/api/{VERSION}/sessions/{existing_session_id}/pipe/{pipeline}"
            if existing_tagged_interval:
                url = f"{BASE_URL}/api/{VERSION}/sessions/{existing_session_id}/pipe/{pipeline}/tagged_interval/{existing_tagged_interval}"
            _session = {
                "metadata": session_metadata,
                "processing_params": params,
                'processing_tagged_interval': existing_tagged_interval,
            }
            _session = json.dumps(_session).encode('utf-8')
            aes_key_b64 = os.environ.get('AES_KEY')
            aes_key_bytes = base64.b64decode(aes_key_b64)
            response = requests.post(
                url,
                data=encrypt_message(_session, aes_key_bytes),
                headers={'Content-Type': 'application/octet-stream', 'X-User-ID': user_id}
            )
            if response.status_code == 200:
                print("Session successfully created. Requesting results ...")
                session_id = response.json().get('session_id')
                task_id = response.json().get('task_id')

                # Stream response for progressive data handling
                subscription_response = requests.get(
                    f"{BASE_URL}/api/{VERSION}/results/subscribe/{task_id}", 
                    headers={'X-User-ID': user_id}, 
                    stream=True
                )

                if subscription_response.status_code == 200:
                    processed_data = []
                    # Stream the response line by line
                    for line in subscription_response.iter_lines(decode_unicode=True):
                        if line:  # Skip empty lines
                            if "success" in line:  
                                try:
                                    # parse the JSON payload
                                    event_data = json.loads(line)
                                    if event_data.get('status') == 'success':
                                        processed_data.extend( event_data.get('pipeData', []) )  # Append data progressively
                                        print(f"Received page {event_data.get('page')} of {event_data.get('total_pages')}")
                                    elif event_data.get('status') == 'completed':
                                        print("Data streaming complete.")
                                        break
                                    elif event_data.get('status') == 'error':
                                        print("Error in data stream:", event_data.get('error'))
                                        return task_id, None
                                except json.JSONDecodeError as e:
                                    print("JSON decode error:", e)
                    return task_id, processed_data
                else:
                    print("Session failed:", subscription_response.status_code, subscription_response.text)
            else:
                print("Session failed:", response.text)
                return None, None

            return None, None 
        else:
            print("Session failed.")
            return None, None
    else:
        print("Invalid session_id.")




######################################################
def train(session_id, params, user_id):
    """
    Sends a request to the server to train a machine learning algorithm on the data from a specified session.

    Args:     
    **session_id** (*str*): The unique identifier of the session containing the data to be used for training.       
    **params** (*dict*): The parameters for the training process.
    **user_id** (*str*): The user id (obtained through free registration with HABS)

    Returns:      
        *str* or *None*: The task ID if the request is successful, None otherwise.

    This function sends the training parameters and session ID to the server, which initiates the training process.
    The response includes a task ID that can be used for future interactions related to the training task.

    Example:
    ```
    train("session_12345", {"param1": "value1", "param2": "value2"})
    ```
    """
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
        headers={'Content-Type': 'application/octet-stream', 'X-User-ID':user_id}
    )
    # response = requests.get(url, headers={'X-User-ID':USERID}) # mongo _id for the user document. Communicated at user creation.

    if response.status_code == 200:
        task_id = response.json().get('task_id')
        print("Published. For future interactions, use task_id:",task_id)
        return task_id
    else:
        print("Publish failed:", response.text)
        return None




######################################################
def infer(data_id, params, user_id):
    """
    Sends a request to the server to perform machine learning inference based on a previously trained model, given the data ID.

    Args:     
    **data_id** (*str*): The unique identifier of the data to be used for inference.      
    **params** (*dict*): The parameters for the inference process.
    **user_id** (*str*): The user id (obtained through free registration with HABS)

    Returns:
    *str* or *None*: The task ID if the request is successful, None otherwise.

    This function sends the inference parameters and data ID to the server, which initiates the inference process.
    The response includes a task ID that can be used for future interactions related to the inference task.

    Example:
    ```
    infer("data_12345", {"param1": "value1", "param2": "value2"})
    ```
    """
    if data_id:
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
            headers={'Content-Type': 'application/octet-stream', 'X-User-ID':user_id}
        )
        # response = requests.get(url, headers={}) # mongo _id for the user document. Communicated at user creation.
        
        if response.status_code == 200:
            task_id = response.json().get('task_id')
            print("Published. For future interactions, use task_id:",task_id)
            return task_id
        else:
            print("Publish failed:", response.text)
            return None
    else:
        print("Invalid data_id")
        return None

