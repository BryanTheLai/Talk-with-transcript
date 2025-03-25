import os
import re
import psycopg
from typing import Optional, Dict, List, Any, Union
from datetime import datetime
import logging
from .models import ApiResponse, Video

class DatabaseClient:
    """Client for interacting with PostgreSQL database to store YouTube video data"""
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize database client with connection string
        
        Args:
            connection_string: PostgreSQL connection string
                Format: postgresql://user:password@host:port/dbname
                If None, will try to get from NEON_YOUTUBE_DATABASE_URL environment variable
        """
        self.connection_string = connection_string or os.environ.get("NEON_YOUTUBE_DATABASE_URL")
        if not self.connection_string:
            raise ValueError("Database connection string must be provided or set as NEON_YOUTUBE_DATABASE_URL environment variable")
        
        # Modify the connection string for Neon if needed
        if "neon.tech" in self.connection_string and "options=endpoint" not in self.connection_string:
            self.connection_string = self._add_neon_endpoint_param(self.connection_string)
            
        self.conn = None
        self.initialized = False
        
    def _add_neon_endpoint_param(self, conn_string: str) -> str:
        """Add the required endpoint parameter for Neon PostgreSQL connections"""
        # Extract the endpoint ID (project name) from the host portion of the connection string
        match = re.search(r'@([^.]+)\.', conn_string)
        if not match:
            logging.warning("Could not extract Neon project name from connection string")
            return conn_string
            
        endpoint_id = match.group(1)
        
        # Check if the connection string already has parameters
        if '?' in conn_string:
            return f"{conn_string}&options=endpoint%3D{endpoint_id}"
        else:
            return f"{conn_string}?options=endpoint%3D{endpoint_id}"
    
    def connect(self):
        """Establish connection to the database"""
        try:
            logging.info(f"Connecting to database with modified connection string")
            self.conn = psycopg.connect(self.connection_string)
            logging.info("Successfully connected to database")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to database: {str(e)}")
            return False
    
    def initialize_schema(self) -> bool:
        """Create database schema if it doesn't exist"""
        if not self.conn and not self.connect():
            return False
            
        try:
            # With Psycopg 3, cursors are created slightly differently
            with self.conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS public.youtube_videos (
                    id bigint primary key generated always as identity,
                    youtube_id text NOT NULL,
                    title text NOT NULL,
                    channel text NOT NULL,
                    published_date timestamp with time zone NOT NULL,
                    viewcount bigint NOT NULL,
                    url text NOT NULL,
                    description text,
                    transcript text,
                    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
                    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_youtube_id UNIQUE (youtube_id)
                )
                """)
            self.conn.commit()
            self.initialized = True
            return True
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Failed to initialize schema: {str(e)}")
            return False
    
    def save_video(self, video: Video) -> ApiResponse[bool]:
        """Save a video to the database"""
        if not self.conn and not self.connect():
            return ApiResponse(success=False, error="Database connection failed")
            
        if not self.initialized and not self.initialize_schema():
            return ApiResponse(success=False, error="Failed to initialize schema")
            
        try:
            # Convert view_count to integer
            try:
                view_count = int(video.view_count.replace(',', ''))
            except ValueError:
                view_count = 0
                
            # Parse published date
            try:
                published_date = datetime.fromisoformat(video.published_date.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                published_date = datetime.now()
            
            # In Psycopg 3, rows is an attribute of cursor
            with self.conn.cursor() as cur:
                cur.execute("""
                INSERT INTO youtube_videos 
                (youtube_id, title, channel, published_date, viewcount, url, description, transcript)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (youtube_id) 
                DO UPDATE SET
                    title = EXCLUDED.title,
                    channel = EXCLUDED.channel,
                    published_date = EXCLUDED.published_date,
                    viewcount = EXCLUDED.viewcount,
                    url = EXCLUDED.url,
                    description = EXCLUDED.description,
                    transcript = EXCLUDED.transcript,
                    updated_at = CURRENT_TIMESTAMP
                """, (
                    video.id,
                    video.title,
                    video.channel,
                    published_date,
                    view_count,
                    video.url,
                    video.description,
                    video.transcript
                ))
            self.conn.commit()
            return ApiResponse(success=True, data=True)
        except Exception as e:
            self.conn.rollback()
            return ApiResponse(success=False, error=f"Failed to save video: {str(e)}")
    
    def get_video_by_id(self, youtube_id: str) -> ApiResponse[Optional[Video]]:
        """Retrieve a video from database by YouTube ID"""
        if not self.conn and not self.connect():
            return ApiResponse(success=False, error="Database connection failed")
        
        try:
            # Use Psycopg 3's Row factory instead of RealDictCursor
            with self.conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("""
                SELECT youtube_id, title, channel, published_date, viewcount, url, description, transcript
                FROM youtube_videos
                WHERE youtube_id = %s
                """, (youtube_id,))
                
                result = cur.fetchone()
                
            if not result:
                return ApiResponse(success=True, data=None)
                
            # Format viewcount back to string with commas
            view_count = f"{result['viewcount']:,}"
            
            # Format published date to string
            published_date = result['published_date'].isoformat()
            
            video = Video(
                id=result['youtube_id'],
                title=result['title'],
                channel=result['channel'],
                published_date=published_date,
                view_count=view_count,
                url=result['url'],
                description=result['description'],
                transcript=result['transcript']
            )
            
            return ApiResponse(success=True, data=video)
        except Exception as e:
            return ApiResponse(success=False, error=f"Failed to retrieve video: {str(e)}")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __del__(self):
        """Ensure connection is closed when object is destroyed"""
        self.close()