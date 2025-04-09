from geopy.distance import geodesic
from models import OfficeLocation
import requests
import gspread
from datetime import datetime

# SHEET_ID = "1X7AptFt0wPULYcHj0kjUol962OTxfft9anqfz9RsBrM"
# SHEET_NAME = "Attendance Sheet"
# SHEET_URL = "https://docs.google.com/spreadsheets/d/1X7AptFt0wPULYcHj0kjUol962OTxfft9anqfz9RsBrM/edit?gid=0#gid=0"

AIRTABLE_PAT = "patZNQAsA3OEGx1uT.a226c2f8a792f873ab9e09bb57169abdcca7841c7459bb439d96f4926568ab96"
AIRTABLE_BASE_ID = "appoY0DuMMG57qsJl"
AIRTABLE_TABLE_NAME = "Attendance"

def is_within_office(user_lat, user_lon):
    office = OfficeLocation.query.first()
    if not office:
        return False

    office_location = (office.latitude, office.longitude)
    user_location = (user_lat, user_lon)

    distance = geodesic(office_location, user_location).meters
    return distance <= office.radius

def get_place_name(latitude, longitude):
    print(latitude,longitude,"lmmmmmmmmmmmm")
    url = f"https://nominatim.openstreetmap.org/reverse?lat={latitude}&lon={longitude}&format=json"
    headers = {
        "User-Agent": "ashwinnair311.ann@gmail.com"  # Replace with your details
    }
    response = requests.get(url,headers=headers)
    if response.status_code != 200 or not response.text.strip():
            print("Error: Empty or invalid response from API")
            return "Unknown Location"

    data = response.json()  
    return data.get("display_name") 

def write_attendance_to_sheet(user_name, login_time=None, logout_time=None, place=None):
    try:
        url = "https://script.google.com/macros/s/AKfycbzNni8g_qZ-7pe9hqwxOx7rS3X4r_74PfWzldGhcgPjL7bSiZSzWy1EnnVH7DD8Ur-C/exec"
        
        fields = {
            "Employee Name": user_name,
            "Date": datetime.utcnow().strftime("%Y-%m-%d")
        }

        if login_time:
            fields["Login Time"] = login_time.strftime("%H:%M:%S")
        if logout_time:
            fields["Logout Time"] = logout_time.strftime("%H:%M:%S")
        if place:
            fields["Location"] = place

        data = { "records": [ { "fields": fields } ] }

        response = requests.post(url, json=data)
        response.raise_for_status()

        return {"message": "Attendance recorded in Sheet"}

    except Exception as e:
        return {"error": str(e)}

    except requests.exceptions.RequestException as e:
        return {"error": "Failed to write to Sheet", "details": str(e)}

    except Exception as e:
        return {"error": "An unexpected error occurred", "details": str(e)}
