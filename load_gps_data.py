import json
import psycopg2
from psycopg2.extras import execute_batch

# Database connection parameters
db_params = {
    "dbname": "gps_data_db",
    "user": "postgres",
    "host": "localhost",
    "port": "5432"
}

# Load JSON data
with open("Sample_GPS_Data.json", "r") as f:
    gps_data = json.load(f)

# Connect to the database
conn = psycopg2.connect(**db_params)
cur = conn.cursor()

# Prepare SQL insert statement
insert_query = """
    INSERT INTO gps_points (
        frame_number, frame_time, group_id, group_order, lat, lng, geom, millis, speed, video_index
    ) VALUES (
        %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s
    )
"""

# Prepare data for batch insert
data_to_insert = [
    (
        point["frameNumber"],
        point["frameTime"],
        point["groupId"],
        point["groupOrder"],
        point["lat"],
        point["lng"],
        point["lng"],  # For ST_MakePoint(lng, lat)
        point["lat"],
        point["millis"],
        point["speed"],
        point["videoIndex"]
    )
    for point in gps_data
]

# Execute batch insert
execute_batch(cur, insert_query, data_to_insert, page_size=1000)

# Commit and close
conn.commit()
cur.close()
conn.close()

print("Data loaded successfully!")