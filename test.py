for name in unparsed:
    file_path = folder / name
    print(f"\n🔍 File: {name}")
    choice = input("⚙️  Do you want to parse this run? [y/N]: ").strip().lower()

    if choice != 'y':
        print("⏭️  Skipping.")
        continue

    try:
        stryd_df, duration_td, duration_str = process_csv_pipeline(str(file_path), GARMIN_CSV_PATH)

        start_time_str = stryd_df['Local Timestamp'].iloc[0].isoformat(sep=' ', timespec='seconds')
        if run_exists(conn, start_time_str):
            print(f"⚠️  Run at {start_time_str} already exists. Skipping.")
            continue

        workout_name = stryd_df["Workout Name"].iloc[0] if "Workout Name" in stryd_df else "Unknown"
        notes = ""
        avg_hr = None

        insert_full_run(stryd_df, workout_name, notes, avg_hr, conn)
        print(f"✅ Inserted: {name}")

    except Exception as e:
        print(f"❌ Failed to process {name}: {e}")