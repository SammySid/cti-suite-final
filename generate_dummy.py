import os
import random
import pandas as pd
from datetime import datetime, timedelta

def generate_jumbled_excel_files(output_dir, num_files=12):
    os.makedirs(output_dir, exist_ok=True)
    
    sensor_types = ['cwt', 'hwt', 'wbt', 'dbt']
    
    # Base configuration
    start_date = datetime(2023, 11, 12, 16, 0, 0)
    start_date_2 = datetime(2023, 11, 13, 16, 0, 0)
    
    # Generate an EXACT master grid of 30 exact synced seconds for Day 1
    day_1_sync_times = sorted([start_date + timedelta(seconds=random.randint(0, 7200)) for _ in range(30)])
    
    # Generate an EXACT master grid of 30 exact synced seconds for Day 2
    day_2_sync_times = sorted([start_date_2 + timedelta(seconds=random.randint(0, 7200)) for _ in range(30)])
    
    for i in range(num_files):
        # Pick a random sensor type and ID
        s_type = random.choice(sensor_types)
        s_id = f"{random.randint(1, 20):02d}"
        filename = f"{s_type}_logger_{s_id}_synced.xlsx"
        filepath = os.path.join(output_dir, filename)
        
        rows = []
        
        # Add 30 perfectly synced samples for Day 1
        for t in day_1_sync_times:
            base_temp = 32.0 if s_type == 'cwt' else 40.0 if s_type == 'hwt' else 28.0 if s_type == 'wbt' else 35.0
            temp_val = round(base_temp + random.uniform(-2.5, 2.5), 1)
            
            rows.append({
                'Date': t.strftime('%d-%m-%Y'),
                'Time': t.strftime('%H:%M:%S'),
                'Temperature (°C)': temp_val
            })
            
        # Add 30 perfectly synced samples for Day 2
        for t in day_2_sync_times:
            base_temp = 31.0 if s_type == 'cwt' else 39.0 if s_type == 'hwt' else 27.0 if s_type == 'wbt' else 34.0
            temp_val = round(base_temp + random.uniform(-2.5, 2.5), 1)
            
            rows.append({
                'Date': t.strftime('%d-%m-%Y'),
                'Time': t.strftime('%H:%M:%S'),
                'Temperature (°C)': temp_val
            })

        # CRITICAL TEST: Jumble the rows randomly so they are totally out of chronological order!
        random.shuffle(rows)
        
        df = pd.DataFrame(rows)
        df.to_excel(filepath, index=False)
        print(f"Created jumbled synced file: {filename} with {len(df)} rows")

if __name__ == '__main__':
    target_folder = r"f:\2026 latest\cti Toolkit\cti-suite-final\temp_synced_data"
    print(f"Generating synced data in {target_folder}...")
    generate_jumbled_excel_files(target_folder, 15)
    print("Done! Files are output to testing folder.")
