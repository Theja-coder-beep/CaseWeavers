import streamlit as st

import sqlite3

import fitz

import hashlib

import hmac

import secrets

import re
from datetime import datetime

from agents.evidence_agent import analyze_evidence

from agents.connection_agent import find_connections

from agents.orchestrator import run_investigation



st.set_page_config(page_title="CaseWeaver | Investigation Intelligence", page_icon="🔎", layout="wide")

DB_NAME = "caseweaver.db"



# ---------------- DATABASE ----------------

def get_connection():

    db = sqlite3.connect(DB_NAME)

    db.execute("PRAGMA foreign_keys = ON")

    return db



def hash_password(password, salt=None):

    salt = salt or secrets.token_hex(16)

    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200000).hex()

    return salt, digest



def verify_password(password, salt, stored_hash):

    _, candidate = hash_password(password, salt)

    return hmac.compare_digest(candidate, stored_hash)



def setup_database():

    db = get_connection()

    cur = db.cursor()

    cur.execute("CREATE TABLE IF NOT EXISTS cases (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT)")

    cur.execute("CREATE TABLE IF NOT EXISTS evidence (id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER, filename TEXT, content TEXT, FOREIGN KEY(case_id) REFERENCES cases(id))")

    cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL)")

    # Add owner_id to older case databases without deleting existing records.

    columns = [row[1] for row in cur.execute("PRAGMA table_info(cases)").fetchall()]

    if "owner_id" not in columns:

        cur.execute("ALTER TABLE cases ADD COLUMN owner_id INTEGER")

    # Demo-only CBI account. Replace credentials and implement real identity verification before any real deployment.

    cur.execute("SELECT id FROM users WHERE username = ?", ("cbi_demo",))

    if not cur.fetchone():

        salt, digest = hash_password("CaseWeaver@2026")

        cur.execute("INSERT INTO users(username, salt, password_hash, role) VALUES (?, ?, ?, ?)", ("cbi_demo", salt, digest, "CBI Official (Demo)"))

    db.commit()

    db.close()



setup_database()



def create_user(username, password):

    salt, digest = hash_password(password)

    db = get_connection()

    try:

        db.execute("INSERT INTO users(username, salt, password_hash, role) VALUES (?, ?, ?, 'Normal User')", (username, salt, digest))

        db.commit()

        return True, "Account created. You can now log in."

    except sqlite3.IntegrityError:

        return False, "That username already exists. Please choose another."

    finally:

        db.close()



def authenticate(username, password):

    db = get_connection()

    row = db.execute("SELECT id, username, salt, password_hash, role FROM users WHERE username = ?", (username,)).fetchone()

    db.close()

    if row and verify_password(password, row[2], row[3]):

        return {"id": row[0], "username": row[1], "role": row[4]}

    return None



def get_cases(user):

    db = get_connection()

    if user["role"].startswith("CBI Official"):

        rows = db.execute("SELECT id, name, description FROM cases ORDER BY id DESC").fetchall()

    else:

        rows = db.execute("SELECT id, name, description FROM cases WHERE owner_id = ? OR owner_id IS NULL ORDER BY id DESC", (user["id"],)).fetchall()

    db.close()

    return rows



def get_evidence(case_id):

    db = get_connection()

    rows = db.execute("SELECT id, filename, content FROM evidence WHERE case_id = ? ORDER BY id", (case_id,)).fetchall()

    db.close()

    # Analyse only one copy of an identical file/content pair; database records are preserved.

    unique = {}

    for row in rows:

        key = (row[1].strip().casefold(), hashlib.sha256((row[2] or "").encode("utf-8")).hexdigest())

        if key not in unique:

            unique[key] = {"id": row[0], "filename": row[1], "content": row[2]}

    return list(unique.values()), len(rows) - len(unique)





# ---------------- SIMPLE OFFLINE ENTITY EXTRACTION ----------------

