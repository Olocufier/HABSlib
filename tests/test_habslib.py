# USAGE:
# % pytest tests/test_habslib.py

import pytest

import requests
import time

import os
import sys
import base64
import bson
from datetime import datetime

from scipy import signal

from . import BASE_URL, VERSION, BOARD

# HABSlib
import HABSlib as hb

#################################################################
# GLOBALS
g_user_id = None
g_session_id = None
g_data_id = None

#################################################################
import uuid

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False


#################################################################
# - should create the rsa key pair
# - should reply {'status': 'success', 'api_public_key': api_public_key_pem}
# - should receive the rsa-encrypted AES key
# - should reply {'status': 'success'}

@pytest.mark.order(1)
@pytest.mark.dependency
def test_handshake():
    start_time = time.time()

    result = hb.handshake(base_url=BASE_URL, user_id='666c0158fcbfd9a830399121') 
    
    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    assert result == True



#################################################################
# Set user/subject (if the user already exists it should not creat one)
# - should fail if the required param "email" is absent
# - should reply {'status': 'success', 'user_id': str(user_id)}

@pytest.mark.order(2)
@pytest.mark.dependency
@pytest.mark.parametrize("payload, expected_status", [ 
    # pytest.param({}, 400,  marks=pytest.mark.xfail()),
    ({'first_name': 'Domenico', 'last_name': 'Guarino', 'role': 'Admin', 'group': 'HABS', 'email': 'domenico@habs.ai', 'age': 50, 'weight': 89, 'gender': 'M'}, 208)
    # ({'first_name': 'Federico', 'last_name': 'Tesler', 'role': 'Admin', 'group': 'HABS', 'email': 'federico@habs.ai', 'age': 30, 'weight': 79, 'gender': 'M'}, 200)
])
def test_set_user(payload, expected_status):
    print(payload)
    start_time = time.time()

    user_id = hb.set_user(**payload) ## CALL

    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    assert user_id is not None
    assert bson.objectid.ObjectId.is_valid(user_id)
    if bson.objectid.ObjectId.is_valid(user_id):
        global g_user_id
        g_user_id = user_id
    print("g_user_id",g_user_id)



#################################################################
# Get user data by id
# - if the user is found, should reply {'status': 'success', 'user_data': document}
# - if the user is not found, should reply {'status': 'error', 'message': 'User not found'}

@pytest.mark.order(3)
@pytest.mark.dependency(depends=["test_handshake"])
def test_get_user_by_id():
    print("g_user_id",g_user_id)
    start_time = time.time()

    user_data = hb.get_user_by_id(g_user_id)
    
    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    assert isinstance(user_data, dict)



# #################################################################
# # Search user 
# # - should receive the param "email" as get args
# # - if the user is found, should reply {'status': 'success', 'user_id': str(document['_id'])}
# # - if the user is not found, should reply {'status': 'error', 'message': f"User not found"}

# @pytest.mark.order(4)
# @pytest.mark.dependency(depends=["test_handshake"])
# @pytest.mark.parametrize("email, expected_status", [
#     ('domenico@habs.ai', 200),
#     pytest.param('non_existing@example.com', 400,  marks=pytest.mark.xfail()) # test xfail
# ])
# def test_find_user(email, expected_status):
#     start_time = time.time()
#     print(email,email)
#     user_id = hb.search_user_by_mail(email)
#     print(user_id)
#     end_time = time.time()
#     duration = end_time - start_time
#     # Attach the duration to the test report
#     # pytest.current_test_report.duration = duration
#     assert bson.objectid.ObjectId.is_valid(user_id) 



#################################################################
# Simple sending data
# - should receive the param "user_id"
# - should return the session_id, a valid bson ObjectID


