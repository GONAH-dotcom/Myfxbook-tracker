
import os
import requests
import csv
from datetime import datetime

email = os.environ.get("MYFXBOOK_EMAIL")
password = os.environ.get("MYFXBOOK_PASSWORD")

login_url = f"https://www.myfxbook.com/api/login.json?email={email}&password={password}"

try:
    print("Attempting to log into Myfxbook...")
    response = requests.get(login_url)
    login_data = response.json()

    if "session" in login_data and login_data.get("error") in [False, "false", "False"]:
        session_token = login_data["session"]
        print("Login successful! Fetching sentiment data...")

        data_url = f"https://www.myfxbook.com/api/get-community-outlook.json?session={session_token}"
        sentiment_data = requests.get(data_url).json()

        symbols_list = sentiment_data.get("symbols", [])

        if symbols_list:
            today = datetime.now().strftime("%Y-%m-%d")
            hour = datetime.now().strftime("%H")
            filename = f"sentiment_{today}_{hour}00.csv"

            headers = [
                "date", "name", "shortPercentage", "longPercentage",
                "shortVolume", "longVolume", "longPositions",
                "shortPositions", "totalPositions"
            ]

            with open(filename, "w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=headers, extrasaction='ignore')
                writer.writeheader()

                for item in symbols_list:
                    row_data = {"date": today}
                    row_data.update(item)
                    writer.writerow(row_data)

            print(f"Success! Saved data to {filename}")
        else:
            print("Error: Myfxbook sent back an empty list of symbols.")
    else:
        print(f"Login Failed. Myfxbook API said: {login_data.get('message', 'Unknown Error')}")
        print("Please check your GitHub Secrets — email and password may have typos.")

except Exception as e:
    print(f"An unexpected system error occurred: {e}")
