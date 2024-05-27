from datetime import datetime
import math


def convert_timestamps(timestamp):
    dt_object = datetime.utcfromtimestamp(timestamp)
    human_readable_timestamp = dt_object.strftime('%Y-%m-%d %H:%M:%S.%f')
    return human_readable_timestamp


def calculate_and_round_time_diff(timestamp1, timestamp2):
    """
    Calculate the difference between two timestamps and round the result to 3 decimal places.

    Args:
        timestamp1 (float): The first timestamp.
        timestamp2 (float): The second timestamp.

    Returns:
        float: The rounded time difference in seconds.
    """
    time_diff = timestamp2 - timestamp1
    return round(time_diff, 3)


def calculate_total_iterations(stream_duration, buffer_size, overlay):
    if buffer_size <= overlay:
        raise ValueError("Buffer size must be greater than overlay.")
    # Calculate the number of iterations
    return 1 + math.ceil((stream_duration - buffer_size) / (buffer_size - overlay))
