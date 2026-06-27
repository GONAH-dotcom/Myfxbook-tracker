
import os
import requests
import csv
from datetime import datetime

# 1. Get credentials securely from your GitHub Secrets
email = os.environ.get("MYFXBOOK_EMAIL")
password = os.environ.get("MYFXBOOK_PASSWORD")

# 2. Login URL (Using official canonical domain)
login_url = f"https://myfxbook.com{email}&password={password}"

try:
    print("Attempting to log into Myfxbook...")
    response = requests.get(login_url)
    login_data = response.json()
    
    # Check if login gave us a valid session
    if "session" in login_data and login_data.get("error") in [False, "false"]:
        session_token = login_data["session"]
        print("Login successful! Fetching sentiment data...")
        
        # 3. Pull the community sentiment data
        data_url = f"https://myfxbook.com{session_token}"
        sentiment_data = requests.get(data_url).json()
        
        # Extract the list of symbols
        symbols_list = sentiment_data.get("symbols", [])
        
        if symbols_list:
            today = datetime.now().strftime("%Y-%m-%d")
            filename = f"sentiment_{today}.csv"
            
            # 4. Process data into standard CSV rows
            # Get data columns dynamically from the first symbol entry
            headers = ["date", "name"] + [k for k in symbols_list[0].keys() if k != "name"]
            
            with open(filename, "w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=headers)
                writer.writeheader()
                
                for item in symbols_list:
                    # Inject current date into each currency pair row
                    row_data = {"date": today}
                    row_data.update(item)
                    writer.writerow(row_data)
                    
            print(f"Success! Saved data to {filename}")
        else:
            print("Error: Myfxbook sent back an empty list of symbols.")
            
    else:
        print(f"Login Failed. Myfxbook API said: {login_data.get('message', 'Unknown Error')}")
        print("Please check that your GitHub Secret email and password have no typos.")

except Exception as e:
    print(f"An unexpected system error occurred: {e}")