def extract_graph_entities(text):

    """Extract transparent, rule-based entities for the demo knowledge graph."""

    found = []

    lower = text.lower()



    # Times

    for value in re.findall(r"\b\d{1,2}(?::\d{2})?\s?(?:AM|PM)\b", text, flags=re.I):

        found.append(("TIME", value.upper()))



    # Locations: deliberately limited to explicit location terms in the demo data.

    location_terms = [

        "laboratory", "lab", "laboratory building", "laboratory room",

        "office", "campus", "library", "security room"

    ]

    for term in location_terms:

        if re.search(r"\b" + re.escape(term) + r"\b", lower):

            found.append(("LOCATION", term.title()))



    # People / roles. These are descriptions, not identity claims.

    person_patterns = [

        (r"unidentified person", "Unidentified person"),

        (r"unidentified individual", "Unidentified individual"),

        (r"\bindividual\b", "Individual (identity unknown)"),

        (r"\bwitness\b", "Witness (name not established)"),

        (r"staff member", "Staff member (name not established)"),

        (r"laboratory assistant", "Laboratory assistant (name not established)"),

        (r"security personnel", "Security personnel (name not established)"),

    ]

    for pattern, label in person_patterns:

        if re.search(pattern, lower):

            found.append(("PERSON / ROLE", label))



    # Objects explicitly mentioned in the sample case.

    object_terms = ["prototype", "black bag", "bag", "jacket", "blue jacket", "keycard", "access card"]

    for term in object_terms:

        if re.search(r"\b" + re.escape(term) + r"\b", lower):

            found.append(("OBJECT", term.title()))



    # Events: retain the source sentence so the graph can be traced to the document.

    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)

    event_verbs = ["entered", "leaving", "left", "arrived", "departed", "carrying", "saw", "seen", "missing", "reported", "observed", "noticed"]

    for sentence in sentences:

        clean = " ".join(sentence.split()).strip(" .;:-")

        if clean and any(re.search(r"\b" + re.escape(v) + r"\b", clean, flags=re.I) for v in event_verbs):

            found.append(("EVENT", clean[:105] + ("…" if len(clean) > 105 else "")))



    # Remove duplicates while preserving order.

    unique = []

    seen = set()

    for category, label in found:

        key = (category, label.casefold())

        if key not in seen:

            seen.add(key)

            unique.append((category, label))

    return unique




def extract_timeline_events(documents):
    """Extract reported time-stamped sentences and retain their source document."""
    events = []
    for doc in documents:
        content = doc.get("content", "")
        date_match = re.search(
            r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b", content
        )
        parsed_date = None
        date_label = "Date not specified"
        if date_match:
            date_label = date_match.group(1)
            for fmt in ("%d %B %Y", "%d %b %Y"):
                try:
                    parsed_date = datetime.strptime(date_label, fmt).date()
                    break
                except ValueError:
                    pass

        sentences = re.split(r"(?<=[.!?])\s+|\n+", content)
        for sentence in sentences:
            clean = " ".join(sentence.split()).strip(" .;:-")
            time_match = re.search(
                r"\b(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\b",
                clean,
                flags=re.I
            )
            if not clean or not time_match:
                continue
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            meridiem = time_match.group(3).upper()
            if hour < 1 or hour > 12 or minute > 59:
                continue
            hour24 = hour % 12 + (12 if meridiem == "PM" else 0)
            sort_time = (hour24, minute)
            events.append({
                "date": date_label,
                "parsed_date": parsed_date,
                "time": time_match.group(0).upper(),
                "sort_time": sort_time,
                "description": clean,
                "source": doc.get("filename", "Unknown source")
            })

    events.sort(key=lambda item: (
        item["parsed_date"] is None,
        item["parsed_date"] or datetime.max.date(),
        item["sort_time"]
    ))
    return events


def dot_escape(value):

    return str(value).replace("\\\\", "\\\\\\\\").replace('"', '\\\\"').replace("\n", " ")



# ---------------- DESIGN ----------------

st.markdown("""<style>

.stApp{background:linear-gradient(135deg,#071321,#0b1b2d 55%,#10243a);color:#e8eef5}

[data-testid="stSidebar"]{background:#071321;border-right:1px solid #263c52}

.block-container{padding-top:2rem;max-width:1250px}

.cw-brand{font-size:27px;font-weight:800;letter-spacing:2px;color:#55D6D0}

.cw-subtitle{font-size:10px;letter-spacing:2px;color:#8CA6B9;margin-top:5px}

.cw-panel{background:#11263b;border:1px solid #29465e;padding:25px;border-radius:14px;margin-bottom:18px}

.cw-status{display:inline-block;background:#12352f;color:#68e0b5;border:1px solid #286b5b;padding:9px 15px;border-radius:20px;font-size:12px;letter-spacing:1px;margin-bottom:25px}

.cw-eyebrow{color:#55D6D0;font-size:12px;letter-spacing:3px;margin-bottom:18px}

.cw-heading{font-size:43px;line-height:1.25;font-weight:800;color:#F1F6FA;margin-bottom:20px}

.cw-highlight{color:#55D6D0}.cw-description{color:#AFC1D1;font-size:16px;line-height:1.8;max-width:750px}

.cw-card{background:#11263b;border:1px solid #29465e;padding:22px;border-radius:14px;min-height:125px}

.cw-card-title{color:#9db5c9;font-size:13px;margin-bottom:12px}.cw-card-number{font-size:30px;font-weight:800;color:#55D6D0}

.stButton>button{background:#12AFA8;color:white;border:0;border-radius:8px;font-weight:600}

.stButton>button:hover{background:#0D8F8A;color:white}

</style>""", unsafe_allow_html=True)



