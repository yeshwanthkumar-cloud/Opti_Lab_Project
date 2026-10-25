import os
import io
import time
import random
import json
import base64
import requests
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from flask import Flask, render_template, jsonify, request, send_file
from datetime import datetime, timedelta
import pandas as pd

app = Flask(__name__)

# Environment & Database Configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
DATA_FILE = "data.json"

# GitHub API Database Backup Configuration (Optional fallback)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
FILE_PATH = "data.json"

DEPARTMENTS = ["Battery Lab", "Cell Lab", "Vibration Team", "E&E Lab"]

DEFAULT_CHAMBERS = [
    {"id": "Chamber-1", "name": "Chamber 1", "type": "chamber", "img": "/static/images/chamber.png"},
    {"id": "Chamber-2", "name": "Chamber 2", "type": "chamber", "img": "/static/images/chamber.png"},
    {"id": "Chamber-3", "name": "Chamber 3", "type": "chamber", "img": "/static/images/chamber.png"},
    {"id": "Chamber-4", "name": "Chamber 4", "type": "chamber", "img": "/static/images/chamber.png"},
    {"id": "Chamber-5", "name": "Chamber 5", "type": "chamber", "img": "/static/images/chamber.png"},
    {"id": "Chamber-6", "name": "Chamber 6", "type": "chamber", "img": "/static/images/chamber.png"},
    {"id": "Chamber-7", "name": "Chamber 7", "type": "chamber", "img": "/static/images/chamber.png"},
    {"id": "Chamber-8", "name": "Chamber 8", "type": "chamber", "img": "/static/images/chamber.png"}
]

DEFAULT_CYCLERS = [
    {"id": "EA-Cycler-1", "name": "EA Cycler 1", "type": "cycler", "img": "/static/images/ea_cycler.png"},
    {"id": "EA-Cycler-2", "name": "EA Cycler 2", "type": "cycler", "img": "/static/images/ea_cycler.png"},
    {"id": "EA-Cycler-3", "name": "EA Cycler 3", "type": "cycler", "img": "/static/images/ea_cycler.png"},
    {"id": "EA-Cycler-4", "name": "EA Cycler 4", "type": "cycler", "img": "/static/images/ea_cycler.png"},
    {"id": "EA-Cycler-5", "name": "EA Cycler 5", "type": "cycler", "img": "/static/images/ea_cycler.png"},
    {"id": "EA-Cycler-6", "name": "EA Cycler 6", "type": "cycler", "img": "/static/images/ea_cycler.png"},
    {"id": "EA-Cycler-7", "name": "EA Cycler 7", "type": "cycler", "img": "/static/images/ea_cycler.png"},
    {"id": "ITECH-1", "name": "ITECH Cycler 1", "type": "cycler", "img": "/static/images/itech_cycler.png"},
    {"id": "ITECH-2", "name": "ITECH Cycler 2", "type": "cycler", "img": "/static/images/itech_cycler.png"},
    {"id": "ITECH-3", "name": "ITECH Cycler 3", "type": "cycler", "img": "/static/images/itech_cycler.png"},
    {"id": "Neware-1", "name": "Neware Cycler 1", "type": "cycler", "img": "/static/images/neware_cycler.png"},
    {"id": "Neware-2", "name": "Neware Cycler 2", "type": "cycler", "img": "/static/images/neware_cycler.png"}
]

DIGITAL_TWINS = {
    "Battery Lab": {
        "title": "Battery Lab Spatial Twin",
        "top_row": DEFAULT_CHAMBERS,
        "bottom_row": DEFAULT_CYCLERS
    },
    "Cell Lab": {
        "title": "Cell Lab Spatial Twin",
        "top_row": DEFAULT_CHAMBERS[:4],
        "bottom_row": DEFAULT_CYCLERS[:6]
    },
    "Vibration Team": {
        "title": "Vibration Team — High-Capacity Shakers",
        "top_row": [
            {"id": "Shaker-1.5T", "name": "1.5-Ton Tri-Axial Shaker", "type": "shaker-large", "img": "/static/images/shaker.png"},
            {"id": "Shaker-3T", "name": "3.0-Ton Tri-Axial Shaker", "type": "shaker-large", "img": "/static/images/shaker.png"},
            {"id": "Shaker-SDYN", "name": "SDYN Shaker Rig", "type": "shaker-large", "img": "/static/images/shaker.png"}
        ],
        "bottom_row": []
    },
    "E&E Lab": {
        "title": "E&E Lab Spatial Twin",
        "top_row": DEFAULT_CHAMBERS[:6],
        "bottom_row": DEFAULT_CYCLERS[:4]
    }
}

