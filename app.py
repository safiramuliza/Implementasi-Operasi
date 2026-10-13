from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import io
import base64
import csv
from matplotlib.figure import Figure
from matplotlib_venn import venn2, venn3

app = Flask(__name__)
app.secret_key = "logicforge-pjbl2"

DB = "logicforge.db"

CATEGORIES = {
    "A": "Mahasiswa Informatika",
    "B": "Mahasiswa Semester 3",
    "C": "Mahasiswa Laki-laki",
    "D": "Mahasiswa Aktif",
}

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mahasiswa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nim TEXT UNIQUE NOT NULL,
            nama TEXT NOT NULL,
            prodi TEXT NOT NULL,
            semester INTEGER NOT NULL,
            jk TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def get_students():
    conn = get_db()
    rows = conn.execute("SELECT * FROM mahasiswa ORDER BY nim").fetchall()
    conn.close()
    return rows

def student_sets(rows):
    by_name = {row["nama"]: row for row in rows}
    U = set(by_name.keys())
    A = {r["nama"] for r in rows if r["prodi"].strip().lower() == "informatika"}
    B = {r["nama"] for r in rows if int(r["semester"]) == 3}
    C = {r["nama"] for r in rows if r["jk"].strip().upper() == "L"}
    D = {r["nama"] for r in rows if r["status"].strip().lower() == "aktif"}
    return {"U": U, "A": A, "B": B, "C": C, "D": D}

def venn_image(sets, labels):
    fig = Figure(figsize=(7, 5), dpi=110)
    ax = fig.subplots()
    if len(sets) == 2:
        venn2(sets, set_labels=labels, ax=ax)
    else:
        venn3(sets, set_labels=labels, ax=ax)
    ax.set_title("Diagram Venn Hasil Klasifikasi")
    fig.tight_layout()
    output = io.BytesIO()
    fig.savefig(output, format="png", bbox_inches="tight")
    output.seek(0)
    return base64.b64encode(output.read()).decode("utf-8")

def parse_category(name):
    return CATEGORIES.get(name, name)

def perform_operation(sets, op, x, y=None):
    if x not in sets:
        raise ValueError("Himpunan pertama tidak ditemukan.")
    if op == "union":
        return sets[x] | sets[y]
    if op == "intersection":
        return sets[x] & sets[y]
    if op == "difference":
        return sets[x] - sets[y]
    if op == "complement":
        return sets["U"] - sets[x]
    raise ValueError("Operasi tidak dikenal.")

def inclusion_exclusion(sets, selected):
    selected = [s for s in selected if s in sets and s != "U"]
    if len(selected) == 2:
        a, b = selected
        return len(sets[a]) + len(sets[b]) - len(sets[a] & sets[b])
    if len(selected) == 3:
        a, b, c = selected
        return (
            len(sets[a]) + len(sets[b]) + len(sets[c])
            - len(sets[a] & sets[b])
            - len(sets[a] & sets[c])
            - len(sets[b] & sets[c])
            + len(sets[a] & sets[b] & sets[c])
        )
    return 0

def load_csv(file):
    decoded = file.read().decode("utf-8-sig").splitlines()
    reader = csv.DictReader(decoded)
    required = {"nim", "nama", "prodi", "semester", "jk", "status"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise ValueError("Kolom CSV harus: nim,nama,prodi,semester,jk,status")
    rows = []
    for r in reader:
        rows.append((
            r["nim"].strip(), r["nama"].strip(), r["prodi"].strip(),
            int(r["semester"]), r["jk"].strip(), r["status"].strip()
        ))
    return rows

@app.route("/")
def index():
    rows = get_students()
    sets = student_sets(rows)
    return render_template("index.html", students=rows, sets=sets, categories=CATEGORIES)

@app.route("/add", methods=["POST"])
def add():
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO mahasiswa (nim,nama,prodi,semester,jk,status) VALUES (?,?,?,?,?,?)",
            (request.form["nim"], request.form["nama"], request.form["prodi"],
             int(request.form["semester"]), request.form["jk"], request.form["status"])
        )
        conn.commit()
        conn.close()
        flash("Data mahasiswa berhasil ditambahkan.", "success")
    except sqlite3.IntegrityError:
        flash("NIM sudah digunakan.", "error")
    except Exception as e:
        flash(f"Gagal menambahkan data: {e}", "error")
    return redirect(url_for("index"))

