from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import pandas as pd
import pymysql
from app.parsers.room_parser import parse_room_to_df
from app.parsers.parts_parser import parse_room_to_parts
from app.database import get_connection

app = FastAPI()

# Enable CORS for Angular frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "CreekFlow backend is running"}

@app.get("/jobs")
def list_jobs():
    jobs_path = os.environ.get("MOZAIK_JOBS_FOLDER")
    if not jobs_path:
        raise HTTPException(status_code=500, detail="MOZAIK_JOBS_FOLDER not set")
    
    job_folders = [f for f in os.listdir(jobs_path)
                   if os.path.isdir(os.path.join(jobs_path, f))]
    print("Found job folders:", job_folders)
    return {"jobs": job_folders}

@app.post("/import-job/{job_name}")
def import_job(job_name: str):
    print(f"Received import request for job: {job_name}")

    jobs_path = os.environ.get("MOZAIK_JOBS_FOLDER")
    if not jobs_path:
        raise HTTPException(status_code=500, detail="MOZAIK_JOBS_FOLDER not set")
    
    job_path = os.path.join(jobs_path, job_name)
    if not os.path.isdir(job_path):
        raise HTTPException(status_code=404, detail="Job folder not found")
    
    # Process RoomX.des files (skip files starting with room0)
    des_files = [f for f in os.listdir(job_path)
                 if f.endswith(".des") and not f.lower().startswith("room0")]
    if not des_files:
        raise HTTPException(status_code=404, detail="No RoomX.des files found")
    
    # Parse cabinet data from each .des file
    cabinet_dfs = []
    for des_file in des_files:
        des_path = os.path.join(job_path, des_file)
        df_cabinets = parse_room_to_df(des_path)
        print(f"Parsed {len(df_cabinets)} cabinet rows from {des_file}")
        if not df_cabinets.empty:
            cabinet_dfs.append(df_cabinets)
    
    if not cabinet_dfs:
        raise HTTPException(status_code=400, detail="No cabinet data found in .des files")
    
    df_cabinets_all = pd.concat(cabinet_dfs, ignore_index=True)
    print(f"Total parsed cabinets: {len(df_cabinets_all)}")
    
    # Save cabinet data to MySQL
    conn = get_connection()
    cursor = conn.cursor()
    
    cabinets_table = f"{job_name}_cabinets".replace("-", "_").replace(" ", "_")
    print(f"Using cabinets table: {cabinets_table}")
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS `{cabinets_table}` (
            id INT AUTO_INCREMENT PRIMARY KEY,
            unique_id VARCHAR(255) UNIQUE,
            cabinet_number VARCHAR(20),
            product_name VARCHAR(255)
        )
    """)
    
    # Ensure unique_id column exists
    cursor.execute(f"SHOW COLUMNS FROM `{cabinets_table}` LIKE 'unique_id'")
    if not cursor.fetchone():
        print("unique_id column not found; adding it...")
        cursor.execute(f"ALTER TABLE `{cabinets_table}` ADD COLUMN unique_id VARCHAR(255) UNIQUE")
    
    # Remove cabinets from table that are no longer present in this import
    new_ids = df_cabinets_all['UniqueID'].tolist()
    if new_ids:
        placeholders = ','.join(['%s'] * len(new_ids))
        delete_query = f"DELETE FROM `{cabinets_table}` WHERE unique_id NOT IN ({placeholders})"
        cursor.execute(delete_query, new_ids)
        print(f"Deleted cabinets not in current import from {cabinets_table}")
    
    # Insert or update cabinets
    for _, row in df_cabinets_all.iterrows():
        try:
            cursor.execute(
                f"""INSERT INTO `{cabinets_table}` (cabinet_number, product_name, unique_id)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        cabinet_number = VALUES(cabinet_number),
                        product_name = VALUES(product_name)
                """,
                (row['Cabinet Number'], row['Product Name'], row['UniqueID'])
            )
        except Exception as e:
            print(f"Error inserting cabinet row {row['UniqueID']}: {e}")
    
    # --- Process and store parts ---
    parts_dfs = []
    for des_file in des_files:
        des_path = os.path.join(job_path, des_file)
        df_parts = parse_room_to_parts(des_path)
        if not df_parts.empty:
            parts_dfs.append(df_parts)
    
    if parts_dfs:
        df_parts_all = pd.concat(parts_dfs, ignore_index=True)
        parts_table = f"{job_name}_parts".replace("-", "_").replace(" ", "_")
        print(f"Storing parts in table: {parts_table}")
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS `{parts_table}` (
                id INT AUTO_INCREMENT PRIMARY KEY,
                cabinet_number VARCHAR(20),
                name VARCHAR(255),
                quantity INT,
                width FLOAT,
                length FLOAT,
                type VARCHAR(100),
                comment TEXT,
                scanned BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Clear existing parts for this job
        cursor.execute(f"DELETE FROM `{parts_table}`")
        for _, row in df_parts_all.iterrows():
            cursor.execute(
                f"""INSERT INTO `{parts_table}` 
                    (cabinet_number, name, quantity, width, length, type, comment, scanned)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    row['cabinet_number'],
                    row['name'],
                    row['quantity'],
                    row['width'],
                    row['length'],
                    row['type'],
                    row['comment'],
                    row['scanned']
                )
            )
        print(f"Successfully imported {len(df_parts_all)} parts to {parts_table}")
    
    conn.commit()
    return {"message": f"Imported {len(df_cabinets_all)} cabinets and {len(df_parts_all) if parts_dfs else 0} parts from job: {job_name}"}

@app.get("/cabinets/{job_name}")
def get_cabinets(job_name: str):
    cabinets_table = f"{job_name}_cabinets".replace("-", "_").replace(" ", "_")
    print(f"Fetching cabinet data from table: {cabinets_table}")
    
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute(f"SELECT * FROM `{cabinets_table}`")
        data = cursor.fetchall()
        print(f"Retrieved {len(data)} rows from {cabinets_table}")
        return {"cabinets": data}
    except Exception as e:
        print(f"Error fetching cabinet data: {e}")
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/parts/{job_name}")
def get_parts(job_name: str):
    parts_table = f"{job_name}_parts".replace("-", "_").replace(" ", "_")
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        cursor.execute(f"SELECT * FROM `{parts_table}`")
        data = cursor.fetchall()
        return {"parts": data}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/parts/{job_name}/{cabinet_number}")
def get_parts_for_cabinet(job_name: str, cabinet_number: str):
    parts_table = f"{job_name}_parts".replace("-", "_").replace(" ", "_")
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        cursor.execute(f"SELECT * FROM `{parts_table}` WHERE cabinet_number = %s", (cabinet_number,))
        data = cursor.fetchall()
        return {"parts": data}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
