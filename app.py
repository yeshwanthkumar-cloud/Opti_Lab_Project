import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, jsonify, request
from datetime import datetime

app = Flask(__name__)

# Check for Render PostgreSQL Database URL
DATABASE_URL = os.environ.get('DATABASE_URL')
DATA_FILE = "data.json"

DEPARTMENTS = ["Battery Lab", "Cell Lab", "Vibration Team", "E&E Lab"]

DIGITAL_TWINS = {
    "Battery Lab": {
        "title": "Battery Lab View — Environmental Chambers & Charge/Discharge Cyclers",
        "top_row": [
            {"id": "Chamber-1", "name": "Chamber 1", "type": "chamber", "img": "/static/images/chamber.png"},
            {"id": "Chamber-2", "name": "Chamber 2", "type": "chamber", "img": "/static/images/chamber.png"},
            {"id": "Chamber-3", "name": "Chamber 3", "type": "chamber", "img": "/static/images/chamber.png"},
            {"id": "Chamber-4", "name": "Chamber 4", "type": "chamber", "img": "/static/images/chamber.png"},
            {"id": "Chamber-5", "name": "Chamber 5", "type": "chamber", "img": "/static/images/chamber.png"},
            {"id": "Chamber-6", "name": "Chamber 6", "type": "chamber", "img": "/static/images/chamber.png"},
            {"id": "Chamber-7", "name": "Chamber 7", "type": "chamber", "img": "/static/images/chamber.png"},
            {"id": "Chamber-8", "name": "Chamber 8", "type": "chamber", "img": "/static/images/chamber.png"}
        ],
        "bottom_row": [
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
    },
    "Cell Lab": {
        "title": "Cell Lab View — Channel Rig Array",
        "top_row": [
            {"id": "Cell-Bench-1", "name": "Pouch Cell Rig A", "type": "chamber", "img": "/static/images/chamber.png"},
            {"id": "Cell-Bench-2", "name": "Prismatic Rig 1", "type": "chamber", "img": "/static/images/chamber.png"},
            {"id": "Cell-Bench-3", "name": "Prismatic Rig 2", "type": "chamber", "img": "/static/images/chamber.png"}
        ],
        "bottom_row": []
    },
    "Vibration Team": {
        "title": "Vibration Team Lab View — High-Capacity Shakers",
        "top_row": [
            {"id": "Shaker-1.5T", "name": "1.5-Ton Tri-Axial Shaker", "type": "chamber", "img": "/static/images/shaker.png"},
            {"id": "Shaker-3T", "name": "3.0-Ton Tri-Axial Shaker", "type": "chamber", "img": "/static/images/shaker.png"},
            {"id": "Shaker-SDYN", "name": "SDYN Shaker Rig", "type": "chamber", "img": "/static/images/shaker.png"}
        ],
        "bottom_row": []
    },
    "E&E Lab": {
        "title": "E&E Lab View — Controller Simulators",
        "top_row": [
            {"id": "EE-MCU-Bench", "name": "MCU Bench Station", "type": "chamber", "img": "/static/images/chamber.png"},
            {"id": "EE-VCU-Bench", "name": "VCU Simulator Rig", "type": "chamber", "img": "/static/images/chamber.png"},
            {"id": "EE-BMS-Tester", "name": "BMS HIL Station", "type": "chamber", "img": "/static/images/chamber.png"}
        ],
        "bottom_row": []
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
        "roster_stamps": {}
    } for dept in DEPARTMENTS
}

# ==============================================================================
# DATABASE OR LOCAL PERSISTENCE SWITCHER
# ==============================================================================

def init_db():
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS opti_lab_store (
                    id VARCHAR(50) PRIMARY KEY,
                    data JSONB NOT NULL
                );
            """)
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print("Database initialization error:", e)

def save_data_to_file():
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO opti_lab_store (id, data) 
                VALUES ('master', %s) 
                ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data;
            """, (json.dumps(LAB_DATA),))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print("DB Save Error:", e)
    else:
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(LAB_DATA, f, indent=4)
        except Exception as e:
            print("Error saving local file:", e)

def load_data_from_file():
    global LAB_DATA
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT data FROM opti_lab_store WHERE id = 'master';")
            row = cursor.fetchone()
            if row and row.get('data'):
                saved_data = row['data']
                for dept in DEPARTMENTS:
                    if dept in saved_data:
                        LAB_DATA[dept] = saved_data[dept]
            cursor.close()
            conn.close()
        except Exception as e:
            print("DB Load Error:", e)
    else:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    saved_data = json.load(f)
                    for dept in DEPARTMENTS:
                        if dept in saved_data:
                            LAB_DATA[dept] = saved_data[dept]
            except Exception as e:
                print("Error loading local file:", e)

