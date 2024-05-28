# HABSlib

Habslib is a Python library for interacting with a remote API, handling complexities like encryption, authentication, and more, so you can focus on building your application.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Installation

You can install habslib using pip:

```
pip install HABSlib
```

## Usage

Here’s a quick example to get you started:

```
import HABSlib as hb

###############
# Security handshake
hb.handshake()

###############
# Set user/subject (if the user already exists it should not creat one)
user_id = hb.set_user("Domenico", "Guarino", "domenico@habs.ai", 50, 89, "M")

###############
# Get user data by id
user_data = hb.get_user_by_id(user_id)
print(user_data)

# ###############
# Simple sending data
session_id = hb.acquire_send_raw(
    user_id=user_id, 
    date=datetime.today().strftime('%Y-%m-%d'), 
    stream_duration=20, 
    buffer_duration=5, 
    overlay=0)
print("this session:", session_id)
```

## Contributing

We welcome contributions! Please see our CONTRIBUTING.md for more details.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

If you have any questions or need support, please open an issue on GitHub or contact info@habs.ai.
