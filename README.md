# Stryder CLI 🏃‍♂️

As a hobbyist runner getting into coding, I built this command-line tool to help organize and analyze my running data using CSV files from Stryd and Garmin. It stores the cleaned data in a local SQLite database for easy access and future analysis.

---

## 📄 Files You Need

Before using Stryder, make sure you have the following:

### ✅ Stryd CSV Files

These are your **detailed per-run files**, exported from Stryd PowerCenter or the mobile app. Each file contains second-by-second metrics such as pace, power, cadence, etc.

🗂 Export them in **bulk** and place them all in a folder. Each file typically has a long numeric filename, like:

5059274362093568.csv,
5073428460371968.csv

💡 You’ll be prompted to select this folder during batch import.

---

### ✅ Garmin CSV Export

This is a **single CSV file** containing summary data for your Garmin runs — one row per workout — with columns like start time, duration, and distance.

To download it:
1. Visit [Garmin Connect](https://connect.garmin.com/)
2. Go to your activities list
3. Export all (or running-only) activities as a `.csv` file

It will be named something like:

 activities.csv

💡 This is the file you'll be prompted to provide as the "Garmin file."

---

⚠️ The app uses the **start time** from each Stryd file to match it with the correct Garmin run. The match is made using timezone-aware comparison with a ±60 second tolerance.

---

## ⚙️ Features

- 🛠️ Initialize or reset the SQLite database
- 📂 Batch import Stryd CSVs with automatic Garmin run matching
- ➕ Add a single run interactively
- 🔍 Detect and handle unmatched Stryd runs
- 🧠 Remembers last-used folders between sessions
- 🌍 Timezone handling with user prompting and suggestions
- ✅ Ensures only Garmin-matched runs are stored — unless overridden

---

## 🖥️ Example CLI Output

🌀 Stryder CLI v1.1.1

✅ Parsed files in DB: 287

❗ Unparsed files: 15

🌍 Timezone for 5151xxxx.csv: Europe/Athens

✅ Match found: "Evening Run" at 2023-06-22 19:25:00+03:00

✅ Run saved: Workout ID 103, Run ID 195


---

## ▶️ Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize the database
python Stryder_CLI.py init-db

# Batch import Stryd folder + Garmin file
python Stryder_CLI.py add-batch

# Review unmatched runs
python Stryder_CLI.py find-unparsed

# CLI Help
python Stryder_CLI.py --help

---

🛠 Tech Stack
Python 3.9+

pandas

SQLite

tzlocal

argparse, pathlib, logging


---

## 🧭 Roadmap

These are planned or possible features for future versions of Stryder:

- [x] Basic CLI with Stryd + Garmin import
- [x] Timezone prompt and matching tolerance
- [x] Skipping unmatched runs for later review
- [x] Store last-used file paths
- [ ] Add CLI commands for viewing runs and summaries
- [ ] Weekly/monthly mileage summaries
- [ ] Graphs: pace over time, distance over time, elevation
- [ ] Support .fit/.tcx/.gpx file parsing
- [ ] Allow manual tagging of runs (e.g., "race", "long run")
- [ ] Optional GUI (e.g., Streamlit or PyQt)
- [ ] Export to Excel or CSV with filters

👤 Author
Giorgos Chrysopoulos
Beginner Python Developer & Hobbyist Runner
🔗 [LinkedIn](https://www.linkedin.com/in/giorgos-chrisopoulos-277989374/)
💡 Want to contribute? Open an issue or fork the repo!

---

---

## 📃 License
MIT License — see the [LICENSE](LICENSE) file.


