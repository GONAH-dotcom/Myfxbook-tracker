
import os
import csv
import requests
from datetime import datetime

# Load credentials from GitHub Secrets
MYFXBOOK_EMAIL = os.environ.get("MYFXBOOK_EMAIL")
MYFXBOOK_PASSWORD = os.environ.get("MYFXBOOK_PASSWORD")

def get_session_token():
    login_url = f"https://myfxbook.com{MYFXBOOK_EMAIL}&password={MYFXBOOK_PASSWORD}"
    try:
        response = requests.get(login_url)
        data = response.json()
        if data.get("error") == "false" or not data.get("error"):
            return data.get("session")
        else:
            print(f"Login failed: {data.get('message')}")
            return None
    except Exception as e:
        print(f"Connection error: {e}")
        return None

def fetch_and_save_sentiment():
    session_token = get_session_token()
    if not session_token:
        return

    outlook_url = f"https://myfxbook.com{session_token}"
    try:
        response = requests.get(outlook_url)
        data = response.json()
        
        if data.get("error") == "true":
            print(f"API Error: {data.get('message')}")
            return
            
        symbols_data = data.get("symbols",)
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        csv_file = "myfxbook_sentiment_history.csv"
        file_exists = os.path.isfile(csv_file)

        with open(csv_file, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["Timestamp_UTC", "Symbol", "Long_Percentage", "Short_Percentage", "Long_Volume", "Short_Volume"])

            for item in symbols_data:
                writer.writerow([
                    timestamp,
                    itemget("name"),
                    itemget("longPercentage"),
                    itemget("shortPercentage"),
                    itemget("longVolume"),
                    itemget("shortVolume")
                ])
                
        print(f"Data updated at {timestamp} UTC.")
        requests.get(f"https://myfxbook.com{session_token}")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    fetch_and_save_sentiment()
