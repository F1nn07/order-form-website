import pandas as pd

def analyze_weekly_orders(file_path='orders.csv'):
    try:
        # 1. Read the CSV data into a pandas DataFrame
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found. Please place some orders first.")
        return

    # 2. Convert the 'timestamp' column to a proper datetime object
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # 3. Ensure 'quantity' is a number
    df['quantity'] = pd.to_numeric(df['quantity'])

    # 4. Group by week and sum the quantities
    # 'W' stands for weekly frequency (ending on Sunday)
    # We group by both item name and the week for a detailed report
    weekly_summary = df.groupby(['item_name', pd.Grouper(key='timestamp', freq='W')])['quantity'].sum().reset_index()

    # Or for a simpler total of all items per week:
    total_weekly_summary = df.resample('W', on='timestamp')['quantity'].sum()

    print("--- Weekly Order Summary (Total Items) ---")
    if total_weekly_summary.empty:
        print("No orders to analyze yet.")
    else:
        print(total_weekly_summary)

if __name__ == '__main__':
    analyze_weekly_orders()