import pandas as pd
import time
from pathlib import Path


class TransactionStreamer:
    """
    Streams transactions one at a time to simulate
    real-time UPI transaction events.
    """

    def __init__(self, file_path, delay=1):
        self.file_path = Path(file_path)
        self.delay = delay

    def stream_transactions(self):
        """
        Generator that yields one transaction at a time.
        """

        df = pd.read_csv(self.file_path)

        print(f"\nLoaded {len(df)} transactions")
        print("Starting real-time transaction stream...\n")

        for _, transaction in df.iterrows():

            yield transaction.to_dict()

            time.sleep(self.delay)