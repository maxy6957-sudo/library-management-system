"""
Database Seeder for Library Management System (Neo4j)
Populates realistic sample books, authors, categories, copies, members, librarians,
issue transactions, and fine records.
"""

from database import driver, DATABASE


def run_cypher(session, query, parameters=None):
    session.run(query, parameters or {})


def seed():
    print(f"Connecting to Neo4j database '{DATABASE}'...")

    with driver.session(database=DATABASE) as session:
        # Step 1: Create constraints for schema integrity
        print("Creating constraints (if not existing)...")
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (b:BOOK) REQUIRE b.book_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:AUTHOR) REQUIRE a.author_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:CATEGORY) REQUIRE c.category_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (cp:BOOK_COPY) REQUIRE cp.copy_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:MEMBER) REQUIRE m.member_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (l:LIBRARIAN) REQUIRE l.librarian_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (i:ISSUE_TRANSACTION) REQUIRE i.issue_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:FINE) REQUIRE f.fine_id IS UNIQUE",
        ]
        for cql in constraints:
            try:
                run_cypher(session, cql)
            except Exception as e:
                print(f"Constraint notice: {e}")

        # Step 2: Clean up empty ghost nodes (if any)
        print("Cleaning up empty placeholder nodes...")
        run_cypher(session, """
            MATCH (n)
            WHERE properties(n) = {}
            DETACH DELETE n
        """)

        # Step 3: Seed Categories
        print("Seeding Categories...")
        categories = [
            {"id": "C001", "name": "Fiction"},
            {"id": "C002", "name": "Fantasy"},
            {"id": "C003", "name": "Science Fiction"},
            {"id": "C004", "name": "Technology"},
            {"id": "C005", "name": "History"},
            {"id": "C006", "name": "Mystery"},
        ]
        for cat in categories:
            run_cypher(session, """
                MERGE (c:CATEGORY {category_id: $id})
                SET c.category_name = $name
            """, cat)

        # Step 4: Seed Authors
        print("Seeding Authors...")
        authors = [
            {"id": "A001", "name": "R. K. Narayan", "nationality": "Indian"},
            {"id": "A002", "name": "J. K. Rowling", "nationality": "British"},
            {"id": "A003", "name": "George Orwell", "nationality": "British"},
            {"id": "A004", "name": "Isaac Asimov", "nationality": "American"},
            {"id": "A005", "name": "Martin Kleppmann", "nationality": "German"},
            {"id": "A006", "name": "Yuval Noah Harari", "nationality": "Israeli"},
            {"id": "A007", "name": "Arthur Conan Doyle", "nationality": "British"},
        ]
        for auth in authors:
            run_cypher(session, """
                MERGE (a:AUTHOR {author_id: $id})
                SET a.author_name = $name, a.nationality = $nationality
            """, auth)

        # Step 5: Seed Books & link with Author + Category
        print("Seeding Books...")
        books = [
            {
                "id": "B001", "title": "Malgudi Days", "year": 1943,
                "isbn": "9788185986173", "edition": "1st", "total_copies": 2,
                "author_id": "A001", "category_id": "C001"
            },
            {
                "id": "B002", "title": "Harry Potter and the Philosopher's Stone", "year": 1997,
                "isbn": "9780747532699", "edition": "1st", "total_copies": 2,
                "author_id": "A002", "category_id": "C002"
            },
            {
                "id": "B003", "title": "1984", "year": 1949,
                "isbn": "9780451524935", "edition": "1st", "total_copies": 2,
                "author_id": "A003", "category_id": "C001"
            },
            {
                "id": "B004", "title": "Foundation", "year": 1951,
                "isbn": "9780553293357", "edition": "1st", "total_copies": 2,
                "author_id": "A004", "category_id": "C003"
            },
            {
                "id": "B005", "title": "Designing Data-Intensive Applications", "year": 2017,
                "isbn": "9781449373320", "edition": "1st", "total_copies": 2,
                "author_id": "A005", "category_id": "C004"
            },
            {
                "id": "B006", "title": "Sapiens: A Brief History of Humankind", "year": 2014,
                "isbn": "9780062316097", "edition": "1st", "total_copies": 2,
                "author_id": "A006", "category_id": "C005"
            },
            {
                "id": "B007", "title": "The Adventures of Sherlock Holmes", "year": 1892,
                "isbn": "9780141034355", "edition": "1st", "total_copies": 2,
                "author_id": "A007", "category_id": "C006"
            },
        ]
        for bk in books:
            run_cypher(session, """
                MERGE (b:BOOK {book_id: $id})
                SET b.title = $title,
                    b.publication_year = $year,
                    b.ISBN = $isbn,
                    b.isbn = $isbn,
                    b.edition = $edition,
                    b.total_copies = $total_copies

                WITH b
                MATCH (a:AUTHOR {author_id: $author_id})
                MATCH (cat:CATEGORY {category_id: $category_id})
                MERGE (b)-[:WRITTEN_BY]->(a)
                MERGE (b)-[:BELONGS_TO]->(cat)
            """, bk)

        # Step 6: Seed Book Copies
        print("Seeding Book Copies...")
        copies = [
            {"copy_id": "CP001", "book_id": "B001", "shelf": "A-01", "status": "available"},
            {"copy_id": "CP002", "book_id": "B001", "shelf": "A-02", "status": "issued"},
            {"copy_id": "CP003", "book_id": "B002", "shelf": "B-01", "status": "available"},
            {"copy_id": "CP004", "book_id": "B002", "shelf": "B-02", "status": "available"},
            {"copy_id": "CP005", "book_id": "B003", "shelf": "C-01", "status": "available"},
            {"copy_id": "CP006", "book_id": "B003", "shelf": "C-02", "status": "available"},
            {"copy_id": "CP007", "book_id": "B004", "shelf": "D-01", "status": "available"},
            {"copy_id": "CP008", "book_id": "B004", "shelf": "D-02", "status": "issued"},
            {"copy_id": "CP009", "book_id": "B005", "shelf": "E-01", "status": "available"},
            {"copy_id": "CP010", "book_id": "B005", "shelf": "E-02", "status": "available"},
            {"copy_id": "CP011", "book_id": "B006", "shelf": "F-01", "status": "available"},
            {"copy_id": "CP012", "book_id": "B006", "shelf": "F-02", "status": "available"},
            {"copy_id": "CP013", "book_id": "B007", "shelf": "G-01", "status": "available"},
            {"copy_id": "CP014", "book_id": "B007", "shelf": "G-02", "status": "available"},
        ]
        for cp in copies:
            run_cypher(session, """
                MERGE (c:BOOK_COPY {copy_id: $copy_id})
                SET c.shelf_location = $shelf,
                    c.avail_status = $status
                WITH c
                MATCH (b:BOOK {book_id: $book_id})
                MERGE (b)-[:HAS_COPY]->(c)
            """, cp)

        # Step 7: Seed Members
        print("Seeding Members...")
        members = [
            {"id": "M001", "first": "Alice", "last": "Johnson", "email": "alice@example.com", "status": "Active"},
            {"id": "M002", "first": "Bob", "last": "Smith", "email": "bob@example.com", "status": "Active"},
            {"id": "M003", "first": "Charlie", "last": "Brown", "email": "charlie@example.com", "status": "Active"},
            {"id": "M004", "first": "Diana", "last": "Prince", "email": "diana@example.com", "status": "Active"},
        ]
        for mem in members:
            run_cypher(session, """
                MERGE (m:MEMBER {member_id: $id})
                SET m.first_name = $first,
                    m.last_name = $last,
                    m.email = $email,
                    m.membership_status = $status
            """, mem)

        # Step 8: Seed Librarians
        print("Seeding Librarians...")
        librarians = [
            {"id": "L001", "first": "Sarah", "last": "Connor", "email": "sarah@library.org", "phone": "555-0101"},
            {"id": "L002", "first": "John", "last": "Doe", "email": "john@library.org", "phone": "555-0102"},
        ]
        for lib in librarians:
            run_cypher(session, """
                MERGE (l:LIBRARIAN {librarian_id: $id})
                SET l.first_name = $first,
                    l.last_name = $last,
                    l.email = $email,
                    l.phone = $phone
            """, lib)

        # Step 9: Seed Issue Transactions and Fines
        print("Seeding Issue Transactions and Fines...")
        transactions = [
            # I001: M001 borrowed CP001 (returned on time)
            {
                "issue_id": "I001", "member_id": "M001", "copy_id": "CP001", "lib_id": "L001",
                "issue_date": "2026-09-01", "due_date": "2026-09-15", "return_date": "2026-09-14",
                "status": "returned", "has_fine": False
            },
            # I002: M002 borrowed CP003 (returned on time)
            {
                "issue_id": "I002", "member_id": "M002", "copy_id": "CP003", "lib_id": "L001",
                "issue_date": "2026-09-05", "due_date": "2026-09-19", "return_date": "2026-09-18",
                "status": "returned", "has_fine": False
            },
            # I003: M002 borrowed CP005 (returned 4 days late, fine paid)
            {
                "issue_id": "I003", "member_id": "M002", "copy_id": "CP005", "lib_id": "L002",
                "issue_date": "2026-09-10", "due_date": "2026-09-24", "return_date": "2026-09-28",
                "status": "returned", "has_fine": True,
                "fine_id": "FINE-I003", "fine_rate": "Progressive: ₹2, ₹3, ₹5 / day",
                "fine_amount": 8, "fine_status": "paid"
            },
            # I004: M001 borrowed CP007 (returned 7 days late, fine pending)
            {
                "issue_id": "I004", "member_id": "M001", "copy_id": "CP007", "lib_id": "L002",
                "issue_date": "2026-09-15", "due_date": "2026-09-29", "return_date": "2026-10-06",
                "status": "returned", "has_fine": True,
                "fine_id": "FINE-I004", "fine_rate": "Progressive: ₹2, ₹3, ₹5 / day",
                "fine_amount": 16, "fine_status": "pending"
            },
            # I005: M003 borrowed CP002 (active loan)
            {
                "issue_id": "I005", "member_id": "M003", "copy_id": "CP002", "lib_id": "L001",
                "issue_date": "2026-10-10", "due_date": "2026-10-24", "return_date": None,
                "status": "issued", "has_fine": False
            },
            # I006: M004 borrowed CP008 (active loan - overdue for testing fines!)
            {
                "issue_id": "I006", "member_id": "M004", "copy_id": "CP008", "lib_id": "L001",
                "issue_date": "2026-10-01", "due_date": "2026-10-15", "return_date": None,
                "status": "issued", "has_fine": False
            },
        ]

        for tx in transactions:
            run_cypher(session, """
                MERGE (i:ISSUE_TRANSACTION {issue_id: $issue_id})
                SET i.issue_date = $issue_date,
                    i.due_date = $due_date,
                    i.return_date = $return_date,
                    i.issue_status = $status

                WITH i
                MATCH (m:MEMBER {member_id: $member_id})
                MATCH (c:BOOK_COPY {copy_id: $copy_id})
                MATCH (l:LIBRARIAN {librarian_id: $lib_id})

                MERGE (m)-[:BORROWED]->(i)
                MERGE (i)-[:USES_COPY]->(c)
                MERGE (i)-[:HANDLED_BY]->(l)
            """, tx)

            if tx.get("has_fine"):
                run_cypher(session, """
                    MATCH (i:ISSUE_TRANSACTION {issue_id: $issue_id})
                    MERGE (f:FINE {fine_id: $fine_id})
                    SET f.fine_rate = $fine_rate,
                        f.amount = $fine_amount,
                        f.payment_status = $fine_status
                    MERGE (i)-[:HAS_FINE]->(f)
                """, tx)

    print("\n[OK] Database successfully seeded with rich sample data!")


if __name__ == "__main__":
    seed()