init_db()
load_data_from_file()

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
    
    cat_counts = {
        "450": {"running": 0, "complete": 0},
        "DIESEL": {"running": 0, "complete": 0},
        "EL": {"running": 0, "complete": 0}
    }

    stoppage_breakdown = {"no_parts": 0, "chamber_down": 0, "fixture_adjust": 0}
    shift_completion = {"Shift A": {"completed": 0, "assigned": 0}, "Shift B": {"completed": 0, "assigned": 0}, "Shift C": {"completed": 0, "assigned": 0}}
    incharge_stats = {}
    associate_stats = {}

    for t in tasks:
        cat = t.get("category", "450")
        if cat not in cat_counts:
            cat_counts[cat] = {"running": 0, "complete": 0}
            
        if t["status"] in ["Completed", "Awaiting Report"]:
            total_complete += 1
            cat_counts[cat]["complete"] += 1
        elif t["status"] == "Running":
            total_running += 1
            cat_counts[cat]["running"] += 1
        elif t["status"] in ["Blocked", "Parts Missing"]:
            total_awaiting_res += 1
        else:
            total_awaiting_eng += 1

        for st in t["subtasks"]:
            shift = st.get("shift", "None")
            if shift in shift_completion:
                shift_completion[shift]["assigned"] += 1
                if st["status"] == "Completed":
                    shift_completion[shift]["completed"] += 1

            inc = st.get("incharge", "Unassigned")
            if inc != "Unassigned":
                if inc not in incharge_stats:
                    incharge_stats[inc] = {"completed": 0, "managed": 0}
                incharge_stats[inc]["managed"] += 1
                if st["status"] == "Completed":
                    incharge_stats[inc]["completed"] += 1

            assoc = st.get("associate", "Unassigned")
            if assoc != "Unassigned":
                if assoc not in associate_stats:
                    associate_stats[assoc] = {"completed": 0, "assigned": 0}
                associate_stats[assoc]["assigned"] += 1
                if st["status"] == "Completed":
                    associate_stats[assoc]["completed"] += 1

            if st["status"] == "Parts Missing":
                stoppage_breakdown["no_parts"] += 1
            elif st["status"] == "Blocked":
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

# ==============================================================================
# API ROUTES
# ==============================================================================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/lab/<dept_name>")
def get_lab_data(dept_name):
    dept = dept_name if dept_name in LAB_DATA else "Battery Lab"
    tasks = LAB_DATA[dept]["tasks"]
    metrics = calculate_dashboard_metrics(tasks)
    dept_components = list(dict.fromkeys(LAB_DATA[dept]["components"]))
    
    return jsonify({
        "dept": dept,
        "components": dept_components,
        "blueprints": LAB_DATA[dept]["blueprints"],
        "personnel": LAB_DATA[dept]["personnel"],
        "tasks": tasks,
        "attendance": LAB_DATA[dept]["attendance"],
        "extra_tasks": LAB_DATA[dept]["extra_tasks"],
        "audit_history": LAB_DATA[dept]["audit_history"],
        "metrics": metrics,
        "twin": DIGITAL_TWINS.get(dept, DIGITAL_TWINS["Battery Lab"])
    })

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
            save_data_to_file()
            return jsonify({"success": True})
            
    return jsonify({"success": False, "message": "Task not found"}), 400

@app.route("/api/lab/reset", methods=["POST"])
def reset_all_lab_data():
    global LAB_DATA
    LAB_DATA = {
        dept: {
            "components": [],
            "blueprints": {},
            "personnel": [],
            "tasks": [],
            "attendance": [],
            "extra_tasks": [],
            "audit_history": [],
            "roster_stamps": {}
        } for dept in DEPARTMENTS
    }
    save_data_to_file()
    return jsonify({"success": True})

@app.route("/api/blueprints/save", methods=["POST"])
def save_blueprint():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
    name = data.get("name")
    steps = data.get("steps", [])
    if dept in LAB_DATA and name and steps:
        LAB_DATA[dept]["blueprints"][name] = steps
        log_audit_event(dept, "Flow Blueprint Saved", f"Saved reusable test flow: {name} with {len(steps)} steps.")
        save_data_to_file()
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
            save_data_to_file()
            return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route("/api/tasks/create", methods=["POST"])
