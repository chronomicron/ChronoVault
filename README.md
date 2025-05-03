ChronoVault
ChronoVault is a Python-based application designed to help you consolidate and organize photos from various storage devices. Whether your images are scattered across old computers, USB drives, or CDs, ChronoVault scans directories, archives images to a local database, and (in future updates) uses AI to label and categorize them by dates, people, or places. Built with PyQt5 for a user-friendly GUI and SQLite for metadata storage, it’s perfect for managing your photo collection.
Motivation
Over the years, I’ve captured countless photos stored across disparate devices—old computers, laptops, cameras, phones, hard drives, CDs, and DVDs. ChronoVault was born to solve this: an app that scans folders on any volume, USB, or network drive, copies images to a local database for management, and uses AI to label and organize them by people, places, or dates, making it easy to find cherished memories.
Features

Graphical Interface: Select scan and vault directories using a PyQt5-based GUI.
Database Management: Initialize an SQLite database to store image metadata, with folder structure creation (Vault/Database/ and Vault/Archive/).
Persistent Settings: Save scan and vault paths in config.json for easy reuse.
Status Updates: View progress and error messages in a built-in status window.
In Development:
Directory scanning to find images.
AI-powered labeling for dates, people, and places.
Image archiving to date-based folders (Vault/Archive/YYYY/MM/).



Installation
ChronoVault is developed and tested on Ubuntu. Follow these steps to set it up:

Clone the repository (replace yourusername with your GitHub username):
git clone https://github.com/yourusername/ChronoVault.git
cd ChronoVault


Create and activate a virtual environment:
python3 -m venv .venv
source .venv/bin/activate


Install dependencies:
pip install -r requirements.txt



Usage
Launch the application:
python ChronoVault.py


Scan Directory: Choose a folder or volume to scan for images (e.g., a USB drive or network share).
Vault Directory: Select a directory to store the SQLite database (Vault/Database/chronovault.db) and archived images (Vault/Archive/).
Test Database Integrity: Check if the database and archive folders exist, with an option to create them if missing.
Start Scan: Currently outputs a placeholder message (scanning functionality in development).

Project Status
ChronoVault is under active development. Current features include a GUI for directory selection and database initialization. Upcoming features include image scanning, AI-based labeling, and date-organized archiving. Contributions and feedback are welcome!
License
This project is licensed under the MIT License - see the LICENSE file for details.
Contact
For questions or suggestions, contact the author at chronomicron@gmail.com.
