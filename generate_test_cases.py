#!/usr/bin/env python3

# generate_test_cases.py
#
# Creates a test folder structure for ChronoVault with images, random EXIF data,
# edge cases (unreasonable dates, symbolic links), and varied metadata.
# Folder structure: ChronoVaultTest/Country/Region/City with 5 JPEGs per city.
#
# Author: chronomicron@gmail.com
# Created: 2025-05-11
# Updated: 2025-05-11
#
# Usage:
# 1. Activate ChronoVault virtual environment:
#    source ~/workspace/ChronoVault/.venv/bin/activate
# 2. Install dependencies:
#    pip install Pillow piexif
# 3. Save this script in ~/Documents/ChronoVaultTest
# 4. Make executable:
#    chmod +x generate_test_cases.py
# 5. Run:
#    ./generate_test_cases.py
#
# Expected output:
# Created base directory: ChronoVaultTest
# Created country directory: ChronoVaultTest/Laos
# Created region directory: ChronoVaultTest/Laos/Luang_Prabang
# Created city directory: ChronoVaultTest/Laos/Luang_Prabang/Luang_Prabang_City
# Created image: ChronoVaultTest/Laos/Luang_Prabang/Luang_Prabang_City/image1.jpg with DateTimeOriginal=2023:05:15 14:30:00, Model=Nikon D850, GPS=Lat: 37.75, Lon: -122.42, Alt: 100
# Created symbolic link: ChronoVaultTest/Laos/Luang_Prabang/Luang_Prabang_City/parent_link -> ../
# ...
# Test case generation completed. Total images created: 450
#

import os
import random
import datetime
import time
from pathlib import Path

# Check for dependencies
try:
    from PIL import Image
    import piexif
    from piexif import ExifIFD, GPSIFD, ImageIFD
except ImportError as e:
    print(f"Error: Missing required module: {e}")
    print("Please activate the virtual environment and install dependencies:")
    print("  source ~/workspace/ChronoVault/.venv/bin/activate")
    print("  pip install Pillow piexif")
    exit(1)

# Base directory
BASE_DIR = "ChronoVaultTest"

# Define countries
COUNTRIES = ["Laos", "Cambodia", "Vietnam", "Thailand", "Japan", "Malaysia"]

# Define regions per country (5 per country)
REGIONS = {
    "Laos": ["Luang_Prabang", "Vientiane", "Savannakhet", "Champasak", "Pakse"],
    "Cambodia": ["Phnom_Penh", "Siem_Reap", "Battambang", "Kampot", "Sihanoukville"],
    "Vietnam": ["Hanoi", "Ho_Chi_Minh", "Hue", "Da_Nang", "Hoi_An"],
    "Thailand": ["Bangkok", "Chiang_Mai", "Phuket", "Krabi", "Ayutthaya"],
    "Japan": ["Kansai", "Gunma", "Miyazaki", "Hokkaido", "Tohoku"],
    "Malaysia": ["Kuala_Lumpur", "Penang", "Malacca", "Sabah", "Sarawak"],
}

