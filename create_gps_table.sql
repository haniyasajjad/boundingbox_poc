-- Creating table for GPS data with PostGIS geometry column
CREATE TABLE gps_points (
    id SERIAL PRIMARY KEY,
    frame_number INTEGER NOT NULL,
    frame_time FLOAT NOT NULL,
    group_id INTEGER NOT NULL,
    group_order INTEGER NOT NULL,
    lat FLOAT NOT NULL,
    lng FLOAT NOT NULL,
    geom GEOMETRY(POINT, 4326), -- SRID 4326 for WGS84 lat/lng
    millis BIGINT NOT NULL,
    speed FLOAT NOT NULL,
    video_index INTEGER NOT NULL
);

-- Create a spatial index for efficient queries
CREATE INDEX gps_points_geom_idx ON gps_points USING GIST (geom);