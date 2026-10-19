
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

driver = GraphDatabase.driver(
    URI,
    auth=(USERNAME, PASSWORD)
)

def test_connection():
    driver.verify_connectivity()

    with driver.session(database=DATABASE) as session:
        result = session.run("RETURN 'Connected successfully!' AS message")
        return result.single()["message"]

if __name__ == "__main__":
    try:
        print(test_connection())
    except Exception as error:
        print("Connection failed:", error)
    finally:
        driver.close()