@app.route("/delete/<int:student_id>", methods=["POST"])
def delete(student_id):
    conn = get_db()
    conn.execute("DELETE FROM mahasiswa WHERE id=?", (student_id,))
    conn.commit()
    conn.close()
    flash("Data berhasil dihapus.", "success")
    return redirect(url_for("index"))

@app.route("/seed/<int:number>")
def seed(number):
    datasets = {
        1: [
            ("001","Andi","Informatika",3,"L","Aktif"),
            ("002","Budi","Sistem Informasi",3,"L","Aktif"),
            ("003","Citra","Informatika",2,"P","Aktif"),
            ("004","Dinda","Sistem Informasi",2,"P","Aktif"),
            ("005","Eko","Informatika",3,"L","Aktif"),
        ],
        2: [
            ("101","Rina","Informatika",4,"P","Aktif"),
            ("102","Sinta","Informatika",3,"P","Tidak Aktif"),
            ("103","Tono","Sistem Informasi",3,"L","Aktif"),
            ("104","Udin","Informatika",3,"L","Aktif"),
            ("105","Vina","Sistem Informasi",2,"P","Aktif"),
            ("106","Wahyu","Informatika",2,"L","Tidak Aktif"),
            ("107","Yani","Informatika",3,"P","Aktif"),
            ("108","Zaki","Sistem Informasi",4,"L","Aktif"),
        ]
    }
    conn = get_db()
    conn.execute("DELETE FROM mahasiswa")
    conn.executemany(
        "INSERT INTO mahasiswa (nim,nama,prodi,semester,jk,status) VALUES (?,?,?,?,?,?)",
        datasets[number]
    )
    conn.commit()
    conn.close()
    flash(f"Dataset contoh {number} berhasil dimuat.", "success")
    return redirect(url_for("index"))

@app.route("/operation", methods=["POST"])
def operation():
    rows = get_students()
    sets = student_sets(rows)
    op = request.form["operation"]
    x = request.form["x"]
    y = request.form.get("y")
    try:
        result = perform_operation(sets, op, x, y)
        label = {
            "union": f"{x} ∪ {y}",
            "intersection": f"{x} ∩ {y}",
            "difference": f"{x} − {y}",
            "complement": f"{x}ᶜ"
        }[op]
        venn = None
        selected = [x] + ([y] if y else [])
        if len(selected) == 2:
            venn = venn_image([sets[x], sets[y]], [x, y])
        elif len(selected) == 3:
            venn = venn_image([sets[x], sets[y], sets.get(request.form.get("z"), set())],
                               [x, y, request.form.get("z")])
        return render_template(
            "result.html", students=rows, sets=sets, categories=CATEGORIES,
            result=sorted(result), operation=label, venn=venn,
            pie_value=None, pie_selected=[]
        )
    except Exception as e:
        flash(f"Operasi gagal: {e}", "error")
        return redirect(url_for("index"))

@app.route("/pie", methods=["POST"])
def pie():
    rows = get_students()
    sets = student_sets(rows)
    selected = request.form.getlist("sets")
    value = inclusion_exclusion(sets, selected)
    venn = None
    if len(selected) == 2:
        venn = venn_image([sets[selected[0]], sets[selected[1]]], selected)
    elif len(selected) == 3:
        venn = venn_image([sets[selected[0]], sets[selected[1]], sets[selected[2]]], selected)
    return render_template(
        "result.html", students=rows, sets=sets, categories=CATEGORIES,
        result=sorted(set().union(*(sets[s] for s in selected))) if selected else [],
        operation="Prinsip Inklusi-Eksklusi",
        venn=venn, pie_value=value, pie_selected=selected
    )

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file or not file.filename.lower().endswith(".csv"):
        flash("Pilih file CSV.", "error")
        return redirect(url_for("index"))
    try:
        rows = load_csv(file)
        conn = get_db()
        conn.execute("DELETE FROM mahasiswa")
        conn.executemany(
            "INSERT INTO mahasiswa (nim,nama,prodi,semester,jk,status) VALUES (?,?,?,?,?,?)",
            rows
        )
        conn.commit()
        conn.close()
        flash("Dataset CSV berhasil diimpor.", "success")
    except Exception as e:
        flash(f"Gagal mengimpor CSV: {e}", "error")
    return redirect(url_for("index"))

init_db()

if __name__ == "__main__":
    app.run(debug=False)
