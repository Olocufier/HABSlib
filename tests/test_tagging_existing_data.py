import HABSlib as hb

from datetime import datetime
import numpy as np
from scipy import signal

# Usage:
# % source os/bin/activate
# % python frontend/client.py


if __name__ == "__main__":

    hb.handshake(base_url="http://0.0.0.0", user_id='666c0158fcbfd9a830399121')

    print("\n---- create tagged interval")
    interval_id = hb.create_tagged_interval(
        user_id='666c0158fcbfd9a830399121',
        session_id="667ada8070f5cad4b0525747",
        start_time="2024-07-02T09:00:52Z",
        end_time="2024-07-02T09:00:54Z",
        tags=[{"tag": "seizure", "properties": {"severity": "high"}}]
    )
    if interval_id:
        print(f"Tagged interval created with ID: {interval_id}")
    else:
        print("Tagged interval creation failed.")


    print("\n---- get tagged interval")
    data = hb.get_tagged_interval_data(
        user_id="666c0158fcbfd9a830399121",
        session_id="667ada8070f5cad4b0525747",
        tag="seizure"
    )
    if data:
        data=np.array(data)
        print(data.shape)
        # print(f"Data retrieved for tag 'seizure': {data}")
    else:
        print("Failed to retrieve data for the specified tag.")