LAB_DATA = {
    dept: {
        "components": [],
        "blueprints": {},
        "personnel": [],
        "tasks": [],
        "attendance": [],
        "extra_tasks": [],
        "audit_history": [],
        "roster_stamps": {},
        "equipment_maintenance": {}
    } for dept in DEPARTMENTS
}

def get_db_connection():
    if DATABASE_URL:
        try:
            return psycopg2.connect(
                DATABASE_URL,
                sslmode='require',
                connect_timeout=10
            )
        except Exception as e:
            print("DB Connection Error:", e)
            return None
    return None

def init_db():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS opti_lab_store (
                    id VARCHAR(50) PRIMARY KEY,
                    data JSONB NOT NULL
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lab_fives_submissions (
                    id SERIAL PRIMARY KEY,
                    lab_name VARCHAR(50),
                    shift VARCHAR(20),
                    submitted_by VARCHAR(100),
                    verified_by VARCHAR(100),
                    fives_data JSONB,
                    notes TEXT,
                    status VARCHAR(20) DEFAULT 'Pass',
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chamber_daily_submissions (
                    id SERIAL PRIMARY KEY,
                    chamber_name VARCHAR(100),
                    shift VARCHAR(20),
                    submitted_by VARCHAR(100),
                    checks_data JSONB,
                    notes TEXT,
                    status VARCHAR(20) DEFAULT 'Pass',
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS equipment_master (
                    id SERIAL PRIMARY KEY,
                    equipment_name VARCHAR(100) UNIQUE NOT NULL,
                    pm_date DATE,
                    calibration_due_date DATE
                );
            """)
            conn.commit()
            cursor.close()
            conn.close()
            print("Database initialized successfully.")
        except Exception as e:
            print("Database initialization error:", e)

def save_data_permanently():
    """Permanent storage: Writes synchronously to Postgres first."""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO opti_lab_store (id, data)
                VALUES ('master', %s)
                ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data;
            """, (json.dumps(LAB_DATA),))
            conn.commit()
            cursor.close()
            conn.close()
            print("Data saved permanently to PostgreSQL DB.")
        except Exception as e:
            print("PostgreSQL Save Error:", e)

    try:
        with open(DATA_FILE, "w") as f:
            json.dump(LAB_DATA, f, indent=4)
    except Exception as e:
        print("Local disk save error:", e)

    if GITHUB_TOKEN and "ghp_" in GITHUB_TOKEN and GITHUB_REPO:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            get_res = requests.get(url, headers=headers)
            sha = get_res.json().get("sha") if get_res.status_code == 200 else None

            content_bytes = json.dumps(LAB_DATA, indent=2).encode('utf-8')
            encoded_content = base64.b64encode(content_bytes).decode('utf-8')

            payload = {"message": "Automated DB Update", "content": encoded_content}
            if sha:
                payload["sha"] = sha

            requests.put(url, json=payload, headers=headers)
        except Exception as e:
            print("GitHub backup error (non-fatal):", e)

def load_data_permanently():
    global LAB_DATA
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT data FROM opti_lab_store WHERE id = 'master';")
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row and row['data']:
                saved_data = row['data']
                if isinstance(saved_data, str):
                    saved_data = json.loads(saved_data)
                for dept in DEPARTMENTS:
                    if dept in saved_data:
                        LAB_DATA[dept] = saved_data[dept]
                print("Restored permanent state from PostgreSQL.")
                return
        except Exception as e:
            print("PostgreSQL Load Error:", e)

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                saved_data = json.load(f)
                for dept in DEPARTMENTS:
                    if dept in saved_data:
                        LAB_DATA[dept] = saved_data[dept]
            print("Restored state from data.json.")
        except Exception as e:
            print("Local Load Error:", e)

init_db()
load_data_permanently()

def log_audit_event(dept, title, detail, user="System"):
    LAB_DATA[dept]["audit_history"].insert(0, {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "title": title,
        "detail": detail,
        "user": user
    })

def calculate_dashboard_metrics(tasks):
    total_complete = 0
    total_running = 0
    total_awaiting_res = 0
    total_awaiting_eng = 0
   
    cat_counts = {"450": {"running": 0, "complete": 0}, "DIESEL": {"running": 0, "complete": 0}, "EL": {"running": 0, "complete": 0}}
    stoppage_breakdown = {"no_parts": 0, "chamber_down": 0, "fixture_adjust": 0}
    shift_completion = {"Shift A": {"completed": 0, "assigned": 0}, "Shift B": {"completed": 0, "assigned": 0}, "Shift C": {"completed": 0, "assigned": 0}}
    incharge_stats = {}
    associate_stats = {}
    
    for t in tasks:
        cat = t.get("category", "450")
        if cat not in cat_counts:
            cat_counts[cat] = {"running": 0, "complete": 0}
           
        if t.get("status") in ["Completed", "Awaiting Report"]:
            total_complete += 1
            cat_counts[cat]["complete"] += 1
        elif t.get("status") == "Running":
            total_running += 1
            cat_counts[cat]["running"] += 1
        elif t.get("status") in ["Blocked", "Parts Missing"]:
            total_awaiting_res += 1
        else:
            total_awaiting_eng += 1
            
        for st in t.get("subtasks", []):
            shift = st.get("shift", "None")
            if shift in shift_completion:
                shift_completion[shift]["assigned"] += 1
                if st.get("status") == "Completed":
                    shift_completion[shift]["completed"] += 1
            inc = st.get("incharge", "Unassigned")
            if inc != "Unassigned":
                incharge_stats.setdefault(inc, {"completed": 0, "managed": 0})
                incharge_stats[inc]["managed"] += 1
                if st.get("status") == "Completed":
                    incharge_stats[inc]["completed"] += 1
            assoc = st.get("associate", "Unassigned")
            if assoc != "Unassigned":
                associate_stats.setdefault(assoc, {"completed": 0, "assigned": 0})
                associate_stats[assoc]["assigned"] += 1
                if st.get("status") == "Completed":
                    associate_stats[assoc]["completed"] += 1
            if st.get("status") == "Parts Missing":
                stoppage_breakdown["no_parts"] += 1
            elif st.get("status") == "Blocked":
                stoppage_breakdown["chamber_down"] += 1

    return {
        "complete": total_complete,
        "running": total_running,
        "awaiting_res": total_awaiting_res,
        "awaiting_eng": total_awaiting_eng,
        "cat_counts": cat_counts,
        "stoppage_breakdown": stoppage_breakdown,
        "shift_completion": shift_completion,
        "incharge_stats": incharge_stats,
        "associate_stats": associate_stats
    }

# --- ROUTES ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/lab/<dept_name>")
def get_lab_data(dept_name):
    dept = dept_name if dept_name in LAB_DATA else "Battery Lab"
    shift_filter = request.args.get("shift")
    
    all_tasks = LAB_DATA[dept]["tasks"]
    processed_tasks = []
    
    for t in all_tasks:
        task_copy = dict(t)
        subtask_list = []
        for st in t.get("subtasks", []):
            st_copy = dict(st)
            shift_val = st_copy.get("shift", "None")
            status_val = st_copy.get("status", "To Do")

            if shift_filter:
                if shift_val in ["None", "", None]:
                    continue
                if shift_val == shift_filter or shift_val == "Multi-Shift":
                    subtask_list.append(st_copy)
                elif status_val in ["Running", "Blocked", "Parts Missing", "In Progress"]:
                    st_copy["rollover_from"] = shift_val
                    subtask_list.append(st_copy)
            else:
                subtask_list.append(st_copy)

        if not shift_filter or len(subtask_list) > 0:
            task_copy["subtasks"] = subtask_list
            processed_tasks.append(task_copy)

    metrics = calculate_dashboard_metrics(all_tasks)
    dept_components = list(dict.fromkeys(LAB_DATA[dept]["components"]))
    twin_config = DIGITAL_TWINS.get(dept, DIGITAL_TWINS["Battery Lab"])

    return jsonify({
        "dept": dept,
        "components": dept_components,
        "blueprints": LAB_DATA[dept]["blueprints"],
        "personnel": LAB_DATA[dept]["personnel"],
        "tasks": processed_tasks,
        "attendance": LAB_DATA[dept]["attendance"],
        "extra_tasks": LAB_DATA[dept]["extra_tasks"],
        "audit_history": LAB_DATA[dept]["audit_history"],
        "equipment_maintenance": LAB_DATA[dept].get("equipment_maintenance", {}),
        "metrics": metrics,
        "twin": twin_config
    })

@app.route("/api/tasks/create", methods=["POST"])
def create_master_task():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
   
    if dept in LAB_DATA:
        # Strictly non-repeating Task ID across all departments
        all_existing_task_nums = []
        for d in DEPARTMENTS:
            for t in LAB_DATA.get(d, {}).get("tasks", []):
                try:
                    num = int(str(t.get("task_id", "")).replace("TSK-", ""))
                    all_existing_task_nums.append(num)
                except (ValueError, TypeError):
                    pass
        
        next_task_num = max(all_existing_task_nums, default=400000) + 1
        task_id = f"TSK-{next_task_num}"

        # Globally unique Subtask IDs using microsecond timestamp + random salt
        steps = data.get("steps", [])
        subtasks = []
        base_ts = int(time.time() * 1000000)
        
        for idx, s in enumerate(steps):
            unique_salt = random.randint(100, 999)
            sub_id = f"SUB-{(base_ts % 1000000) + idx:06d}{unique_salt}"
            
            subtasks.append({
                "sub_id": sub_id,
                "name": s.get("name", f"Step {idx+1}"),
                "status": "To Do",
                "logged": 0,
                "target": float(s.get("target", 1)),
                "unit": s.get("unit", "Hours"),
                "assign_date": s.get("assign_date", datetime.now().strftime("%Y-%m-%d")),
                "shift": s.get("shift", "None"),
                "incharge": s.get("incharge", "Unassigned"),
                "associate": s.get("associate", "Unassigned"),
                "parts_status": "Parts Available",
                "chamber": "None",
                "cycler": "None",
                "neware_channel": "",
                "grafana": "",
                "observations": []
            })
           
        new_task = {
            "task_id": task_id,
            "prio": data.get("prio", "P1"),
            "bin": data.get("bin", ""),
            "drive_link": data.get("drive_link", "").strip(),
            "component": data.get("component", "General Hardware"),
            "trf_ref": data.get("trf_id", "-"),
            "dvp_name": data.get("dvp_name", "Custom Flow"),
            "category": data.get("category", "450"),
            "sprint_no": data.get("sprint_no", ""),
            "objective": data.get("objective", ""),
            "background": data.get("background", ""),
            "engineer": data.get("engineer", ""),
            "progress": 0,
            "status": "Running",
            "shift": "Multi-Shift",
            "trf_status": "Testing Active",
            "subtasks": subtasks
        }
       
        LAB_DATA[dept]["tasks"].append(new_task)
        log_audit_event(dept, "Master Task Created", f"Task {task_id} ({data.get('bin')}) generated with {len(subtasks)} unique subtasks.", data.get('engineer', 'Lead Engineer'))
        save_data_permanently()
        return jsonify({"success": True, "task": new_task})
    return jsonify({"success": False}), 400

@app.route("/api/tasks/edit", methods=["POST"])
def edit_master_task():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
    task_id = data.get("task_id")
    new_task_id = str(data.get("new_task_id", "")).strip()
    
    if dept in LAB_DATA and task_id:
        for t in LAB_DATA[dept]["tasks"]:
            if t["task_id"] == task_id:
                if new_task_id and new_task_id != task_id:
                    if any(existing["task_id"] == new_task_id for existing in LAB_DATA[dept]["tasks"]):
                        return jsonify({"success": False, "message": "That Task ID already exists"}), 400
                    t["task_id"] = new_task_id

                t["bin"] = data.get("bin", t.get("bin", ""))
                t["drive_link"] = data.get("drive_link", t.get("drive_link", "")).strip()
                t["dvp_name"] = data.get("dvp_name", t.get("dvp_name", ""))
                t["component"] = data.get("component", t.get("component", "General Hardware"))
                t["category"] = data.get("category", t.get("category", "450"))
                t["prio"] = data.get("prio", t.get("prio", "P1"))
                t["objective"] = data.get("objective", t.get("objective", ""))
                t["engineer"] = data.get("engineer", t.get("engineer", ""))
                t["sprint_no"] = data.get("sprint_no", t.get("sprint_no", ""))
                
                incoming_steps = data.get("steps")
                if incoming_steps is not None:
                    updated_subtasks = []
                    base_ts = int(time.time() * 1000000)
                    for idx, s in enumerate(incoming_steps):
                        sub_id = s.get("sub_id") or f"SUB-{(base_ts % 1000000) + idx:06d}{random.randint(100, 999)}"
                        updated_subtasks.append({
                            "sub_id": sub_id,
                            "name": s.get("name", f"Step {idx+1}"),
                            "status": s.get("status", "To Do"),
                            "logged": float(s.get("logged", 0)),
                            "target": float(s.get("target", 1)),
                            "unit": s.get("unit", "Hours"),
                            "assign_date": s.get("assign_date", datetime.now().strftime("%Y-%m-%d")),
                            "shift": s.get("shift", "None"),
                            "incharge": s.get("incharge", "Unassigned"),
                            "associate": s.get("associate", "Unassigned"),
                            "parts_status": s.get("parts_status", "Parts Available"),
                            "chamber": s.get("chamber", "None"),
                            "cycler": s.get("cycler", "None"),
                            "neware_channel": s.get("neware_channel", ""),
                            "grafana": s.get("grafana", ""),
                            "observations": s.get("observations", [])
                        })
                    t["subtasks"] = updated_subtasks
                    
                    total_target = sum(float(sub.get("target", 1)) for sub in t["subtasks"])
                    total_logged = sum(float(sub.get("logged", 0)) for sub in t["subtasks"])
                    t["progress"] = int((total_logged / total_target) * 100) if total_target > 0 else 0

                log_audit_event(dept, "Master Task Edited", f"Task {task_id} details updated.", t.get("engineer", "System"))
                save_data_permanently()
                return jsonify({"success": True, "task": t})
                
    return jsonify({"success": False, "message": "Task not found"}), 400

@app.route("/api/tasks/delete", methods=["POST"])
def delete_single_task():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
    task_id = data.get("task_id")
   
    if dept in LAB_DATA and task_id:
        original_count = len(LAB_DATA[dept]["tasks"])
        LAB_DATA[dept]["tasks"] = [t for t in LAB_DATA[dept]["tasks"] if t["task_id"] != task_id]
       
        if len(LAB_DATA[dept]["tasks"]) < original_count:
            log_audit_event(dept, "Task Deleted", f"Permanently removed task {task_id}.")
            save_data_permanently()
            return jsonify({"success": True})
           
    return jsonify({"success": False, "message": "Task not found"}), 400

@app.route("/api/subtasks/update", methods=["POST"])
def update_subtask():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
    task_id = data.get("task_id")
    sub_id = data.get("sub_id")
   
    if dept in LAB_DATA and task_id and sub_id:
        for t in LAB_DATA[dept]["tasks"]:
            if t["task_id"] == task_id:
                for st in t.get("subtasks", []):
                    if st["sub_id"] == sub_id:
                        if "associate" in data:
                            st["associate"] = str(data.get("associate") or "Unassigned").strip()
                        if "incharge" in data:
                            st["incharge"] = str(data.get("incharge") or "Unassigned").strip()
                        if "shift" in data:
                            st["shift"] = str(data.get("shift") or "None").strip()
                        if "assign_date" in data:
                            st["assign_date"] = str(data.get("assign_date") or datetime.now().strftime("%Y-%m-%d")).strip()

                        if "chamber" in data and data.get("chamber"):
                            st["chamber"] = data.get("chamber")
                        if "cycler" in data and data.get("cycler"):
                            st["cycler"] = data.get("cycler")
                        if "neware_channel" in data:
                            st["neware_channel"] = data.get("neware_channel", "")
                        if "grafana" in data:
                            st["grafana"] = data.get("grafana", "")
                       
                        try:
                            add_p = float(data.get("add_progress", 0))
                        except (ValueError, TypeError):
                            add_p = 0.0
                            
                        if add_p > 0:
                            st["logged"] = float(st.get("logged", 0)) + add_p
                       
                        manual_status = data.get("status")
                        if manual_status:
                            st["status"] = manual_status
                        elif float(st.get("target", 1)) > 0 and float(st.get("logged", 0)) >= float(st.get("target", 1)):
                            st["status"] = "Completed"
                       
                        notes = data.get("notes", "").strip()
                        if notes:
                            if "observations" not in st:
                                st["observations"] = []
                            st["observations"].append({
                                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "associate": st.get("associate"),
                                "shift": st.get("shift"),
                                "chamber": st.get("chamber"),
                                "cycler": st.get("cycler"),
                                "channel": st.get("neware_channel"),
                                "notes": notes
                            })
                           
                        total_target = sum(float(s.get("target", 1)) for s in t["subtasks"])
                        total_logged = sum(float(s.get("logged", 0)) for s in t["subtasks"])
                        t["progress"] = int((total_logged / total_target) * 100) if total_target > 0 else 0
                        
                        if all(s.get("status") == "Completed" for s in t["subtasks"]):
                            t["status"] = "Completed"
                        elif any(s.get("status") in ["Running", "Blocked", "Parts Missing"] for s in t["subtasks"]):
                            t["status"] = "Running"
                           
                        log_audit_event(dept, "Subtask Assigned / Updated", f"{sub_id} on {t['task_id']}: Shift={st['shift']}, Inc={st['incharge']}, Assoc={st['associate']}.", st.get("associate", "System"))
                        save_data_permanently()
                        return jsonify({"success": True, "subtask": st, "task_progress": t["progress"]})
                        
    return jsonify({"success": False, "message": "Task or subtask not found"}), 400

@app.route("/api/blueprints/save", methods=["POST"])
def save_blueprint():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
    name = data.get("name")
    steps = data.get("steps", [])
    if dept in LAB_DATA and name and steps:
        LAB_DATA[dept]["blueprints"][name] = steps
        log_audit_event(dept, "Flow Blueprint Saved", f"Saved reusable test flow: {name} with {len(steps)} steps.")
        save_data_permanently()
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route("/api/components/add", methods=["POST"])
def add_component():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
    name = data.get("name")
    if dept in LAB_DATA and name:
        if name not in LAB_DATA[dept]["components"]:
            LAB_DATA[dept]["components"].append(name)
            log_audit_event(dept, "Component Registered", f"Added component: {name} to {dept}")
            save_data_permanently()
            return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route("/api/personnel/add", methods=["POST"])
def add_personnel():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
    if dept in LAB_DATA:
        schedule = [data.get("shift", "Shift A")] * 30
        new_member = {
            "id": data.get("emp_id", f"EMP-{len(LAB_DATA[dept]['personnel']) + 101}"),
            "name": str(data.get("name")).strip(),
            "role": data.get("role", "Associate"),
            "shift": data.get("shift", "Shift A"),
            "schedule": schedule
        }
        LAB_DATA[dept]["personnel"].append(new_member)
        log_audit_event(dept, "Personnel Added", f"Registered {new_member['name']} ({new_member['role']}) to {new_member['shift']}.")
        save_data_permanently()
        return jsonify({"success": True, "personnel": new_member})
    return jsonify({"success": False}), 400

@app.route("/api/attendance/mark", methods=["POST"])
def mark_attendance():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
    if dept in LAB_DATA:
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "emp_name": data.get("emp_name"),
            "shift": data.get("shift", "Shift A"),
            "action": data.get("action", "Check In"),
            "status": data.get("status", "Present"),
            "time_in": datetime.now().strftime("%H:%M")
        }
        LAB_DATA[dept]["attendance"].append(entry)
        log_audit_event(dept, "Attendance Punch", f"{data.get('emp_name')} logged {data.get('action')} on {data.get('shift')} ({data.get('status')}).", data.get('emp_name'))
        save_data_permanently()
        return jsonify({"success": True, "entry": entry})
    return jsonify({"success": False}), 400

@app.route("/api/roster/<dept_name>")
def get_roster(dept_name):
    dept = dept_name if dept_name in LAB_DATA else "Battery Lab"
    days = list(range(1, 31))
    matrix = []
    for p in LAB_DATA[dept]["personnel"]:
        matrix.append({
            "id": p["id"],
            "name": p["name"],
            "role": p["role"],
            "shift": p["shift"],
            "schedule": p["schedule"]
        })
    return jsonify({"days": days, "matrix": matrix})

@app.route("/api/roster/update", methods=["POST"])
def update_roster_cell():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
    emp_id = data.get("emp_id")
    day_idx = data.get("day_idx")
    new_shift = data.get("new_shift")
   
    if dept in LAB_DATA:
        for p in LAB_DATA[dept]["personnel"]:
            if p["id"] == emp_id:
                if day_idx is not None and 0 <= day_idx < 30:
                    p["schedule"][day_idx] = new_shift
                if "default_shift" in data:
                    p["shift"] = data["default_shift"]
                save_data_permanently()
                return jsonify({"success": True, "schedule": p["schedule"]})
    return jsonify({"success": False}), 400

@app.route("/api/roster/stamp", methods=["POST"])
def stamp_roster():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
    name = data.get("name")
    shift = data.get("shift")
    date_str = data.get("date")
   
    if dept in LAB_DATA and name and date_str:
        key = f"{name}_{date_str}"
        LAB_DATA[dept]["roster_stamps"][key] = shift
        log_audit_event(dept, "Roster Stamped", f"Stamped {shift} for {name} on {date_str}.")
        save_data_permanently()
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route("/api/extra_tasks/add", methods=["POST"])
def add_extra_task():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
    if dept in LAB_DATA:
        extra = {
            "id": f"EXT-{len(LAB_DATA[dept]['extra_tasks']) + 1}",
            "title": data.get("title"),
            "logged_by": data.get("logged_by"),
            "shift": data.get("shift"),
            "notes": data.get("notes")
        }
        LAB_DATA[dept]["extra_tasks"].append(extra)
        log_audit_event(dept, "Unplanned Task Logged", f"Ad-hoc task '{data.get('title')}' logged by {data.get('logged_by')}.", data.get('logged_by'))
        save_data_permanently()
        return jsonify({"success": True, "extra": extra})
    return jsonify({"success": False}), 400

@app.route('/api/5s-submit', methods=['POST'])
def submit_5s():
    data = request.json or {}
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO lab_fives_submissions
            (lab_name, shift, submitted_by, verified_by, fives_data, notes, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        ''', (
            data.get('lab_name', 'Battery Lab'),
            data.get('shift', 'Shift A'),
            data.get('submitted_by', 'Operator'),
            data.get('verified_by', ''),
            Json(data.get('fives_data', {})),
            data.get('notes', ''),
            data.get('status', 'Pass')
        ))
        conn.commit()
        cur.close()
        conn.close()
   
    dept = data.get('lab_name', 'Battery Lab')
    if dept in LAB_DATA:
        log_audit_event(dept, "5S Checksheet Submitted", f"5S log recorded for {data.get('shift')} by {data.get('submitted_by')}.")
        save_data_permanently()
    return jsonify({"status": "success", "message": f"5S Check Sheet recorded!"})

@app.route('/api/chamber-check-submit', methods=['POST'])
def submit_chamber_check():
    data = request.json or {}
    chamber_name = data.get('chamber_name', 'Chamber-1')
    dept = data.get('dept', 'Battery Lab')
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO chamber_daily_submissions
            (chamber_name, shift, submitted_by, checks_data, notes, status)
            VALUES (%s, %s, %s, %s, %s, %s);
        ''', (
            chamber_name,
            data.get('shift', 'Shift A'),
            data.get('submitted_by', 'Operator'),
            Json(data.get('checks_data', {})),
            data.get('notes', ''),
            data.get('status', 'Pass')
        ))
        conn.commit()
        cur.close()
        conn.close()
    if dept in LAB_DATA:
        if "equipment_maintenance" not in LAB_DATA[dept]:
            LAB_DATA[dept]["equipment_maintenance"] = {}
        if chamber_name not in LAB_DATA[dept]["equipment_maintenance"]:
            LAB_DATA[dept]["equipment_maintenance"][chamber_name] = {}
       
        LAB_DATA[dept]["equipment_maintenance"][chamber_name]["last_check"] = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "submitted_by": data.get('submitted_by'),
            "shift": data.get('shift'),
            "checks": data.get('checks_data', {})
        }
        log_audit_event(dept, "Chamber Check Logged", f"Daily maintenance check completed for {chamber_name}.", data.get('submitted_by'))
        save_data_permanently()
    return jsonify({"status": "success", "message": f"Daily Check Sheet for {chamber_name} recorded!"})

