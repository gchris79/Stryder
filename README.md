# Stryder 🏃‍♂️  
### Local Running Data Analysis — CLI & Web Viewer

Stryder is a local-first running data analysis project built around **Stryd and Garmin CSV exports**.

It is designed with a clear separation of concerns:

- **Stryder Core** handles parsing, matching, normalization, and metrics.
- **Stryder CLI** is responsible for importing data and generating reports.
- **Stryder Web** (Django) provides a read-only web viewer on top of the same database.

The goal of Stryder is not to replace commercial platforms, but to give runners **full ownership and transparency** over their training data while serving as a learning project in Python and software architecture.

---

## 🧱 Architecture Overview

Stryder is structured as a multi-layer application:

### 🧠 Stryder Core
- Shared business logic used by all interfaces
- CSV parsing and normalization
- Timezone-aware Garmin ↔ Stryd matching
- Canonical metrics and summaries
- SQLite database schema

### ⌨️ Stryder CLI
- Primary entry point for data import
- Batch and single-run processing
- Weekly and custom summaries
- CLI tables and exported plots

### 🌐 Stryder Web (Django)
- Local web viewer running on Django
- Single run detailed reports with graphs
- Custom date range reports
- Interactive axis selection
- Read-only by design (no imports via web)

The CLI and Web interface operate on the **same SQLite database**, ensuring consistency across views.

---

## 📽️ Demo (Django views)

### 1. Custom range run view
View your stored runs filtering them by custom dates or/and keywords.

![Custom range run view](assets/dashboard-view.jpg)

---

### 2. Single run summary view
Visualize your training load with plots using selectable axes.

![Single Run Summary View](assets/single-run-sum.jpg)


---

---
## 📽️ Demo (CLI)

### 1. Weekly & Rolling Reports
Generate weekly reports with distance, avg HR, power, and duration.

<img src="assets/reports_demo.gif" width="700">

---

### 2. Visual Reports
Visualize your training load with automatic plots.

![Weekly Plot](assets/weekly_plot.png)

---

### 3. Detailed Views
Inspect any run in detail with normalized workout names, timestamps, and metrics.

<img src="assets/run_view.png" width="700">

---

## ✨ Features

### Core
- Timezone-aware Stryd ↔ Garmin matching (±60s tolerance)
- Normalized workout naming
- Canonical metrics and summaries
- Local SQLite storage

### CLI
- Interactive menu-based interface
- Batch import of Stryd CSV files
- Garmin activity matching
- Weekly and custom summaries
- Single-run detailed reports
- Exportable visual charts

### Web
- Single run detailed reports
- Custom date range analysis
- Interactive X/Y axis selection
- Clean, page-based layout

---

## 📄 Files You Need

Before using Stryder, make sure you have the following:

### ✅ Stryd CSV Files

These are your **detailed per-run files**, exported from Stryd PowerCenter or the mobile app. Each file contains second-by-second metrics such as pace, power, cadence, etc.

🗂 Export them in **bulk** and place them all in a folder. Each file typically has a long numeric filename, like:

5059274362093568.csv,
5073428460371968.csv

💡 You’ll be prompted to select this folder during batch import.


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

## ▶️ Getting Started

### 1️⃣ Install dependencies
```bash
pip install -r requirements.txt
```
### 2️⃣ Run the CLI (data import & reports)
```bash
python -m stryder_cli.cli_main
```
The CLI is responsible for:
- Importing Stryd and Garmin CSV files
- Building the local SQLite database
- Generating CLI-based reports

### 3️⃣ Run the Web Viewer
```bash
python manage.py runserver
```
The web interface:
- Reads from the same SQLite database
- Provides interactive visual reports
- Does not modify or import data

---

## 🛠 Tech Stack

### Core
- Python 3.11
- SQLite
- Pandas

### CLI
- Matplotlib
- Tabulate

### Web
- Django
- HTML / CSS (Django templates)
- Matplotlib (server-side rendering)

The same SQLite database and core logic are shared between the CLI and Web interfaces.

---

## 🧭 Roadmap

These are planned or possible features for future versions of Stryder:

- [x] Basic CLI with Stryd + Garmin import
- [x] Timezone prompt and matching tolerance
- [x] Skipping unmatched runs for later review
- [x] Store last-used file paths
- [x] Add CLI commands for viewing runs and summaries
- [x] Weekly/monthly mileage summaries
- [x] Graphs: power, distance, duration and HR over time 
- [x] Web Viewer (Django)

- [ ] Text-based UI (Textual) as an optional interface on top of Stryder Core
- [ ] Advanced run comparisons
- [ ] Weekly / monthly / yearly presets in the web interface
- [ ] Segment-based analysis within runs
- [ ] Export filtered data to CSV
- [ ] Support FIT / TCX / GPX parsing

## 👤 Author
Giorgos Chrysopoulos

Junior Python Developer & Hobbyist Runner

🔗 [LinkedIn](https://www.linkedin.com/in/giorgos-chrisopoulos-277989374/)

💡 Want to contribute? Open an issue or fork the repo!

---

## 📃 License
MIT License — see the [LICENSE](LICENSE) file.


