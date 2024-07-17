[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/Olocufier/HABSlib/HEAD)
# HABSlib

A Python library for interacting with the HABS BrainOS API, to manage EEG recordings, handling complexities like encryption, authentication, and more, so you can focus on building your application.

Please, consider reading (and providing feedback about) our online [documentation](https://olocufier.github.io/HABSlib/HABSlib/service.html).


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
hb.handshake(base_url="http://habs", user_id="your_id_from_habs")

###############
# Get user data by id
user_data = hb.get_user_by_id(user_id)
print(user_data)

# ###############
# Simple sending data
session_id = hb.acquire_send_raw(
    user_id=user_id, 
    date=datetime.today().strftime('%Y-%m-%d'), 
    board="SYNTHETIC",
    stream_duration=20, 
    buffer_duration=5
)
print("this session:", session_id)
```

## Contributing

We welcome contributions! Please see our CONTRIBUTING.md for more details.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

If you have any questions or need support, please open an issue on GitHub or contact dev@habs.ai.