# Define cities per region (3 per region)
CITIES = {
    # Laos
    "Luang_Prabang": ["Luang_Prabang_City", "Phonsavan", "Muang_Ngoi"],
    "Vientiane": ["Vientiane_City", "Vang_Vieng", "Thakhek"],
    "Savannakhet": ["Savannakhet_City", "Don_Khon", "Don_Det"],
    "Champasak": ["Pakse", "Champasak_Town", "Si_Phan_Don"],
    "Pakse": ["Pakse_City", "Bolaven_Plateau", "Wat_Phou"],
    # Cambodia
    "Phnom_Penh": ["Phnom_Penh_City", "Toul_Sleng", "Koh_Rong"],
    "Siem_Reap": ["Siem_Reap_City", "Angkor_Wat", "Banteay_Srei"],
    "Battambang": ["Battambang_City", "Bamboo_Train", "Phnom_Sampov"],
    "Kampot": ["Kampot_City", "Bokor_Hill", "Kep"],
    "Sihanoukville": ["Sihanoukville_City", "Koh_Rong_Samloem", "Otres_Beach"],
    # Vietnam
    "Hanoi": ["Hanoi_City", "Ha_Long_Bay", "Sapa"],
    "Ho_Chi_Minh": ["Ho_Chi_Minh_City", "Cu_Chi_Tunnels", "Mekong_Delta"],
    "Hue": ["Hue_City", "Imperial_City", "Phong_Nha"],
    "Da_Nang": ["Da_Nang_City", "Hoi_An", "Marble_Mountains"],
    "Hoi_An": ["Hoi_An_City", "My_Son", "Cham_Islands"],
    # Thailand
    "Bangkok": ["Bangkok_City", "Grand_Palace", "Chatuchak"],
    "Chiang_Mai": ["Chiang_Mai_City", "Doi_Suthep", "Pai"],
    "Phuket": ["Phuket_City", "Patong_Beach", "Phi_Phi"],
    "Krabi": ["Krabi_City", "Railay_Beach", "Ao_Nang"],
    "Ayutthaya": ["Ayutthaya_City", "Wat_Mahathat", "Bang_Pa_In"],
    # Japan
    "Kansai": ["Osaka", "Kyoto", "Nara"],
    "Gunma": ["Takasaki", "Kiryu", "Maebashi"],
    "Miyazaki": ["Miyazaki_City", "Aoshima", "Takachiho"],
    "Hokkaido": ["Sapporo", "Otaru", "Hakodate"],
    "Tohoku": ["Sendai", "Aomori", "Fukushima"],
    # Malaysia
    "Kuala_Lumpur": ["Kuala_Lumpur_City", "Petronas_Towers", "Batu_Caves"],
    "Penang": ["George_Town", "Penang_Hill", "Kek_Lok_Si"],
    "Malacca": ["Malacca_City", "Jonker_Street", "A_Famosa"],
    "Sabah": ["Kota_Kinabalu", "Sandakan", "Sipadan"],
    "Sarawak": ["Kuching", "Miri", "Bako"],
}

# Define camera models
CAMERA_MODELS = [
    "Canon EOS 5D",
    "Nikon D850",
    "Sony Alpha 7R IV",
    "Fujifilm X-T4",
    "Panasonic Lumix GH5",
    "Olympus OM-D E-M1",
]

def generate_random_date():
    """Generate a random date (1% chance of 1900, else 2000–2025)."""
    if random.random() < 0.01:
        return "1900:01:01 00:00:00"
    year = random.randint(2000, 2025)
    month = random.randint(1, 12)
    day = random.randint(1, 28)  # Avoid edge cases
    hour = random.randint(0, 23)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return f"{year:04d}:{month:02d}:{day:02d} {hour:02d}:{minute:02d}:{second:02d}"

def generate_touch_timestamp(exif_date):
    """Generate a random timestamp within ±3 days of EXIF date."""
    if exif_date == "1900:01:01 00:00:00":
        # For 1900, use a random date in 2000–2025
        year = random.randint(2000, 2025)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        hour = random.randint(0, 23)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
    else:
        # Parse EXIF date
        try:
            dt = datetime.datetime.strptime(exif_date, "%Y:%m:%d %H:%M:%S")
            # Add random offset (±3 days)
            offset = random.randint(-259200, 259200)  # ±3 days in seconds
            dt = dt + datetime.timedelta(seconds=offset)
            year, month, day = dt.year, dt.month, dt.day
            hour, minute, second = dt.hour, dt.minute, dt.second
        except ValueError:
            # Fallback if date parsing fails
            year = random.randint(2000, 2025)
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
    return datetime.datetime(year, month, day, hour, minute, second)

def generate_random_gps():
    """Generate random GPS coordinates and altitude."""
    lat = random.uniform(-90, 90)  # -90 to +90
    lon = random.uniform(-180, 180)  # -180 to +180
    alt = random.randint(0, 1000)  # 0 to 1000 meters
    return lat, lon, alt

