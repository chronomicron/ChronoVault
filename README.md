ChronoVault
Synopsis
ChronoVault is a Python-based desktop application designed to streamline the organization and archiving of digital photos. It scans storage volumes (e.g., hard drives, USB drives) for images, extracts metadata, and organizes them into a timeline-based archive. Leveraging AI, ChronoVault automatically labels images with information such as people, locations, and dates, storing all metadata in a lightweight SQLite database for fast retrieval. A user-friendly PyQt interface allows users to select volumes, manage archives, and explore their photo collections.

Features
Volume Scanning: Recursively scans storage volumes to locate images (e.g., JPG, JPEG, BMP, RAW).
Metadata Extraction: Extracts EXIF data (e.g., date taken, GPS) for intelligent organization.
AI-Powered Labeling: Uses face recognition and optional cloud APIs to tag images with people and locations.
Database Storage: Stores metadata in SQLite for efficient searching and timeline views.
Photo Archiving: Copies or moves images to an organized archive (e.g., ~/ChronoVault/Archive/YYYY/MM/).
User Interface: PyQt-based GUI for selecting volumes, viewing progress, and browsing images.
Configurable Options: User settings (e.g., archive location, copy/move preference) stored in a JSON file.
Installation
Clone the repository:
bash

Copy
git clone https://github.com/yourusername/ChronoVault.git
cd ChronoVault
Create and activate a virtual environment:
bash

Copy
python3 -m venv .venv
source .venv/bin/activate
Install dependencies:
bash

Copy
pip install -r requirements.txt
Run the application:
bash

Copy
python ChronoVault.py
File Structure
The project is organized into modular components for maintainability and scalability:

text

Copy
ChronoVault/
├── chronovault/
│   ├── __init__.py             # Marks chronovault as a Python package
│   ├── ui.py                  # PyQt GUI logic for user interaction
│   ├── scanner.py            # File scanning and multithreaded crawling
│   ├── database.py           # SQLite database operations for metadata storage
│   ├── ai.py                 # AI processing (face recognition, EXIF extraction)
│   └── config.py             # Constants (e.g., image extensions, archive path)
├── ChronoVault.py            # Main application entry point
├── config.json               # User options (e.g., archive directory, scan locations)
├── requirements.txt          # Python dependencies
├── LICENSE                   # MIT License
├── .gitignore                # Excludes unnecessary files from Git
└── README.md                 # Project documentation

Development
ChronoVault is under active development. Key areas of focus include:

Implementing multithreaded scanning with temporary file output.
Enhancing the database with metadata queries (e.g., by date, person).
Adding AI features for face recognition and location tagging.
Expanding the GUI with timeline views and user controls.
To contribute:

Fork the repository and create a feature branch:
bash

Copy
git checkout -b feature/your-feature
Commit changes and push:
bash

Copy
git commit -m "Add your feature"
git push origin feature/your-feature
Open a pull request on GitHub.
License
This project is licensed under the MIT License. See the  file for details.

Contact
For questions, issues, or feature requests, please open an issue on GitHub or contact the maintainer at [chronomicron@gmail.com].