# ---------------- AUTHENTICATION ----------------

if "user" not in st.session_state:

    st.session_state.user = None



if st.session_state.user is None:

    st.markdown('<div class="cw-brand">CASEWEAVER</div><div class="cw-subtitle">INVESTIGATIVE INTELLIGENCE PLATFORM</div>', unsafe_allow_html=True)

    st.markdown("## Secure sign in")

    st.caption("Hackathon demonstration login. CBI role is simulated and is not official identity verification.")

    login_tab, signup_tab = st.tabs(["Login", "Create normal-user account"])

    with login_tab:

        with st.form("login_form"):

            username = st.text_input("Username")

            password = st.text_input("Password", type="password")

            submitted = st.form_submit_button("Sign in", use_container_width=True)

        if submitted:

            user = authenticate(username.strip(), password)

            if user:

                st.session_state.user = user

                st.rerun()

            else:

                st.error("Invalid username or password.")

        with st.expander("Demo CBI account (for presentation only)"):

            st.write("Username: `cbi_demo`")

            st.write("Password: `CaseWeaver@2026`")

            st.warning("Change this demo password and add real identity verification before any real-world use.")

    with signup_tab:

        with st.form("signup_form"):

            new_username = st.text_input("Choose username")

            new_password = st.text_input("Choose password", type="password")

            confirm_password = st.text_input("Confirm password", type="password")

            create = st.form_submit_button("Create account", use_container_width=True)

        if create:

            if len(new_username.strip()) < 3:

                st.error("Username must contain at least 3 characters.")

            elif len(new_password) < 8:

                st.error("Use a password with at least 8 characters.")

            elif new_password != confirm_password:

                st.error("Passwords do not match.")

            else:

                ok, message = create_user(new_username.strip(), new_password)

                (st.success if ok else st.error)(message)

    st.stop()



user = st.session_state.user



# ---------------- SIDEBAR ----------------

with st.sidebar:

    st.markdown('<div class="cw-brand">CASEWEAVER</div><div class="cw-subtitle">INVESTIGATIVE INTELLIGENCE</div>', unsafe_allow_html=True)

    st.markdown("---")

    st.write("Signed in as")

    st.markdown(f"**{user['username']}**")

    st.caption(user["role"])

    if st.button("Log out", use_container_width=True):

        st.session_state.user = None

        st.session_state.pop("investigation_result", None)

        st.rerun()

    st.markdown("---")

    pages = ["Dashboard", "Create Investigation", "Evidence Explorer", "Investigation Report"]

    if user["role"].startswith("CBI Official"):

        pages.append("User & Access Information")

    page = st.radio("NAVIGATION", pages)

    st.markdown("---")

    st.caption("CASEWEAVER v2.0 · LOCAL DEMO")



# ---------------- DASHBOARD ----------------

if page == "Dashboard":

    cases = get_cases(user)

    db = get_connection()

    evidence_count = db.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]

    db.close()

    st.html("""<div class="cw-panel"><div class="cw-status">● SYSTEM READY · LOCAL PROCESSING</div><div class="cw-eyebrow">INTELLIGENCE BEYOND THE EVIDENCE</div><div class="cw-heading">Every clue has a story.<br><span class="cw-highlight">Every connection matters.</span></div><div class="cw-description">Transform disconnected evidence into structured investigative insights. Explore relationships, review possible inconsistencies and identify questions that need human attention.</div></div>""")

    c1,c2,c3=st.columns(3)

    for col,label,value in [(c1,"YOUR INVESTIGATIONS",len(cases)),(c2,"EVIDENCE FILE RECORDS",evidence_count),(c3,"PROCESSING MODE","OFFLINE")]:

        with col: st.html(f'<div class="cw-card"><div class="cw-card-title">{label}</div><div class="cw-card-number">{value}</div></div>')

    st.markdown("### Responsible investigation")

    st.info("CaseWeaver produces preliminary, source-dependent leads. It does not establish guilt, innocence, or the truth of a statement.")



