from fastapi import FastAPI, HTTPException
from psycopg2 import OperationalError
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Database connection parameters
db_params = {
    "dbname": "gps_data_db",
    "user": "postgres",
    "host": "localhost",
    "port": "5432"
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BoundingBox(BaseModel):
    min_lat: float
    min_lng: float
    max_lat: float
    max_lng: float
    zoom_level: int

def get_db_connection():
    return psycopg2.connect(**db_params)

@app.post("/gps-points/")
async def get_gps_points(bbox: BoundingBox):
    
    if bbox.min_lat >= bbox.max_lat or bbox.min_lng >= bbox.max_lng:
        raise HTTPException(status_code=400, detail="Invalid bounding box coordinates")
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
    
        #zoom-level logic: show points:"Normal" (speed < 46) only at zoom >= 15
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
                    CASE WHEN speed < 46 THEN 'Normal' ELSE 'Speeding' END as point_type
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
                    'Normal' as point_type
                FROM gps_points
                WHERE ST_Within(
                    geom,
                    ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                ) AND speed >= 46
            """
        
        
        #min_lng, min_lat, max_lng, max_lat
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

    except OperationalError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    cur.close()
    conn.close()
    
    return geojson

@app.get("/")
def read_root():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)