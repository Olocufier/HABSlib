# Configuration fixtures for the tests
# 
# pip install pytest
# pip install pytest-html
# 
# run tests, in order:
# (os)$ pytest tests/test_handshake.py --html=report.html --self-contained-html
# (os)$ pytest tests/test_user.py --html=report.html --self-contained-html
# (os)$ pytest tests/test_session.py --html=report.html --self-contained-html
# (os)$ pytest tests/test_data.py --html=report.html --self-contained-html
# (os)$ pytest tests/test_train.py --html=report.html --self-contained-html
# 
# run all tests
# (os)$ pytest tests --durations=10 --durations-min=1.0 --html=report.html --self-contained-html


import pytest
import time
from pytest_html import extras

import sys
import os
print(os.path.abspath(os.path.join(os.path.dirname(__file__), '../HABSlib/')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../HABSlib/')))

from crypt import store_public_key, load_public_key, generate_aes_key, encrypt_aes_key_with_rsa, encrypt_message, decrypt_message
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


##### later, html report

# @pytest.hookimpl(tryfirst=True, hookwrapper=True)
# def pytest_runtest_makereport(item, call):
#     # Execute the test and get the report object
#     outcome = yield
#     report = outcome.get_result()
    
#     # Add a custom attribute to the report
#     if report.when == "call":
#         # Attach the execution time to the report
#         report.execution_time = getattr(item, "execution_time", None)

# def pytest_html_results_table_header(cells):
#     cells.insert(2, extras.html("<th>Execution Time</th>"))

# def pytest_html_results_table_row(report, cells):
#     cells.insert(2, extras.html(f"<td>{getattr(report, 'execution_time', 'N/A')}</td>"))

# @pytest.hookimpl(tryfirst=True)
# def pytest_runtest_protocol(item, nextitem):
#     start = time.time()
#     outcome = yield
#     stop = time.time()
#     item.execution_time = stop - start