@app.route('/api/equipment', methods=['POST'])
def update_equipment():
    data = request.json or {}
    chamber_name = data.get('equipment_name')
    dept = data.get('dept', 'Battery Lab')
    pm_date = data.get('pm_date')
    calib_date = data.get('calibration_due_date')
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO equipment_master (equipment_name, pm_date, calibration_due_date)
            VALUES (%s, %s, %s)
            ON CONFLICT (equipment_name)
            DO UPDATE SET
                pm_date = EXCLUDED.pm_date,
                calibration_due_date = EXCLUDED.calibration_due_date;
        ''', (
            chamber_name,
            pm_date or None,
            calib_date or None
        ))
        conn.commit()
        cur.close()
        conn.close()
    if dept in LAB_DATA:
        if "equipment_maintenance" not in LAB_DATA[dept]:
            LAB_DATA[dept]["equipment_maintenance"] = {}
        if chamber_name not in LAB_DATA[dept]["equipment_maintenance"]:
            LAB_DATA[dept]["equipment_maintenance"][chamber_name] = {}
       
        if pm_date:
            LAB_DATA[dept]["equipment_maintenance"][chamber_name]["pm_date"] = pm_date
        if calib_date:
            LAB_DATA[dept]["equipment_maintenance"][chamber_name]["calibration_due_date"] = calib_date
       
        log_audit_event(dept, "Equipment PM/Calib Updated", f"Updated PM ({pm_date}) & Calibration ({calib_date}) dates for {chamber_name}.")
        save_data_permanently()
    return jsonify({"status": "success", "message": f"PM & Calibration dates updated for {chamber_name}!"})

@app.route('/api/download-backup', methods=['GET'])
def download_backup():
    buffer = io.BytesIO()
    buffer.write(json.dumps(LAB_DATA, indent=4).encode('utf-8'))
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype='application/json',
        as_attachment=True,
        download_name=f'OptiLab_Full_Backup_{datetime.now().strftime("%Y%m%d_%H%M")}.json'
    )

@app.route('/api/export-excel', methods=['GET'])
def export_excel():
    conn = get_db_connection()
    output = io.BytesIO()
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if conn:
            df_5s = pd.read_sql_query(f"SELECT * FROM lab_fives_submissions WHERE submitted_at >= '{thirty_days_ago}' ORDER BY submitted_at DESC;", conn)
            df_chamber = pd.read_sql_query(f"SELECT * FROM chamber_daily_submissions WHERE submitted_at >= '{thirty_days_ago}' ORDER BY submitted_at DESC;", conn)
            df_equip = pd.read_sql_query("SELECT * FROM equipment_master ORDER BY equipment_name ASC;", conn)
            conn.close()
        else:
            df_5s = pd.DataFrame([{"info": "30-Day Logs stored in cloud session"}])
            df_chamber = pd.DataFrame([{"info": "30-Day Logs stored in cloud session"}])
            df_equip = pd.DataFrame([{"info": "30-Day Logs stored in cloud session"}])
           
        df_chamber.to_excel(writer, sheet_name='30-Day Chamber Daily Logs', index=False)
        df_5s.to_excel(writer, sheet_name='30-Day Lab 5S Logs', index=False)
        df_equip.to_excel(writer, sheet_name='Equipment PM & Calib Dates', index=False)
   
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='OptiLab_30Day_Checksheet_Logs.xlsx'
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)