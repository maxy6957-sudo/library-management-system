
import time
from datetime import date

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from database import driver, DATABASE, URI


app = Flask(__name__)
app.secret_key = "library-local-development-key"


# ==================================================
# DATABASE HELPER
# ==================================================

def serialize_neo4j(obj):
    if isinstance(obj, dict):
        return {k: serialize_neo4j(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [serialize_neo4j(item) for item in obj]
    elif hasattr(obj, "iso_format"):
        return obj.iso_format()
    elif hasattr(obj, "year") and hasattr(obj, "month") and hasattr(obj, "day"):
        return str(obj)
    return obj


def run_query(query, parameters=None):
    with driver.session(database=DATABASE) as session:
        result = session.run(query, parameters or {})
        return [serialize_neo4j(record.data()) for record in result]


# ==================================================
# DASHBOARD
# ==================================================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/health")
def api_health():
    try:
        t0 = time.time()
        driver.verify_connectivity()
        latency_ms = max(1, round((time.time() - t0) * 1000))
        with driver.session(database=DATABASE) as session:
            count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        safe_uri = str(URI or "bolt://localhost:7687").split("@")[-1]
        return jsonify({
            "status": "connected",
            "latency_ms": latency_ms,
            "total_nodes": count,
            "database": DATABASE,
            "uri": safe_uri
        })
    except Exception as e:
        return jsonify({
            "status": "disconnected",
            "error": str(e)
        }), 503


@app.route("/api/stats")
def api_stats():
    return jsonify(get_status_stats())


def get_status_stats():
    query = """
    CALL () {
        OPTIONAL MATCH (b:BOOK)
        WHERE b.book_id IS NOT NULL OR b.title IS NOT NULL
        RETURN count(b) AS total_books
    }
    CALL () {
        OPTIONAL MATCH (m:MEMBER)
        WHERE m.member_id IS NOT NULL
        RETURN count(m) AS total_members
    }
    CALL () {
        OPTIONAL MATCH (c:BOOK_COPY)
        WITH count(c) AS total_copies
        OPTIONAL MATCH (i:ISSUE_TRANSACTION)
        WHERE (i.return_date IS NULL OR toString(i.return_date) = '')
          AND toLower(toString(coalesce(i.issue_status, i.status, 'issued')))
              IN ['issued', 'active', 'borrowed', 'open']
        WITH total_copies, count(i) AS active_loans_count
        RETURN case when total_copies >= active_loans_count then total_copies - active_loans_count else 0 end AS available_copies
    }
    CALL () {
        OPTIONAL MATCH (i:ISSUE_TRANSACTION)
        WHERE (i.return_date IS NULL OR toString(i.return_date) = '')
          AND toLower(toString(coalesce(i.issue_status, i.status, 'issued')))
              IN ['issued', 'active', 'borrowed', 'open']
        RETURN count(i) AS active_loans
    }
    CALL () {
        OPTIONAL MATCH (f:FINE)
        WHERE toLower(toString(coalesce(f.payment_status, '')))
              IN ['pending', 'unpaid', 'due']
        WITH count(f) AS recorded_fines
        OPTIONAL MATCH (i:ISSUE_TRANSACTION)
        WHERE i.due_date IS NOT NULL
          AND date(toString(i.due_date)) < date()
          AND (i.return_date IS NULL OR toString(i.return_date) = '')
          AND toLower(toString(coalesce(i.issue_status, i.status, 'issued'))) IN ['issued', 'active', 'borrowed', 'open']
          AND NOT (i)-[:HAS_FINE|GENERATES]-(:FINE)
        WITH recorded_fines, count(i) AS overdue_unfined
        RETURN recorded_fines + overdue_unfined AS pending_fines
    }
    RETURN total_books, total_members,
           available_copies, active_loans, pending_fines
    """

    rows = run_query(query)
    return rows[0] if rows else {}


@app.route("/api/check")
def api_check():
    query = """
    MATCH (n)
    RETURN labels(n) AS labels, count(n) AS total
    ORDER BY labels
    """
    return jsonify(run_query(query))


# ==================================================
# BOOK CATALOGUE
# ==================================================

@app.route("/books")
def books_page():
    search = request.args.get("search", "").strip()

    query = """
    MATCH (b:BOOK)
    WHERE (b.book_id IS NOT NULL OR b.title IS NOT NULL)
      AND ($search = ''
       OR toLower(toString(coalesce(b.title, '')))
          CONTAINS toLower($search)
       OR toLower(toString(coalesce(b.ISBN, '')))
          CONTAINS toLower($search)
       OR toLower(toString(coalesce(b.book_id, '')))
          CONTAINS toLower($search))

    OPTIONAL MATCH (b)-[:BELONGS_TO]->(cat:CATEGORY)
    OPTIONAL MATCH (b)-[:WRITTEN_BY|WRITES]-(a:AUTHOR)
    OPTIONAL MATCH (b)-[:HAS_COPY|HAS]->(c:BOOK_COPY)
    WITH b, cat, collect(DISTINCT a.author_name) AS authors, collect(DISTINCT c) AS copies
    OPTIONAL MATCH (i:ISSUE_TRANSACTION)
    WHERE (i.return_date IS NULL OR toString(i.return_date) = '')
      AND toLower(toString(coalesce(i.issue_status, i.status, 'issued'))) IN ['issued', 'active', 'borrowed', 'open']
      AND (
        (i)-[:USES_COPY|APPEARS_IN]->(:BOOK_COPY)<-[:HAS_COPY|HAS]-(b)
        OR (i)-[:ISSUED_BOOK|BORROWED]-(b)
      )
    WITH b, cat, authors, size(copies) AS total_physical_copies, count(DISTINCT i) AS active_loans
    RETURN properties(b) AS book,
           cat.category_name AS category,
           authors,
           total_physical_copies,
           active_loans,
           case when total_physical_copies >= active_loans then total_physical_copies - active_loans else 0 end AS available_copies
    ORDER BY book.title
    """

    rows = run_query(query, {"search": search})

    books = []
    for row in rows:
        book = row["book"] or {}
        book["category"] = row["category"] or "-"
        book["authors"] = [
            author for author in (row["authors"] or []) if author
        ]
        book["total_copies"] = row["total_physical_copies"] if row["total_physical_copies"] > 0 else int(book.get("total_copies", 1))
        book["available_copies"] = row["available_copies"]
        book["active_loans"] = row["active_loans"]
        if "isbn" not in book and "ISBN" in book:
            book["isbn"] = book["ISBN"]
        books.append(book)

    return render_template(
        "books.html",
        books=books,
        search=search
    )


@app.route("/api/books")
def api_books():
    query = """
    MATCH (b:BOOK)
    WHERE b.book_id IS NOT NULL OR b.title IS NOT NULL
    RETURN properties(b) AS book
    ORDER BY b.title
    """
    rows = run_query(query)
    return jsonify([row["book"] for row in rows])


# ==================================================
# MEMBERS
# ==================================================

@app.route("/members")
def members_page():
    query = """
    MATCH (m:MEMBER)
    RETURN properties(m) AS member
    ORDER BY m.member_id
    """

    rows = run_query(query)
    members = [row["member"] for row in rows]

    return render_template(
        "members.html",
        members=members
    )


# ==================================================
# INDIVIDUAL ENTITY PAGES
# ==================================================

@app.route("/data/<entity>")
def entity_page(entity):

    if entity == "authors":
        authors = run_query("""
            MATCH (a:AUTHOR)
            RETURN a.author_id AS author_id,
                   a.author_name AS author_name,
                   a.nationality AS nationality
            ORDER BY a.author_id
        """)
        return render_template("authors.html", authors=authors)

    elif entity == "categories":
        categories = run_query("""
            MATCH (c:CATEGORY)
            RETURN c.category_id AS category_id,
                   c.category_name AS category_name
            ORDER BY c.category_id
        """)
        return render_template(
            "categories.html",
            categories=categories
        )

    elif entity == "book-copies":
        copies = run_query("""
            MATCH (c:BOOK_COPY)
            OPTIONAL MATCH (b:BOOK)-[:HAS_COPY|HAS]->(c)
            OPTIONAL MATCH (i:ISSUE_TRANSACTION)-[:USES_COPY|APPEARS_IN]->(c)
            WHERE (i.return_date IS NULL OR toString(i.return_date) = '')
              AND toLower(toString(coalesce(i.issue_status, i.status, 'issued'))) IN ['issued', 'active', 'borrowed', 'open']
            WITH c, b, count(i) AS active_loans_on_copy
            RETURN c.copy_id AS copy_id,
                   b.book_id AS book_id,
                   b.title AS title,
                   c.shelf_location AS shelf_location,
                   CASE
                       WHEN active_loans_on_copy > 0 THEN 'issued'
                       WHEN toLower(toString(coalesce(c.avail_status, ''))) IN ['available', 'avail'] THEN 'available'
                       ELSE coalesce(c.avail_status, 'available')
                   END AS avail_status
            ORDER BY c.copy_id
        """)
        return render_template(
            "book_copies.html",
            copies=copies
        )

    elif entity == "librarians":
        librarians = run_query("""
            MATCH (l:LIBRARIAN)
            RETURN l.librarian_id AS librarian_id,
                   l.first_name AS first_name,
                   l.last_name AS last_name,
                   l.email AS email,
                   l.phone AS phone
            ORDER BY l.librarian_id
        """)
        return render_template(
            "librarians.html",
            librarians=librarians
        )

    elif entity == "issue-transactions":
        issues = run_query("""
            MATCH (i:ISSUE_TRANSACTION)
            OPTIONAL MATCH (m:MEMBER)-[:BORROWED|BORROWS]-(i)
            OPTIONAL MATCH (i)-[:USES_COPY|APPEARS_IN]-(c:BOOK_COPY)
            OPTIONAL MATCH (i)-[:HANDLED_BY|ISSUES]-(l:LIBRARIAN)
            RETURN i.issue_id AS issue_id,
                   toString(i.issue_date) AS issue_date,
                   toString(i.due_date) AS due_date,
                   toString(i.return_date) AS return_date,
                   coalesce(i.issue_status, i.status, 'issued') AS issue_status,
                   coalesce(c.copy_id, 'DIRECT') AS copy_id,
                   coalesce(m.member_id, 'Unknown') AS member_id,
                   coalesce(l.librarian_id, 'N/A') AS librarian_id
            ORDER BY i.issue_date DESC
        """)
        return render_template(
            "issue_transactions.html",
            issues=issues
        )

    elif entity == "fines":
        fines = run_query("""
            MATCH (f:FINE)
            OPTIONAL MATCH (i:ISSUE_TRANSACTION)-[:HAS_FINE|GENERATES]-(f)
            OPTIONAL MATCH (m:MEMBER)-[:BORROWED|BORROWS]-(i)
            OPTIONAL MATCH (i)-[:USES_COPY|APPEARS_IN]-(c:BOOK_COPY)-[:HAS_COPY|HAS]-(b1:BOOK)
            OPTIONAL MATCH (i)-[:ISSUED_BOOK|BORROWED]-(b2:BOOK)
            WITH f, i,
                 head(collect(DISTINCT coalesce(b2.title, b1.title))) AS book_title,
                 head(collect(DISTINCT (m.first_name + ' ' + coalesce(m.last_name, '')))) AS member_name
            RETURN f.fine_id AS fine_id,
                   i.issue_id AS issue_id,
                   book_title,
                   member_name,
                   f.fine_rate AS fine_rate,
                   f.amount AS amount,
                   f.payment_status AS payment_status,
                   i.return_date AS return_date

            UNION

            MATCH (i:ISSUE_TRANSACTION)
            WHERE i.due_date IS NOT NULL
              AND date(toString(i.due_date)) < date()
              AND (i.return_date IS NULL OR toString(i.return_date) = '')
              AND toLower(toString(coalesce(i.issue_status, i.status, 'issued'))) IN ['issued', 'active', 'borrowed', 'open']
              AND NOT (i)-[:HAS_FINE|GENERATES]-(:FINE)
            WITH i, duration.inDays(date(toString(i.due_date)), coalesce(date(toString(i.return_date)), date())).days AS overdue_days
            WHERE overdue_days > 0
            WITH i, overdue_days,
                 (CASE WHEN overdue_days <= 5 THEN overdue_days * 2
                       WHEN overdue_days <= 14 THEN 10 + (overdue_days - 5) * 3
                       ELSE 10 + 27 + (overdue_days - 14) * 5
                  END) AS est_amount
            OPTIONAL MATCH (m:MEMBER)-[:BORROWED|BORROWS]-(i)
            OPTIONAL MATCH (i)-[:USES_COPY|APPEARS_IN]-(c:BOOK_COPY)-[:HAS_COPY|HAS]-(b1:BOOK)
            OPTIONAL MATCH (i)-[:ISSUED_BOOK|BORROWED]-(b2:BOOK)
            WITH i, est_amount,
                 head(collect(DISTINCT coalesce(b2.title, b1.title))) AS book_title,
                 head(collect(DISTINCT (m.first_name + ' ' + coalesce(m.last_name, '')))) AS member_name
            RETURN 'OVERDUE-' + i.issue_id AS fine_id,
                   i.issue_id AS issue_id,
                   book_title,
                   member_name,
                   'Progressive: Rs. 2, 3, 5 / day' AS fine_rate,
                   est_amount AS amount,
                   'pending' AS payment_status,
                   i.return_date AS return_date

            ORDER BY fine_id
        """)
        return render_template(
            "fines.html",
            fines=fines
        )

    return "Page not found", 404


# ==================================================
# CIRCULATION DESK
# ==================================================

@app.route("/circulation")
def circulation_page():

    loans = run_query("""
        MATCH (i:ISSUE_TRANSACTION)
        WHERE (i.return_date IS NULL OR toString(i.return_date) = '')
          AND toLower(toString(coalesce(i.issue_status, i.status, 'issued')))
              IN ['issued', 'active', 'borrowed', 'open']
        OPTIONAL MATCH (m:MEMBER)-[:BORROWED|BORROWS]-(i)
        OPTIONAL MATCH (i)-[:USES_COPY|APPEARS_IN]-(c:BOOK_COPY)
        OPTIONAL MATCH (c)-[:HAS_COPY|HAS]-(b1:BOOK)
        OPTIONAL MATCH (i)-[:ISSUED_BOOK|BORROWED]-(b2:BOOK)
        WITH i, m, c,
             head(collect(DISTINCT coalesce(b2.title, b1.title))) AS title,
             head(collect(DISTINCT coalesce(c.copy_id, 'DIRECT'))) AS copy_id
        RETURN i.issue_id AS issue_id,
               toString(i.issue_date) AS issue_date,
               toString(i.due_date) AS due_date,
               coalesce(m.member_id, 'Unknown') AS member_id,
               copy_id,
               coalesce(title, 'Untitled Book') AS title
        ORDER BY i.due_date
    """)

    books = run_query("""
        MATCH (b:BOOK)-[:HAS_COPY|HAS]->(c:BOOK_COPY)
        WHERE toLower(toString(coalesce(c.avail_status, '')))
              IN ['available', 'avail']
          AND NOT EXISTS {
              MATCH (active:ISSUE_TRANSACTION)-[:USES_COPY]->(c)
              WHERE (active.return_date IS NULL OR toString(active.return_date) = '')
                AND toLower(toString(coalesce(active.issue_status, active.status, 'issued'))) IN ['issued', 'active', 'borrowed', 'open']
          }
        RETURN b.book_id AS book_id,
               b.title AS title,
               c.copy_id AS copy_id
        ORDER BY b.title, c.copy_id
    """)

    members = run_query("""
        MATCH (m:MEMBER)
        RETURN m.member_id AS member_id,
               m.first_name AS first_name,
               m.last_name AS last_name
        ORDER BY m.member_id
    """)

    librarians = run_query("""
        MATCH (l:LIBRARIAN)
        RETURN l.librarian_id AS librarian_id,
               l.first_name AS first_name,
               l.last_name AS last_name
        ORDER BY l.librarian_id
    """)

    return render_template(
        "circulation.html",
        loans=loans,
        books=books,
        members=members,
        librarians=librarians,
        today=date.today().isoformat()
    )


# ==================================================
# ISSUE A BOOK COPY
# ==================================================

@app.route("/issue", methods=["POST"])
def issue_book():
    member_id = request.form.get("member_id", "").strip()
    copy_id = request.form.get("copy_id", "").strip()
    librarian_id = request.form.get("librarian_id", "").strip()
    due_date = request.form.get("due_date", "").strip()

    if not all([member_id, copy_id, librarian_id, due_date]):
        flash("Please complete all issue-book fields.", "error")
        return redirect(url_for("circulation_page"))

    try:
        parsed_due_date = date.fromisoformat(due_date)
    except ValueError:
        flash("Please enter a valid due date.", "error")
        return redirect(url_for("circulation_page"))

    if parsed_due_date < date.today():
        flash("The due date cannot be in the past.", "error")
        return redirect(url_for("circulation_page"))

    query = """
    MATCH (m:MEMBER {member_id: $member_id})
    MATCH (c:BOOK_COPY {copy_id: $copy_id})
    MATCH (l:LIBRARIAN {librarian_id: $librarian_id})
    OPTIONAL MATCH (b:BOOK)-[:HAS_COPY|HAS]->(c)

    WHERE toLower(toString(coalesce(c.avail_status, '')))
          IN ['available', 'avail']
      AND NOT EXISTS {
          MATCH (active:ISSUE_TRANSACTION)-[:USES_COPY]->(c)
          WHERE (active.return_date IS NULL OR toString(active.return_date) = '')
            AND toLower(toString(coalesce(active.issue_status, active.status, 'issued'))) IN ['issued', 'active', 'borrowed', 'open']
      }

    CREATE (i:ISSUE_TRANSACTION {
        issue_id: 'ISSUE-' + randomUUID(),
        issue_date: toString(date()),
        due_date: $due_date,
        return_date: null,
        issue_status: 'issued',
        status: 'ISSUED'
    })

    CREATE (m)-[:BORROWED]->(i)
    CREATE (i)-[:USES_COPY]->(c)
    CREATE (i)-[:HANDLED_BY]->(l)
    FOREACH (_ IN CASE WHEN b IS NOT NULL THEN [1] ELSE [] END |
        CREATE (i)-[:ISSUED_BOOK]->(b)
    )

    SET c.avail_status = 'issued'

    RETURN i.issue_id AS issue_id
    """

    rows = run_query(query, {
        "member_id": member_id,
        "copy_id": copy_id,
        "librarian_id": librarian_id,
        "due_date": due_date
    })

    if rows:
        flash(
            "Book copy issued successfully. Issue ID: "
            + rows[0]["issue_id"],
            "success"
        )
    else:
        flash(
            "Issue failed. Check the member, copy, librarian IDs "
            "and copy availability.",
            "error"
        )

    return redirect(url_for("circulation_page"))


# ==================================================
# RETURN A BOOK COPY
# ==================================================

@app.route("/return/<issue_id>", methods=["POST"])
def return_book(issue_id):
    # Step 1: Find the issue and calculate overdue days safely
    result = run_query("""
        MATCH (i:ISSUE_TRANSACTION {issue_id: $issue_id})
        WHERE (i.return_date IS NULL OR toString(i.return_date) = '')
          AND toLower(toString(coalesce(i.issue_status, i.status, 'issued')))
              IN ['issued', 'active', 'borrowed', 'open']
        RETURN CASE
                   WHEN i.due_date IS NOT NULL
                   THEN duration.inDays(date(toString(i.due_date)), date()).days
                   ELSE 0
               END AS overdue_days
    """, {"issue_id": issue_id})

    # Step 2: Check whether the issue exists and is still active
    if not result:
        flash("Issue not found or the book has already been returned.", "error")
        return redirect(url_for("circulation_page"))

    overdue_days = max(0, int(result[0].get("overdue_days") or 0))

    # Step 3: Calculate the progressive fine
    # Days 1-5: ₹2/day, Days 6-14: ₹3/day, Days 15+: ₹5/day
    fine_amount = 0
    if overdue_days > 0:
        days_at_2 = min(overdue_days, 5)
        days_at_3 = min(max(overdue_days - 5, 0), 9)
        days_at_5 = max(overdue_days - 14, 0)

        fine_amount = (
            days_at_2 * 2
            + days_at_3 * 3
            + days_at_5 * 5
        )

    # Step 4: Return the book and create a fine only if overdue
    fine_id = "FINE-" + issue_id
    run_query("""
        MATCH (i:ISSUE_TRANSACTION {issue_id: $issue_id})
        OPTIONAL MATCH (i)-[:USES_COPY|APPEARS_IN]-(c:BOOK_COPY)
        WHERE (i.return_date IS NULL OR toString(i.return_date) = '')
          AND toLower(toString(coalesce(i.issue_status, i.status, 'issued')))
              IN ['issued', 'active', 'borrowed', 'open']

        SET i.return_date = toString(date()),
            i.issue_status = 'returned',
            i.status = 'RETURNED'

        FOREACH (_ IN CASE WHEN c IS NOT NULL THEN [1] ELSE [] END |
            SET c.avail_status = 'available'
        )

        FOREACH (_ IN CASE
            WHEN $overdue_days > 0 THEN [1]
            ELSE []
        END |
            MERGE (f:FINE {fine_id: $fine_id})
            SET f.fine_rate = $fine_rate,
                f.amount = $fine_amount,
                f.payment_status = coalesce(
                    f.payment_status, 'pending'
                )
            MERGE (i)-[:HAS_FINE]->(f)
        )

        RETURN i.issue_id AS issue_id
    """, {
        "issue_id": issue_id,
        "overdue_days": overdue_days,
        "fine_id": fine_id,
        "fine_rate": "Progressive: Rs. 2, 3, 5 / day",
        "fine_amount": fine_amount
    })

    # Step 5: Show the result
    if overdue_days > 0:
        flash(
            f"Book returned successfully. "
            f"Overdue by {overdue_days} day(s). "
            f"Fine: Rs. {fine_amount} generated (Pending payment).",
            "warning"
        )
    else:
        flash(
            "Book returned successfully. No fine applicable.",
            "success"
        )

    return redirect(url_for("circulation_page"))


@app.route("/fine/pay/<fine_id>", methods=["POST"])
def pay_fine(fine_id):
    if fine_id.startswith("OVERDUE-"):
        issue_id = fine_id.split("OVERDUE-", 1)[1]
        calc = run_query("""
            MATCH (i:ISSUE_TRANSACTION {issue_id: $issue_id})
            RETURN duration.inDays(date(toString(i.due_date)), coalesce(date(toString(i.return_date)), date())).days AS overdue_days
        """, {"issue_id": issue_id})
        overdue_days = max(0, int(calc[0].get("overdue_days") or 0)) if calc else 0
        days_at_2 = min(overdue_days, 5)
        days_at_3 = min(max(overdue_days - 5, 0), 9)
        days_at_5 = max(overdue_days - 14, 0)
        fine_amount = max(2, (days_at_2 * 2 + days_at_3 * 3 + days_at_5 * 5))

        run_query("""
            MATCH (i:ISSUE_TRANSACTION {issue_id: $issue_id})
            MERGE (f:FINE {fine_id: 'FINE-' + $issue_id})
            SET f.payment_status = 'paid',
                f.fine_rate = 'Progressive: Rs. 2, 3, 5 / day',
                f.amount = $fine_amount
            MERGE (i)-[:HAS_FINE]->(f)
        """, {"issue_id": issue_id, "fine_amount": fine_amount})
    else:
        run_query("""
            MATCH (f:FINE {fine_id: $fine_id})
            SET f.payment_status = 'paid'
        """, {"fine_id": fine_id})
    flash(f"Fine {fine_id} marked as paid successfully.", "success")
    return redirect(url_for("entity_page", entity="fines"))


@app.route("/recommendations")
def recommendations_page():

    members = run_query("""
        MATCH (m:MEMBER)
        RETURN m.member_id AS member_id,
               m.first_name AS first_name,
               m.last_name AS last_name
        ORDER BY m.member_id
    """)

    selected_member = request.args.get("member_id", "").strip()
    recommendations = []

    if selected_member:
        query = """
        MATCH (selected:MEMBER {member_id: $member_id})

        OPTIONAL MATCH (selected)-[:BORROWED|BORROWS]-(i1:ISSUE_TRANSACTION)
        OPTIONAL MATCH (i1)-[:USES_COPY|APPEARS_IN]-(:BOOK_COPY)-[:HAS_COPY|HAS]-(p1:BOOK)
        OPTIONAL MATCH (i1)-[:ISSUED_BOOK|BORROWED]-(p2:BOOK)
        WITH selected, collect(DISTINCT coalesce(p1.book_id, p2.book_id)) AS past_ids

        MATCH (other:MEMBER)-[:BORROWED|BORROWS]-(i2:ISSUE_TRANSACTION)
        OPTIONAL MATCH (i2)-[:USES_COPY|APPEARS_IN]-(:BOOK_COPY)-[:HAS_COPY|HAS]-(c1:BOOK)
        OPTIONAL MATCH (i2)-[:ISSUED_BOOK|BORROWED]-(c2:BOOK)
        WITH selected, past_ids, other, coalesce(c2, c1) AS candidate
        WHERE candidate IS NOT NULL
          AND other <> selected
          AND NOT candidate.book_id IN past_ids

        WITH candidate, count(DISTINCT other) AS score

        OPTIONAL MATCH (candidate)-[:WRITTEN_BY|WRITES]-(a:AUTHOR)
        OPTIONAL MATCH (candidate)-[:BELONGS_TO]->(cat:CATEGORY)

        RETURN properties(candidate) AS book,
               collect(DISTINCT a.author_name) AS authors,
               cat.category_name AS category,
               score
        ORDER BY score DESC, book.title
        LIMIT 10
        """

        rows = run_query(query, {"member_id": selected_member})

        for row in rows:
            book = row["book"] or {}
            book["authors"] = [
                name for name in (row["authors"] or []) if name
            ]
            book["category"] = row["category"] or "-"
            book["score"] = row["score"]
            recommendations.append(book)

    return render_template(
        "recommendations.html",
        members=members,
        recommendations=recommendations,
        selected_member=selected_member
    )


# ==================================================
# GRAPH EXPLORER PAGE
# ==================================================

@app.route("/graph")
def graph_page():
    return render_template("graph.html")


# ==================================================
# GRAPH EXPLORER API
# ==================================================

@app.route("/api/graph")
def api_graph():

    rows = run_query("""
        MATCH (a)-[r]->(b)

        WHERE any(label IN labels(a)
                  WHERE label IN [
                      'BOOK', 'AUTHOR', 'CATEGORY', 'BOOK_COPY',
                      'MEMBER', 'LIBRARIAN',
                      'ISSUE_TRANSACTION', 'FINE'
                  ])
          AND any(label IN labels(b)
                  WHERE label IN [
                      'BOOK', 'AUTHOR', 'CATEGORY', 'BOOK_COPY',
                      'MEMBER', 'LIBRARIAN',
                      'ISSUE_TRANSACTION', 'FINE'
                  ])

        RETURN elementId(a) AS source,
               labels(a)[0] AS source_label,
               properties(a) AS source_properties,
               elementId(b) AS target,
               labels(b)[0] AS target_label,
               properties(b) AS target_properties,
               type(r) AS relationship

        LIMIT 300
    """)

    nodes_by_id = {}
    links = []

    def display_name(label, properties):
        properties = properties or {}

        if label in ["MEMBER", "LIBRARIAN"]:
            full_name = f"{properties.get('first_name', '')} {properties.get('last_name', '')}".strip()
            if full_name:
                return full_name

        preferred_keys = {
            "BOOK": ["title", "book_id"],
            "AUTHOR": ["author_name", "author_id"],
            "CATEGORY": ["category_name", "category_id"],
            "BOOK_COPY": ["copy_id"],
            "MEMBER": ["first_name", "member_id"],
            "LIBRARIAN": ["first_name", "librarian_id"],
            "ISSUE_TRANSACTION": ["issue_id"],
            "FINE": ["fine_id"]
        }

        for key in preferred_keys.get(label, []):
            if properties.get(key) is not None:
                return str(properties[key])

        return label

    for row in rows:
        source_id = row["source"]
        target_id = row["target"]

        if source_id not in nodes_by_id:
            source_label = row["source_label"]
            source_properties = row["source_properties"] or {}

            nodes_by_id[source_id] = {
                "id": source_id,
                "label": source_label,
                "name": display_name(
                    source_label, source_properties
                ),
                "properties": source_properties
            }

        if target_id not in nodes_by_id:
            target_label = row["target_label"]
            target_properties = row["target_properties"] or {}

            nodes_by_id[target_id] = {
                "id": target_id,
                "label": target_label,
                "name": display_name(
                    target_label, target_properties
                ),
                "properties": target_properties
            }

        links.append({
            "source": source_id,
            "target": target_id,
            "relationship": row["relationship"]
        })

    return jsonify({
        "nodes": list(nodes_by_id.values()),
        "links": links
    })


# ==================================================
# RUN APPLICATION
# ==================================================

if __name__ == "__main__":
    app.run(debug=True)