def create_master_task():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
    
    if dept in LAB_DATA:
        task_id = f"TSK-{len(LAB_DATA[dept]['tasks']) + 400001}"
        steps = data.get("steps", [])
        
        subtasks = []
        for idx, s in enumerate(steps):
            subtasks.append({
                "sub_id": f"SUB-{idx+700001}",
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
                "chamber": "Chamber-1",
                "cycler": "None",
                "neware_channel": "",
                "grafana": "",
                "observations": []
            })
            
        new_task = {
            "task_id": task_id,
            "prio": data.get("prio", "P1"),
            "bin": data.get("bin", ""),
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
        log_audit_event(dept, "Master Task Created", f"Task {task_id} ({data.get('bin')}) generated with {len(subtasks)} steps.", data.get('engineer', 'Lead Engineer'))
        save_data_to_file()
        return jsonify({"success": True, "task": new_task})
    return jsonify({"success": False}), 400

@app.route("/api/subtasks/update", methods=["POST"])
def update_subtask():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
    task_id = data.get("task_id")
    sub_id = data.get("sub_id")
    
    if dept in LAB_DATA:
        for t in LAB_DATA[dept]["tasks"]:
            if t["task_id"] == task_id:
                for st in t["subtasks"]:
                    if st["sub_id"] == sub_id:
                        st["associate"] = data.get("associate", st["associate"])
                        st["incharge"] = data.get("incharge", st["incharge"])
                        st["shift"] = data.get("shift", st["shift"])
                        st["assign_date"] = data.get("assign_date", st["assign_date"])
                        
                        st["chamber"] = data.get("chamber", st.get("chamber", "Chamber-1"))
                        st["cycler"] = data.get("cycler", st.get("cycler", "None"))
                        st["neware_channel"] = data.get("neware_channel", st.get("neware_channel", ""))
                        st["grafana"] = data.get("grafana", st.get("grafana", ""))
                        
                        add_p = float(data.get("add_progress", 0))
                        st["logged"] += add_p
                        
                        status = data.get("status", st["status"])
                        st["status"] = status
                        
                        notes = data.get("notes", "").strip()
                        if notes:
                            st["observations"].append({
                                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "associate": st["associate"],
                                "shift": st["shift"],
                                "chamber": st["chamber"],
                                "cycler": st["cycler"],
                                "channel": st["neware_channel"],
                                "notes": notes
                            })
                            
                        if st["logged"] >= st["target"]:
                            st["status"] = "Completed"
                            
                        total_target = sum(s["target"] for s in t["subtasks"])
                        total_logged = sum(s["logged"] for s in t["subtasks"])
                        t["progress"] = int((total_logged / total_target) * 100) if total_target > 0 else 0
                        if all(s["status"] == "Completed" for s in t["subtasks"]):
                            t["status"] = "Completed"
                            
                        log_audit_event(dept, "Subtask Progress Logged", f"{sub_id} on {t['task_id']} updated (+{add_p} {st['unit']}). Status: {status}. Equipment: {st['chamber']} & {st['cycler']} (Ch: {st['neware_channel']}).", st["associate"])
                        save_data_to_file()
                        return jsonify({"success": True, "subtask": st, "task_progress": t["progress"]})
    return jsonify({"success": False}), 400

@app.route("/api/personnel/add", methods=["POST"])
def add_personnel():
    data = request.json or {}
    dept = data.get("dept", "Battery Lab")
    if dept in LAB_DATA:
        schedule = [data.get("shift", "Shift A")] * 30
        new_member = {
            "id": data.get("emp_id", f"EMP-{len(LAB_DATA[dept]['personnel']) + 101}"),
            "name": data.get("name"),
            "role": data.get("role", "Associate"),
            "shift": data.get("shift", "Shift A"),
            "schedule": schedule
        }
        LAB_DATA[dept]["personnel"].append(new_member)
        log_audit_event(dept, "Personnel Added", f"Registered {data.get('name')} ({data.get('role')}) to {data.get('shift')}.")
        save_data_to_file()
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
        save_data_to_file()
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
                save_data_to_file()
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
        save_data_to_file()
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
        save_data_to_file()
        return jsonify({"success": True, "extra": extra})
    return jsonify({"success": False}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
    # =========================================================
# NEW FEATURES: CHECKSHEETS & EXCEL EXPORT
# =========================================================
import io
import pandas as pd

def init_checksheet_tables():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS master_shift_submissions (
                id SERIAL PRIMARY KEY,
                shift VARCHAR(20),
                equipment_name VARCHAR(100),
                submitted_by VARCHAR(100),
                fives_data JSONB,
                tools_data JSONB,
                chamber_checklist JSONB,
                status VARCHAR(20) DEFAULT 'Pass',
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("Checksheet Table Init Error:", e)

init_checksheet_tables()

@app.route('/api/master-shift-submit', methods=['POST'])
def submit_master_shift():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO master_shift_submissions 
        (shift, equipment_name, submitted_by, fives_data, tools_data, chamber_checklist, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s);
    ''', (
        data['shift'],
        data['equipment_name'],
        data['submitted_by'],
        psycopg2.extras.Json(data['fives']),
        psycopg2.extras.Json(data['tools']),
        psycopg2.extras.Json(data['chamber_checks']),
        data.get('status', 'Pass')
    ))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "success", "message": f"{data['shift']} submission recorded!"})

@app.route('/api/export-excel', methods=['GET'])
def export_excel():
    conn = get_db_connection()
    df = pd.read_sql_query('SELECT * FROM master_shift_submissions ORDER BY submitted_at DESC;', conn)
    conn.close()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Shift Checksheet Logs', index=False)
    
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='OptiLab_Master_Shift_Checksheets.xlsx'
    )