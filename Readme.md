# Stryder CLI 🏃‍♂️

A command-line tool to manage and match running data from Stryd and Garmin sources, with support for database tracking, timezone correction, and unmatched run review.

## Features

- 🛠️ Initialize or reset the database
- 📂 Batch import Stryd CSVs with automatic Garmin matching
- 📄 Add a single run with interactive prompts
- 🔍 Identify and resolve unmatched Stryd runs
- 🧠 Remembers last-used paths
- 🌍 Timezone support with user prompting
- ✅ All parsed runs are Garmin-matched unless explicitly allowed

## Requirements

- Python 3.9+
- `pandas`
- `tzlocal`

Install dependencies:

```bash
pip install -r requirements.txt
