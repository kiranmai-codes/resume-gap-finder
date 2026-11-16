import sqlite3
import hashlib
import re


class JobDatabase:
    def __init__(self, db_path="jobs.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_portal TEXT,
                source_job_id TEXT,
                job_title TEXT,
                company_name TEXT,
                location TEXT,
                description TEXT,
                content_hash TEXT UNIQUE,
                discovery_family TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_portal ON jobs(source_portal)"
        )
        self.conn.commit()

    @staticmethod
    def generate_hash(company, title, description):
        """Deterministic fingerprint: company + title + normalized description."""
        text = f"{company}||{title}||{description}".lower()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def is_duplicate(self, content_hash):
        self.cursor.execute(
            "SELECT 1 FROM jobs WHERE content_hash = ?", (content_hash,)
        )
        return self.cursor.fetchone() is not None

    def insert_job(self, job_data):
        """Returns True if inserted, False if duplicate."""
        content_hash = self.generate_hash(
            job_data.get("company_name", ""),
            job_data.get("job_title", ""),
            job_data.get("description", ""),
        )

        if self.is_duplicate(content_hash):
            return False

        try:
            self.cursor.execute(
                """
                INSERT INTO jobs (
                    source_portal, source_job_id, job_title, company_name,
                    location, description, content_hash, discovery_family
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_data.get("source_portal", ""),
                    str(job_data.get("source_job_id", "")),
                    job_data.get("job_title", ""),
                    job_data.get("company_name", ""),
                    job_data.get("location", ""),
                    job_data.get("description", ""),
                    content_hash,
                    job_data.get("discovery_family", ""),
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        
    def get_job_ids(self, portal: str) -> set:
        """Return set of known job IDs for a portal. Used for incremental scraping."""
        self.cursor.execute(
            "SELECT source_job_id FROM jobs WHERE source_portal = ?", (portal,)
        )
        return {str(row[0]) for row in self.cursor.fetchall() if row[0]}

    def count(self):
        self.cursor.execute("SELECT COUNT(*) FROM jobs")
        return self.cursor.fetchone()[0]

    def export_to_dataframe(self):
        import pandas as pd
        return pd.read_sql_query("SELECT * FROM jobs", self.conn)

    def close(self):
        self.conn.close()
