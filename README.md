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

## 🧰 Requirements

- Python 3.9+
- `pandas`
- `tzlocal`

Install dependencies with:

```bash
pip install -r requirements.txt
```

## 🏁 Getting Started
Initialize the database:
-> python Stryder_CLI.py init-db

Batch import your Stryd runs:
-> python Stryder_CLI.py add-batch

Review unmatched runs later:
-> python Stryder_CLI.py find-unparsed

Other commands:
-> python Stryder_CLI.py --help

---

## 📃 License
MIT License — see the [LICENSE](LICENSE) file.

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

💡 Want to contribute? Open an issue or fork the repo!
