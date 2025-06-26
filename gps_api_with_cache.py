from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import redis
import hashlib

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development; restrict in production
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],  # Allow POST and OPTIONS
    allow_headers=["*"],
)

# Database connection parameters
db_params = {
    "dbname": "gps_data_db",
    "user": "postgres",
    "host": "localhost",
    "port": "5432"
}

# Redis connection
redis_client = redis.Redis(host='localhost', port=6379, db=0)

class BoundingBox(BaseModel):
    min_lat: float
    min_lng: float
    max_lat: float
    max_lng: float
    zoom_level: int

def get_db_connection():
    return psycopg2.connect(**db_params)

def get_cache_key(bbox: BoundingBox):
    # Create a unique key for the bounding box and zoom level
    key_str = f"{bbox.min_lat}:{bbox.min_lng}:{bbox.max_lat}:{bbox.max_lng}:{bbox.zoom_level}"
    return hashlib.md5(key_str.encode()).hexdigest()

@app.post("/gps-points/")
async def get_gps_points(bbox: BoundingBox):
    # Check cache
    cache_key = get_cache_key(bbox)
    cached_result = redis_client.get(cache_key)
    if cached_result:
        return json.loads(cached_result)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Define zoom-level logic: show potential distresses (speed < 30) only at zoom >= 15
        if bbox.zoom_level >= 15:
            query = """
                SELECT 
                    frame_number, 
                    frame_time, 
                    group_id, 
                    group_order, 
                    lat, 
                    lng, 
                    millis, 
                    speed, 
                    video_index,
                    ST_AsGeoJSON(geom) as geometry,
                    CASE WHEN speed < 30 THEN 'distress' ELSE 'normal' END as point_type
                FROM gps_points
                WHERE ST_Within(
                    geom,
                    ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                )
            """
        else:
            query = """
                SELECT 
                    frame_number, 
                    frame_time, 
                    group_id, 
                    group_order, 
                    lat, 
                    lng, 
                    millis, 
                    speed, 
                    video_index,
                    ST_AsGeoJSON(geom) as geometry,
                    'normal' as point_type
                FROM gps_points
                WHERE ST_Within(
                    geom,
                    ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                ) AND speed >= 30
            """
        
        params = (bbox.min_lng, bbox.min_lat, bbox.max_lng, bbox.max_lat)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        # Format as GeoJSON
        features = [
            {
                "type": "Feature",
                "geometry": json.loads(row["geometry"]),
                "properties": {
                    "frame_number": row["frame_number"],
                    "frame_time": row["frame_time"],
                    "group_id": row["group_id"],
                    "group_order": row["group_order"],
                    "lat": row["lat"],
                    "lng": row["lng"],
                    "millis": row["millis"],
                    "speed": row["speed"],
                    "video_index": row["video_index"],
                    "point_type": row["point_type"]
                }
            }
            for row in rows
        ]
        
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        # Cache the result for 1 hour
        redis_client.setex(cache_key, 3600, json.dumps(geojson))
        
        return geojson
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")