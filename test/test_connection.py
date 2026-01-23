import requests
import json

# --- CONFIGURATION TO TEST ---
# Copy these EXACTLY from your .ini file or Bruno
TIP_TO_TEST = "e5135e2c69fa0933c2611a4c5b653765e2c1cdf6d0764b39db6ef1ecbbeb9af6"
BASE_URL = "https://services.apse2.elasticnoggin.com"
ENDPOINT = f"/rest/object/loadComplianceCheckDriverLoader/{TIP_TO_TEST}"

# https://services.apse2.elasticnoggin.com/rest/object/loadComplianceCheckDriverLoader/12c02349d9d18e78095961cb3baa77eaa864fa25bd43bf8af7b0b113aacbd15e


# Check your config.ini for this value. It usually starts with a number.
NAMESPACE_ID = "6649a25a06337e51a87b77a7d83e58f522795452456649b8e019574837f8674"

# Paste your NEW token here (ensure no spaces at start/end)
TOKEN = "ZXlKMGVYQWlPaUpLVjFRaUxDSmhiR2NpT2lKSVV6STFOaUo5LmV5SnpaWE56YVc5dVZHOXJaVzRpT2lKallqVm1NemRrWkRkak1XVXhPV1ZrTldNeU1EWmhZbVptTnprMVlXUmxaVEprTUdNM09ERmhOVFE0WkRCaFlXTTFNR1V6TXpRMlpqRXpaamd6TjJFMUlpd2ljMlZ6YzJsdmJrbGtJam9pTjJRek5tVTVNak16TUdZME5tSTFZVEF6TURkbU5HRXpZVFl3T0dZek5UQTJaVEZtWXpFNFpEUmpNR1ZtTldRME5UQXdZVGhqTVdRMk5EZzFaak5qTVNJc0ltNWhiV1Z6Y0dGalpTSTZJalkyTkRsaE1qVmhNRFl6TXpkbE5URmhPRGRpTnpkaE4yUTRNMlUxT0dZMU1qSTNPVFUwTlRJME5UWTJORGxpT0dVd01UazFOelE0TXpkbU9EWTNOQ0lzSW1WNGNDSTZNak01T1RNNE5qVTFNeXdpWTNWemRHOXRVR0Y1Ykc5aFpDSTZleUoxYzJWeVZHbHdJam9pWlRGa05XRm1OakJpWkdJM01UQmxaRFkyWVRaaE1HTXpPREF4WTJKa05ERXhabU5pTURJNE9UQmlNR1kwTjJJMk9HUXhORGd3WW1ZM1pHWTFabVE1T0NKOWZRLmlnX1hBX2JZLS1pTE9NeWJ3cjRQQ3l1YUhDVFVrS2pwV3E4aUlPTE1iMDg" 
# (If your ini includes "Bearer " inside the value, include it here. 
#  If the ini only has the hash, put "Bearer " before it below)

def test_request():
    url = BASE_URL + ENDPOINT
    
    # Construct headers exactly like the processor does
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "NogginLCDProcessor/1.0 (Internal Integration)",
        "en-namespace": NAMESPACE_ID,
        "Authorization": TOKEN if TOKEN.startswith("Bearer") else f"Bearer {TOKEN}"
    }

    print(f"Testing URL: {url}")
    print("Sending headers:")
    print(json.dumps(headers, indent=2, default=str))
    print("-" * 40)

    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print("SUCCESS! The credentials and URL are correct.")
            print("Preview:", response.text[:200])
        else:
            print("FAILED.")
            print("Response Body:", response.text)
            
            # Check for specific 500 causes
            if response.status_code == 500:
                print("\n[!] DIAGNOSIS FOR 500 ERROR:")
                print("1. Namespace Mismatch: Does the token belong to the same env as 'en-namespace'?")
                print("2. Permissions: Does the user for this token have 'View' rights on 'Load Compliance Check'?")
                print("3. Invisible Config Chars: Check your .ini file for trailing spaces after the token.")

    except Exception as e:
        print(f"Exception occurred: {e}")

if __name__ == "__main__":
    test_request()

# import psycopg2
# conn = psycopg2.connect(
#     # host="GS-SV-011",
#     # host="192.168.0.236",
#     host="localhost",
#     database="noggin_db",
#     user="noggin_app",
#     password="GoodKingCoat16"
# )