# ---------------- CREATE CASE ----------------

elif page == "Create Investigation":

    st.title("Create Investigation")

    with st.form("create_case"):

        name=st.text_input("Investigation name")

        description=st.text_area("Description")

        submit=st.form_submit_button("Create investigation")

    if submit:

        if not name.strip(): st.error("Enter an investigation name.")

        else:

            db=get_connection(); db.execute("INSERT INTO cases(name,description,owner_id) VALUES(?,?,?)",(name.strip(),description,user["id"])); db.commit(); db.close(); st.success("Investigation created.")

    st.subheader("Available investigations")

    for case in get_cases(user): st.write(f"**{case[1]}** — {case[2] or 'No description'}")



# ---------------- EVIDENCE ----------------

elif page == "Evidence Explorer":

    st.title("Evidence Explorer")

    cases=get_cases(user)

    if not cases: st.info("Create an investigation first.")

    else:

        labels={f"{c[1]} (ID: {c[0]})":c[0] for c in cases}

        selected=st.selectbox("Select investigation",list(labels))

        case_id=labels[selected]

        uploads=st.file_uploader("Upload PDF or TXT evidence",type=["pdf","txt"],accept_multiple_files=True)

        if st.button("Save uploaded evidence"):

            if not uploads: st.warning("Choose at least one file.")

            else:

                db=get_connection(); added=0; skipped=0

                for f in uploads:

                    raw=f.read()

                    if f.name.lower().endswith(".pdf"):

                        pdf=fitz.open(stream=raw,filetype="pdf"); content="\n".join(p.get_text() for p in pdf); pdf.close()

                    else: content=raw.decode("utf-8",errors="replace")

                    exists=db.execute("SELECT id FROM evidence WHERE case_id=? AND lower(filename)=lower(?) AND content=? LIMIT 1",(case_id,f.name,content)).fetchone()

                    if exists: skipped+=1; continue

                    db.execute("INSERT INTO evidence(case_id,filename,content) VALUES(?,?,?)",(case_id,f.name,content)); added+=1

                db.commit(); db.close()

                st.success(f"Saved {added} new file(s). Skipped {skipped} exact duplicate upload(s).")

                st.rerun()

        documents, duplicate_count=get_evidence(case_id)

        st.subheader("Saved evidence")

        if duplicate_count: st.warning(f"{duplicate_count} duplicate record(s) are hidden from analysis. Existing database records have not been deleted.")

        for d in documents:

            with st.expander(d["filename"]):

                st.text(d["content"][:3000])

                findings=analyze_evidence(d["content"])

                st.markdown("**Extracted preliminary details**")

                for category,items in findings.items(): st.write(f"{category.title()}: {', '.join(map(str,items)) if items else 'Not identified'}")

        if documents:

            st.markdown("### Investigative knowledge graph")

            st.caption("Documents connect to extracted people, locations, times, objects and reported events. These are rule-based suggestions; verify each item against its source.")

            dot = [

                'graph CaseWeaver {',

                'graph [bgcolor="transparent", overlap=false, splines=true, ranksep="0.8", nodesep="0.35"];',

                'node [style="filled", fontcolor="white", fontname="Arial", fontsize=10, color="#55D6D0", penwidth=1.4];',

                'edge [color="#66869b", penwidth=1.2];'

            ]

            palette = {

                "DOCUMENT": "#16445b", "PERSON / ROLE": "#6b3f75",

                "LOCATION": "#246b62", "TIME": "#8a6428",

                "OBJECT": "#72502f", "EVENT": "#344f83"

            }

            entity_sources = {}

            document_nodes = []

            for i, doc in enumerate(documents):

                doc_id = f"doc_{i}"

                document_nodes.append(doc_id)

                dot.append(f'{doc_id} [label="{dot_escape(doc["filename"])}", shape=folder, fillcolor="{palette["DOCUMENT"]}"];')

                for category, label in extract_graph_entities(doc["content"]):

                    entity_key = (category, label.casefold())

                    entity_sources.setdefault(entity_key, {"label": label, "sources": []})

                    entity_sources[entity_key]["sources"].append(doc_id)

            for j, (key, data) in enumerate(entity_sources.items()):

                category, normalized = key

                entity_id = f"entity_{j}"

                shape = "ellipse" if category in ("PERSON / ROLE", "LOCATION") else "box"

                node_label = f"{category}\\\n{data['label']}"

                dot.append(f'{entity_id} [label="{dot_escape(node_label)}", shape={shape}, fillcolor="{palette[category]}"];')

                for doc_id in sorted(set(data["sources"])):

                    dot.append(f'{doc_id} -- {entity_id};')

            dot.append("}")

            if entity_sources:

                st.graphviz_chart("\n".join(dot), use_container_width=True)

                st.markdown("**Graph legend**")

                legend_cols = st.columns(3)

                legend_items = list(palette.items())

                for idx, (category, color) in enumerate(legend_items):

                    with legend_cols[idx % 3]:

                        st.markdown(f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{color};margin-right:7px"></span>{category}', unsafe_allow_html=True)

                with st.expander("View extracted entities and their source documents"):

                    for (category, normalized), data in entity_sources.items():

                        source_names = [documents[int(source.split("_")[1])]["filename"] for source in sorted(set(data["sources"]))]

                        st.write(f"**{category}: {data['label']}**")

                        st.caption("Source: " + "; ".join(source_names))

            else:

                st.info("No entities were extracted from these documents yet.")

            st.markdown("### Investigation timeline")
            st.caption(
                "Chronological view of sentences containing reported times. "
                "The timeline reflects what documents say; it does not verify when events actually occurred."
            )
            timeline_events = extract_timeline_events(documents)
            if timeline_events:
                filter_options = ["All evidence sources"] + sorted(
                    {event["source"] for event in timeline_events}
                )
                timeline_filter = st.selectbox(
                    "Filter timeline by source document",
                    filter_options,
                    key="timeline_source_filter"
                )
                visible_events = [
                    event for event in timeline_events
                    if timeline_filter == "All evidence sources"
                    or event["source"] == timeline_filter
                ]
                for index, event in enumerate(visible_events, start=1):
                    with st.container(border=True):
                        time_col, detail_col = st.columns([1, 5])
                        with time_col:
                            st.markdown(f"**{event['time']}**")
                            st.caption(event["date"])
                        with detail_col:
                            st.markdown(f"**{index}. {event['description']}**")
                            st.caption("Source document: " + event["source"])
            else:
                st.info(
                    "No sentences containing a recognisable AM/PM time were found. "
                    "Add time-stamped evidence to populate the timeline."
                )

            st.markdown("### Complete investigation")

            if st.button("Run complete investigation"):

                result=run_investigation(selected.split(" (ID:")[0],documents)

                st.session_state.investigation_result=result

                st.session_state.investigation_case=selected

                st.success("Analysis completed.")

            if "investigation_result" in st.session_state:

                result=st.session_state.investigation_result

                st.subheader("Potential discrepancies")

                if result["contradictions"]:

                    for item in result["contradictions"]: st.warning(f"{item['file1']} / {item['file2']}: {item['description']}")

                else: st.info("No potential discrepancies identified by the current rule-based checks.")

                st.subheader("Suggested follow-up questions")

                for q in result["leads"]: st.write("• "+q)

                st.download_button("Download investigation report",result["report"],file_name="CaseWeaver_Report.txt",mime="text/plain")



# ---------------- REPORT ----------------

elif page == "Investigation Report":

    st.title("Investigation Report")

    if "investigation_result" in st.session_state:

        st.caption(st.session_state.get("investigation_case","Selected investigation"))

        st.text_area("Report",st.session_state.investigation_result["report"],height=500)

        st.download_button("Download report",st.session_state.investigation_result["report"],file_name="CaseWeaver_Report.txt",mime="text/plain")

    else: st.info("Run a complete investigation from Evidence Explorer first.")



# ---------------- ACCESS INFO ----------------

elif page == "User & Access Information":

    st.title("User & Access Information")

    st.warning("This is a hackathon demonstration role system, not a verified CBI identity or production access-control system.")

    st.write("Normal users can create accounts through the login screen. The CBI demo account is pre-created for presentation purposes.")

    st.write("For real deployment, CBI accounts must be provisioned by an authorised administrator after independent identity verification, with audit logs, case-level permissions, secure secret management and deployment behind HTTPS.")



st.markdown("---")

st.caption("CASEWEAVER · OFFLINE HACKATHON DEMONSTRATION · Human verification is required for every finding.")
