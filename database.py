import sqlite3

DATABASE = "ai_wellness.db"


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():

    conn = get_db_connection()
    cursor = conn.cursor()

    # =================================================
    # USERS TABLE
    # =================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    # =================================================
    # MOOD PREDICTIONS TABLE
    # =================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mood_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sleep_hours REAL NOT NULL,
            stress_level REAL NOT NULL,
            screen_time REAL NOT NULL,
            exercise_minutes REAL NOT NULL,
            energy_level REAL,
            mood TEXT NOT NULL,
            prediction_date TEXT NOT NULL,
            prediction_time TEXT,
            wellness_score REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # =================================================
    # SAFE DATABASE MIGRATION
    # Adds energy_level to an older database
    # without deleting existing records
    # =================================================

    try:

        cursor.execute("""
            ALTER TABLE mood_predictions
            ADD COLUMN energy_level REAL
        """)

        print("energy_level column added successfully!")

    except sqlite3.OperationalError:

        # Column already exists
        pass

    # =================================================
    # WELLNESS GOALS TABLE
    # =================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wellness_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            sleep_goal REAL NOT NULL DEFAULT 8,
            exercise_goal REAL NOT NULL DEFAULT 30,
            screen_time_goal REAL NOT NULL DEFAULT 5,
            stress_goal REAL NOT NULL DEFAULT 4,
            energy_goal REAL NOT NULL DEFAULT 7,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()

    print("SQLite database initialized successfully!")


if __name__ == "__main__":
    init_database()