@pytest.mark.order(5)
@pytest.mark.dependency(depends=["test_handshake"])
@pytest.mark.parametrize("user_id, expected_status", [
    ('g_user_id', 200),
    pytest.param('non_existing_id', 400,  marks=pytest.mark.xfail()) # test xfail
])
def test_acquire_send_raw(user_id, expected_status):
    if user_id=='g_user_id':
        user_id = g_user_id
    start_time = time.time()
    session_id = hb.acquire_send_raw(
        user_id=user_id, 
        date=datetime.today().strftime('%Y-%m-%d'), 
        board=BOARD,
        serial_number="", # in the back of the MUSE pod
        stream_duration=10, 
        buffer_duration=5)
    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    assert bson.objectid.ObjectId.is_valid(session_id)
    # update
    if bson.objectid.ObjectId.is_valid(session_id):
        global g_session_id
        g_session_id = session_id



#################################################################
# Pipe setup and sending data
# preprocessing setup, requires a bit of knowledge about the data to process
# - should receive the param "user_id"
# - should return the session_id, a valid bson ObjectID

@pytest.mark.order(6)
@pytest.mark.dependency(depends=["test_handshake"])
@pytest.mark.parametrize("user_id, expected_status", [
    ('g_user_id', 200),
    pytest.param({}, 400,  marks=pytest.mark.xfail()) # test xfail
])
def test_acquire_send_pipe(user_id, expected_status):
    b_notch, a_notch = signal.iirnotch(50., 2.0, 256)
    sos = signal.butter(10, [0.5, 40], 'bandpass', fs=256, output='sos')
    if user_id=='g_user_id':
        user_id = g_user_id
    start_time = time.time()
    session_id = hb.acquire_send_pipe(
        pipeline='/filtering/theta',
        params={ 
            # dictionary, the order does not matter, they will be called by key
            "filtering": {
                'a_notch': a_notch.tolist(),
                'b_notch': b_notch.tolist(),
                'sos': sos.tolist(),
            },
            "theta":{},
        },
        user_id=user_id, 
        date=datetime.today().strftime('%Y-%m-%d'), 
        board=BOARD,
        serial_number="", # in the back of the MUSE pod
        stream_duration=20, 
        buffer_duration=5
    )
    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    assert bson.objectid.ObjectId.is_valid(session_id)
    # update
    if bson.objectid.ObjectId.is_valid(session_id):
        global g_session_id
        g_session_id = session_id



# #################################################################
# # get data by data id
# # - should receive the param "data_id"
# # - should return a valid list
# def test_get_data_ids_by_session(data_id):
#   data = get_data_ids_by_session(data_id)



#################################################################
# get all data joined by session id (piped or raw)
# - should receive the param "session_id"
# - should return a valid list

@pytest.mark.order(7)
@pytest.mark.dependency(depends=["test_handshake"])
@pytest.mark.parametrize("session_id, expected_status", [
    ('g_session_id', 200),
    pytest.param({}, 400,  marks=pytest.mark.xfail()) # test xfail
])
def test_get_data_by_session(session_id, expected_status):
    if session_id=='g_session_id':
        session_id = g_session_id
    start_time = time.time()
    results = hb.get_data_by_session(session_id=session_id, user_id=user_id)
    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    # print(results)
    assert isinstance(results, list)



#################################################################
# send session_id to ask AI training 
# - should receive the param "session_id"
# - should return a valid list

# @pytest.mark.order(8)
# @pytest.mark.dependency(depends=["test_handshake"])
# @pytest.mark.parametrize("session_id, params, expected_status", [
#     ('g_session_id',{'model':'test', 'session_id':''}, 200),
#     pytest.param('662fc1430e155332ac5ace1f', {}, 400,  marks=pytest.mark.xfail()) # test xfail
# ])
# def test_train(session_id, params, expected_status):
#     if session_id=='g_session_id':
#         session_id = g_session_id
#         params['session_id'] = g_session_id
#     start_time = time.time()
#     task_id = hb.train(
#         session_id=session_id, 
#         params=params)
#     end_time = time.time()
#     duration = end_time - start_time
#     # Attach the duration to the test report
#     # pytest.current_test_report.duration = duration
#     assert is_valid_uuid(task_id)


