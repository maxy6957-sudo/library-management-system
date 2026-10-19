# Library Management System (Graph Database Project)

A modern, high-performance Library Management System built with **Flask** and **Neo4j Graph Database**. It combines enterprise library circulation management with graph-powered reader intelligence, collaborative recommendations, and an interactive 3D/2D Graph Explorer.

---

## 🚀 Key Features

1. **Dashboard & Live Telemetry:**
   - Real-time KPI metrics (`Total Books`, `Available Copies`, `Active Loans`, `Total Members`, `Pending Fines`).
   - Dynamic Neo4j Aura cloud database health monitor with ping latency and node counts.

2. **Dual-Zone Circulation Desk (`/circulation`):**
   - Fast book checkout with copy availability verification.
   - Live Active & Overdue loans table with 1-click book returns.

3. **Graph Explorer (`/graph`):**
   - High-performance, offline-first HTML5 Canvas physics engine.
   - Deep inspection with **up to 15x magnification**, floating zoom slider, and node auto-focus.
   - Taxonomy label filtering and dynamic node property inspector.

4. **Graph Recommendation Hub (`/recommendations`):**
   - Collaborative filtering utilizing reader traversal paths (books frequently borrowed together by readers with shared interests).

5. **Automated & Progressive Fines System (`/data/fines`):**
   - Automatic progressive fine calculations:
     - Days 1–5: ₹2 / day
     - Days 6–14: ₹3 / day
     - Days 15+: ₹5 / day
   - Dynamic real-time calculation of active overdue loans.
   - Instant "Mark Paid" settlement action.

6. **Complete Entity Catalogs:**
   - Books Catalogue (`/books`) with ISBN search and author tags.
   - Inventory Copies (`/data/book-copies`) with shelf location tracking.
   - Members, Librarians, Authors, Categories, and Issue Transactions directories.

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10+, Flask 3.x
- **Database:** Neo4j Graph Database (Neo4j Aura Cloud / Local Desktop)
- **Frontend:** Jinja2 templates, Vanilla JavaScript, HTML5 Canvas physics engine, Stitch Design System (Modern Slate & Navy)

---

## 📦 Setup & Installation

### 1. Clone or Extract the Project
Open a terminal in the project directory:
```bash
cd "new project"
```

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` with your Neo4j database credentials:
```env
NEO4J_URI=neo4j+s://<your-aura-instance-id>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-neo4j-password>
NEO4J_DATABASE=neo4j
```

### 5. (Optional) Seed the Database
To populate the database with initial sample books, authors, members, and copies:
```bash
python seed_data.py
```

### 6. Run the Application
```bash
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 📂 Project Directory Structure

```text
├── app.py                  # Main Flask application and Neo4j Cypher routes
├── database.py             # Neo4j driver connection and session management
├── seed_data.py            # Sample database seed script
├── requirements.txt        # Python package dependencies
├── .env.example            # Environment variables template
├── templates/              # Stitch UI Jinja2 templates
│   ├── base.html           # Unified master layout with topbar & sidebar
│   ├── index.html          # KPI Dashboard & quick action hubs
│   ├── circulation.html    # Dual-zone circulation desk
│   ├── books.html          # Searchable books catalogue
│   ├── graph.html          # Interactive Graph Explorer with 15x zoom
│   ├── recommendations.html# Collaborative graph recommendations
│   ├── fines.html          # Progressive fines and settlements ledger
│   ├── book_copies.html    # Physical inventory copies list
│   ├── members.html        # Library members directory
│   ├── librarians.html     # Librarians directory
│   ├── authors.html        # Authors directory
│   ├── categories.html     # Categories taxonomy directory
│   └── issue_transactions.html # Transaction audit log
└── README.md               # Project documentation
```
