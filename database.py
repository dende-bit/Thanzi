import sqlite3
import hashlib
import os
from contextlib import contextmanager
from config import Config


@contextmanager
def get_db():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def hash_password(plain_text: str) -> str:
    return hashlib.sha256(plain_text.encode("utf-8")).hexdigest()


def init_db():
    with get_db() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS facilities (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                name                TEXT    NOT NULL UNIQUE,
                location            TEXT    NOT NULL,
                available_services  TEXT    NOT NULL DEFAULT '',
                tier                TEXT    NOT NULL DEFAULT 'District Hospital'
                                    CHECK(tier IN ('Village Clinic', 'Community Health Centre', 'District Hospital', 'Central Hospital')),
                status              TEXT    NOT NULL DEFAULT 'ACTIVE'
                                    CHECK(status IN ('ACTIVE', 'INACTIVE', 'FULL')),
                beds_available      INTEGER NOT NULL DEFAULT 0,
                blood_stock         TEXT    NOT NULL DEFAULT 'Available'
                                    CHECK(blood_stock IN ('Available', 'Low', 'Empty')),
                maternity_beds      INTEGER NOT NULL DEFAULT 0,
                malnutrition_ward   INTEGER NOT NULL DEFAULT 0,
                distance_km         REAL    NOT NULL DEFAULT 0,
                created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                username        TEXT    NOT NULL UNIQUE,
                password_hash   TEXT    NOT NULL,
                full_name       TEXT    NOT NULL,
                role            TEXT    NOT NULL
                                CHECK(role IN ('ADMIN', 'CHW', 'SUPERVISOR', 'DHO')),
                catchment_area  TEXT    NOT NULL DEFAULT '',
                facility_id     INTEGER REFERENCES facilities(id)
                                ON UPDATE CASCADE ON DELETE SET NULL,
                status          TEXT    NOT NULL DEFAULT 'ACTIVE'
                                CHECK(status IN ('ACTIVE', 'SUSPENDED', 'INACTIVE')),
                created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                national_id             TEXT    PRIMARY KEY,
                name                    TEXT    NOT NULL,
                age_months              INTEGER NOT NULL DEFAULT 0,
                gender                  TEXT    NOT NULL DEFAULT 'Unknown'
                                        CHECK(gender IN ('Male', 'Female', 'Unknown')),
                village                 TEXT    NOT NULL DEFAULT '',
                registered_by_chw_id    INTEGER REFERENCES users(id)
                                        ON UPDATE CASCADE ON DELETE SET NULL,
                created_at              TEXT    NOT NULL DEFAULT (datetime('now')),
                last_updated_at         TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS encounters (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id              TEXT    NOT NULL
                                        REFERENCES patients(national_id)
                                        ON UPDATE CASCADE ON DELETE CASCADE,
                chw_id                  INTEGER NOT NULL
                                        REFERENCES users(id)
                                        ON UPDATE CASCADE ON DELETE CASCADE,
                timestamp               TEXT    NOT NULL DEFAULT (datetime('now')),
                symptoms_original       TEXT    NOT NULL DEFAULT '',
                symptoms_english        TEXT    NOT NULL DEFAULT '',
                detected_language       TEXT    NOT NULL DEFAULT 'Unknown',
                risk_level              TEXT    NOT NULL DEFAULT 'LOW'
                                        CHECK(risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
                iccm_protocol_applied   TEXT    NOT NULL DEFAULT '',
                assessment_notes        TEXT    NOT NULL DEFAULT '',
                recommended_action      TEXT    NOT NULL DEFAULT '',
                reasoning               TEXT    NOT NULL DEFAULT '',
                referral_needed         INTEGER NOT NULL DEFAULT 0,
                escalated_to_supervisor INTEGER NOT NULL DEFAULT 0,
                supervisor_id           INTEGER REFERENCES users(id)
                                        ON UPDATE CASCADE ON DELETE SET NULL,
                supervisor_feedback     TEXT    NOT NULL DEFAULT '',
                escalated_to_dho        INTEGER NOT NULL DEFAULT 0,
                dho_id                  INTEGER REFERENCES users(id)
                                        ON UPDATE CASCADE ON DELETE SET NULL,
                target_facility_id      INTEGER REFERENCES facilities(id)
                                        ON UPDATE CASCADE ON DELETE SET NULL,
                referral_urgency        TEXT    NOT NULL DEFAULT ''
                                        CHECK(referral_urgency IN ('', 'ROUTINE', 'URGENT', 'EMERGENCY')),
                chichewa_family_message TEXT    NOT NULL DEFAULT '',
                follow_up_days          INTEGER NOT NULL DEFAULT 3,
                record_closed           INTEGER NOT NULL DEFAULT 0,
                outcome                 TEXT    NOT NULL DEFAULT 'ONGOING'
                                        CHECK(outcome IN ('ONGOING', 'REFERRED', 'HEALED', 'REFERRED_COMPLETED', 'DECEASED'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS medicine_stock (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chw_id      INTEGER NOT NULL REFERENCES users(id)
                            ON UPDATE CASCADE ON DELETE CASCADE,
                reported_at TEXT    NOT NULL DEFAULT (datetime('now')),
                ors         INTEGER NOT NULL DEFAULT 0,
                paracetamol INTEGER NOT NULL DEFAULT 0,
                amoxicillin INTEGER NOT NULL DEFAULT 0,
                malaria_rdt INTEGER NOT NULL DEFAULT 0,
                zinc        INTEGER NOT NULL DEFAULT 0,
                notes       TEXT    NOT NULL DEFAULT ''
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_encounters_patient ON encounters(patient_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_encounters_chw ON encounters(chw_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_encounters_risk ON encounters(risk_level)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_encounters_timestamp ON encounters(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_patients_village ON patients(village)")

        facilities_seed = [
            ("Bwaila District Hospital", "Area 3, Lilongwe",
             "Maternity, Paediatrics, Surgery, ART, TB, Malnutrition",
             "District Hospital", "ACTIVE", 18, "Available", 8, 1, 4.2),
            ("Area 25 Health Centre", "Area 25, Lilongwe",
             "OPD, ANC, Immunisation, Family Planning, HIV Testing",
             "Community Health Centre", "ACTIVE", 6, "Low", 2, 0, 6.8),
            ("Mitundu Community Hospital", "Mitundu, Lilongwe Rural",
             "OPD, Maternity, Under-5 Clinic, ART, Nutrition",
             "Community Health Centre", "ACTIVE", 12, "Available", 4, 1, 22.5),
        ]

        for fac in facilities_seed:
            conn.execute("""
                INSERT INTO facilities
                    (name, location, available_services, tier, status,
                     beds_available, blood_stock, maternity_beds,
                     malnutrition_ward, distance_km)
                SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                WHERE NOT EXISTS (SELECT 1 FROM facilities WHERE name = ?)
            """, (*fac, fac[0]))

        admin_hash = hash_password("thanzi_admin_2026")
        conn.execute("""
            INSERT INTO users (username, password_hash, full_name, role, catchment_area, status)
            SELECT 'admin', ?, 'System Administrator', 'ADMIN', 'All Districts', 'ACTIVE'
            WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin')
        """, (admin_hash,))

    print(f"[Thanzi] Database initialised at: {os.path.abspath(Config.DATABASE_PATH)}")
    print(f"[Thanzi] Schema: facilities, users, patients, encounters, medicine_stock")
    print(f"[Thanzi] Seed data: 3 facilities, 1 admin account")


def verify_db():
    with get_db() as conn:
        tables = ["facilities", "users", "patients", "encounters", "medicine_stock"]
        print("\n[Thanzi] Database verification:")
        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {count} rows")
    print()


if __name__ == "__main__":
    init_db()
    verify_db()