def create_image(image_path, date_time, camera_model, lat, lon, alt):
    """Create a JPEG image with EXIF data."""
    try:
        # Create a 100x100 white image
        img = Image.new("RGB", (100, 100), "white")
        img.save(image_path, "JPEG", quality=95)
        
        # Prepare EXIF data
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}}
        
        # Set DateTimeOriginal
        exif_dict["Exif"][ExifIFD.DateTimeOriginal] = date_time.encode("ascii")
        
        # Set camera model
        exif_dict["0th"][ImageIFD.Model] = camera_model.encode("ascii")
        
        # Set GPS coordinates
        lat_abs = abs(lat)
        lon_abs = abs(lon)
        lat_ref = "N" if lat >= 0 else "S"
        lon_ref = "E" if lon >= 0 else "W"
        
        lat_deg = int(lat_abs)
        lat_min = int((lat_abs - lat_deg) * 60)
        lat_sec = int((lat_abs - lat_deg - lat_min / 60) * 3600 * 100)
        lon_deg = int(lon_abs)
        lon_min = int((lon_abs - lon_deg) * 60)
        lon_sec = int((lon_abs - lon_deg - lon_min / 60) * 3600 * 100)
        
        exif_dict["GPS"][GPSIFD.GPSLatitudeRef] = lat_ref.encode("ascii")
        exif_dict["GPS"][GPSIFD.GPSLatitude] = ((lat_deg, 1), (lat_min, 1), (lat_sec, 100))
        exif_dict["GPS"][GPSIFD.GPSLongitudeRef] = lon_ref.encode("ascii")
        exif_dict["GPS"][GPSIFD.GPSLongitude] = ((lon_deg, 1), (lon_min, 1), (lon_sec, 100))
        exif_dict["GPS"][GPSIFD.GPSAltitude] = (alt, 1)
        exif_dict["GPS"][GPSIFD.GPSAltitudeRef] = b"\x00"  # Above sea level
        
        # Save EXIF data
        exif_bytes = piexif.dump(exif_dict)
        img = Image.open(image_path)
        img.save(image_path, "JPEG", quality=95, exif=exif_bytes)
        
        return True
    except Exception as e:
        print(f"Error: Failed to create image or set EXIF data for {image_path}: {e}")
        if os.path.exists(image_path):
            os.remove(image_path)
        return False

def main():
    """Create test case folder structure and images."""
    # Create base directory
    os.makedirs(BASE_DIR, exist_ok=True)
    print(f"Created base directory: {BASE_DIR}")

    for country in COUNTRIES:
        country_dir = os.path.join(BASE_DIR, country)
        os.makedirs(country_dir, exist_ok=True)
        print(f"Created country directory: {country_dir}")

        for region in REGIONS[country]:
            region_dir = os.path.join(country_dir, region)
            os.makedirs(region_dir, exist_ok=True)
            print(f"Created region directory: {region_dir}")

            for city in CITIES[region]:
                city_dir = os.path.join(region_dir, city)
                os.makedirs(city_dir, exist_ok=True)
                print(f"Created city directory: {city_dir}")

                # 5% chance to create a symbolic link to parent
                if random.random() < 0.05:
                    try:
                        link_path = os.path.join(city_dir, "parent_link")
                        os.symlink("..", link_path)
                        print(f"Created symbolic link: {link_path} -> ../")
                    except OSError as e:
                        print(f"Warning: Failed to create symbolic link: {link_path}: {e}")

                # Create 5 JPEG images
                for i in range(1, 6):
                    image_path = os.path.join(city_dir, f"image{i}.jpg")
                    date_time = generate_random_date()
                    camera_model = random.choice(CAMERA_MODELS)
                    lat, lon, alt = generate_random_gps()
                    
                    if create_image(image_path, date_time, camera_model, lat, lon, alt):
                        # Set random modification time
                        mod_time = generate_touch_timestamp(date_time)
                        try:
                            os.utime(image_path, (time.mktime(mod_time.timetuple()), time.mktime(mod_time.timetuple())))
                            print(f"Created image: {image_path} with DateTimeOriginal={date_time}, Model={camera_model}, GPS=Lat: {lat:.2f}, Lon: {lon:.2f}, Alt: {alt}")
                        except OSError as e:
                            print(f"Warning: Failed to set modification time for {image_path}: {e}")

    # Count images and symlinks
    image_count = sum(1 for _ in Path(BASE_DIR).rglob("*.jpg"))
    link_count = sum(1 for _ in Path(BASE_DIR).rglob("parent_link"))
    print(f"Test case generation completed. Total images created: {image_count}")
    print(f"Total symbolic links created: {link_count}")

if __name__ == "__main__":
    main()