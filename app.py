from flask import Flask, request, jsonify, Response, render_template
from flask_cors import CORS
import cv2
import numpy as np
import base64
from ultralytics import YOLO
import sqlite3
from datetime import datetime
import random
import string
import csv
import io
import os
import time

app = Flask(__name__)
CORS(app)

print("\n" + "="*50)
print(" 🚀 ROADWATCH AI COMMAND CENTER INITIATED")
print(" 📍 Deployment: Solapur Municipal Corporation (SMC)")
print("="*50)


MODEL_PATH = 'best.pt'
if os.path.exists(MODEL_PATH):
    print(f"[SYSTEM] Loading Edge AI Neural Network ({MODEL_PATH})...")
    model = YOLO(MODEL_PATH)
    print("[SYSTEM] AI Vision Engine Online.")
else:
    print(f"[WARNING] Model '{MODEL_PATH}' not found. Prediction route will fail.")
    model = None


def init_db():
    print("[SYSTEM] Initializing SQLite Data Lake...")
    conn = sqlite3.connect('roadwatch_smc.db')
    c = conn.cursor()
    
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS defects (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            defect_class TEXT,
            confidence REAL,
            lat TEXT,
            lng TEXT,
            severity TEXT,
            detected_at TEXT,
            status TEXT DEFAULT 'REPORTED',
            assigned_department TEXT,
            contractor_name TEXT,
            repair_image_url TEXT,
            citizen_feedback TEXT
        )
    ''')
    
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS citizen_reports (
            report_id TEXT PRIMARY KEY,
            citizen_name TEXT,
            mobile TEXT,
            ward TEXT,
            issue_type TEXT,
            severity TEXT,
            coordinates TEXT,
            description TEXT,
            status TEXT,
            timestamp TEXT
        )
    ''')
    
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS spending_records (
            ticket_id TEXT PRIMARY KEY,
            location TEXT,
            contractor TEXT,
            amount REAL,
            status TEXT,
            created_at TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("[SYSTEM] Database connected and ready.\n")

init_db()

@app.route('/')
def home():
    """Serves the visually stunning index.html dashboard"""
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    if model is None:
         return jsonify({'status': 'error', 'message': 'AI Model not loaded on server.'}), 500

    if 'image' not in request.files:
        return jsonify({'status': 'error', 'message': 'No image payload received.'}), 400
    
    try:
        file = request.files['image']
        npimg = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
        
        
        time.sleep(0.5) 

        
        results = model(img)
        
        detections = []
        total_volume_m3 = 0.0 
        
        conn = sqlite3.connect('roadwatch_smc.db')
        c = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                class_name = model.names[cls]
                
                
                pixel_to_meter = 0.01 
                width_m = (x2 - x1) * pixel_to_meter
                height_m = (y2 - y1) * pixel_to_meter
                area_m2 = width_m * height_m
                
                depth_m = 0.1 
                volume_m3 = area_m2 * depth_m
                total_volume_m3 += volume_m3
                
                
                cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 0), 2)
                cv2.putText(img, f'{class_name} {conf:.2f}', (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
                
                severity = "High" if conf > 0.7 else "Medium"
                
                # Geotagging simulation for Solapur
                lat = f"17.{random.randint(65000, 67000)}"
                lng = f"75.{random.randint(89000, 91000)}"
                
                c.execute('''
                    INSERT INTO defects (defect_class, confidence, lat, lng, severity, detected_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (class_name, conf, lat, lng, severity, now, 'REPORTED'))
                
                record_id = c.lastrowid 
                
                c.execute('''
                    UPDATE defects SET status = ? WHERE record_id = ?
                ''', ('AI_ANALYZED', record_id))
                
                detections.append({
                    "record_id": record_id, 
                    "label": class_name,
                    "confidence": round(conf * 100, 1), # Convert to cleaner percentage
                    "location": f"[{lat}, {lng}]",
                    "time": now,
                    "severity": severity,
                    "department": "SMC Road Engineering",
                    "status": "AI_ANALYZED"
                })
        
        conn.commit()
        conn.close()
        
        # Calculate budget and scores
        total_tons = total_volume_m3 * 2.4
        total_cost = total_tons * 4500
        
        defect_count = len(detections)
        quality_score = max(0, 100 - (defect_count * 5))
        if quality_score > 80:
            health_status = "Good Condition"
        elif quality_score > 50:
            health_status = "Maintenance Required"
        else:
            health_status = "CRITICAL HAZARD"
        
        _, buffer = cv2.imencode('.jpg', img)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        visual_evidence = f"data:image/jpeg;base64,{img_base64}"
        
        return jsonify({
            "status": "success",
            "visual_evidence": visual_evidence,
            "quality_score": quality_score,
            "health_status": health_status,
            "data": detections,
            "est_tons": round(total_tons, 2),
            "est_cost": round(total_cost, 0)
        })
    except Exception as e:
        print(f"[ERROR] AI Pipeline Failed: {str(e)}")
        return jsonify({"status": "error", "message": "Neural network processing failed."}), 500

@app.route('/api/advance_workflow', methods=['POST'])
def advance_workflow():
    data = request.json
    record_id = data.get('record_id')
    new_status = data.get('new_status')
    
    allowed_states = [
        'REPORTED', 'AI_ANALYZED', 'SMC_REVIEW', 'DEPT_ASSIGNED', 
        'CONTRACTOR_ASSIGNED', 'REPAIRED', 'CITIZEN_VERIFIED', 'CLOSED'
    ]
    
    if new_status not in allowed_states:
        return jsonify({'status': 'error', 'message': f'Invalid status. Must be one of {allowed_states}'}), 400

    try:
        conn = sqlite3.connect('roadwatch_smc.db')
        c = conn.cursor()
        
        query = "UPDATE defects SET status = ?"
        params = [new_status]
        
        if 'assigned_department' in data:
            query += ", assigned_department = ?"
            params.append(data['assigned_department'])
        if 'contractor_name' in data:
            query += ", contractor_name = ?"
            params.append(data['contractor_name'])
            
        query += " WHERE record_id = ?"
        params.append(record_id)
        
        c.execute(query, tuple(params))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "message": f"Ticket {record_id} advanced to {new_status}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        conn = sqlite3.connect('roadwatch_smc.db')
        conn.row_factory = sqlite3.Row  
        c = conn.cursor()
        c.execute('SELECT * FROM defects ORDER BY record_id DESC LIMIT 50')
        rows = c.fetchall()
        conn.close()
        
        data = [dict(row) for row in rows]
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/spending', methods=['GET'])
def get_spending():
    try:
        conn = sqlite3.connect('roadwatch_smc.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM spending_records ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        records = []
        for row in rows:
            records.append({
                "ticket_id": row[0],
                "location": row[1],
                "contractor": row[2],
                "amount": row[3],
                "status": row[4],
                "created_at": row[5]
            })
        return jsonify(records)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/report', methods=['POST'])
def submit_report():
    try:
        data = request.get_json()
        conn = sqlite3.connect('roadwatch_smc.db')
        cursor = conn.cursor()
        
        report_id = 'CIT-' + ''.join(random.choices(string.digits, k=3))
        
        cursor.execute('''
            INSERT INTO citizen_reports 
            (report_id, citizen_name, mobile, ward, issue_type, severity, coordinates, description, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'REPORTED', datetime('now'))
        ''', (
            report_id,
            data.get('name', 'Anonymous'),
            data.get('mobile', ''),
            data.get('ward', ''),
            data.get('issue_type', 'Pothole'),
            data.get('severity', 'High'),
            data.get('coordinates', ''),
            data.get('description', '')
        ))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "report_id": report_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/export', methods=['GET'])
def export_csv():
    try:
        conn = sqlite3.connect('roadwatch_smc.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM defects ORDER BY detected_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['record_id', 'defect_class', 'confidence', 'lat', 'lng', 'severity', 'detected_at', 'status', 'assigned_department', 'contractor_name', 'repair_image_url', 'citizen_feedback'])
        writer.writerows(rows)
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=roadwatch_audit_trail.csv'}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
  tion
    app.run(debug=True, port=5000)