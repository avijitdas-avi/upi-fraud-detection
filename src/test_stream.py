from src.streaming.transaction_streamer import TransactionStreamer


streamer = TransactionStreamer(
    file_path="data/raw/synthetic_transactions.csv",
    delay=1
)

for transaction in streamer.stream_transactions():

    print(
        f"Transaction: {transaction['transaction_id']} | "
        f"Amount: ₹{transaction['amount']}"
    )