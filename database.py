import sqlite3
import os
from datetime import datetime

DB_NAME = 'smc_urbanfix.db'


WORKFLOW_STATES = [
    'REPORTED',
    'AI_ANALYZED', 
    'SMC_REVIEW',
    'DEPT_ASSIGNED',
    'CONTRACTOR_ASSIGNED',
    'REPAIRED',
    'CITIZEN_VERIFIED',
    'CLOSED'
]

def get_db_connection():
    """Establish a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  
    return conn

def init_db():
    """Initialize the database with the new 8-stage workflow schema."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS infrastructure_defects (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            defect_class TEXT NOT NULL,
            confidence REAL NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            severity TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            
            -- THE NEW WORKFLOW STATUS COLUMN --
            -- Allowed states: REPORTED, AI_ANALYZED, SMC_REVIEW, DEPT_ASSIGNED, 
            -- CONTRACTOR_ASSIGNED, REPAIRED, CITIZEN_VERIFIED, CLOSED
            status TEXT NOT NULL DEFAULT 'REPORTED',
            
            -- METADATA COLUMNS FOR THE NEW WORKFLOW --
            assigned_department TEXT,      -- e.g., 'PWD Road Engineering'
            contractor_name TEXT,          -- e.g., 'Acme Paving Co.'
            repair_image_url TEXT,         -- Image proof uploaded by contractor
            citizen_feedback TEXT          -- Notes from the CITIZEN_VERIFIED stage
        )
    ''')
    
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS citizen_reports (
            report_id TEXT PRIMARY KEY,
            citizen_name TEXT,
            mobile TEXT,
            ward TEXT,
            issue_type TEXT,
            severity TEXT,
            coordinates TEXT,
            description TEXT,
            status TEXT DEFAULT 'REPORTED',
            timestamp DATETIME
        )
    ''')

    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS spending_records (
            ticket_id TEXT PRIMARY KEY,
            location TEXT,
            contractor TEXT,
            amount INTEGER,
            status TEXT DEFAULT 'PENDING',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"[DB INFO] Initialized database '{DB_NAME}' with advanced workflow schema & transparency tables.")

def insert_defect(defect_class, confidence, lat, lon, severity):
    """
    Inserts a newly detected defect. 
    By default, it enters the workflow at the 'REPORTED' stage.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        INSERT INTO infrastructure_defects 
        (defect_class, confidence, latitude, longitude, severity, timestamp, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (defect_class, confidence, lat, lon, severity, timestamp, 'REPORTED'))
    
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def update_defect_status(record_id, new_status, **kwargs):
    """
    Moves the defect to the next stage in the workflow.
    Allows updating metadata (like assigned_department) simultaneously.
    """
    if new_status not in WORKFLOW_STATES:
        raise ValueError(f"Invalid status. Must be one of: {WORKFLOW_STATES}")

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "UPDATE infrastructure_defects SET status = ?"
    params = [new_status]

    if 'assigned_department' in kwargs:
        query += ", assigned_department = ?"
        params.append(kwargs['assigned_department'])
    if 'contractor_name' in kwargs:
        query += ", contractor_name = ?"
        params.append(kwargs['contractor_name'])
    if 'repair_image_url' in kwargs:
        query += ", repair_image_url = ?"
        params.append(kwargs['repair_image_url'])
    if 'citizen_feedback' in kwargs:
        query += ", citizen_feedback = ?"
        params.append(kwargs['citizen_feedback'])

    query += " WHERE record_id = ?"
    params.append(record_id)

    cursor.execute(query, tuple(params))
    conn.commit()
    conn.close()
    
    return True

def get_all_defects():
    """Fetches all logs to display on the frontend System Logs table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM infrastructure_defects ORDER BY timestamp DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


if __name__ == '__main__':
    init_db()