from .pg import get_cur


def ensure_schema():
    with get_cur() as cur:
        # users
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            role TEXT DEFAULT 'point',
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)

        # cities
        cur.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        );
        """)

        # points
        cur.execute("""
        CREATE TABLE IF NOT EXISTS points (
            id SERIAL PRIMARY KEY,
            city_id INT NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            UNIQUE(city_id, name)
        );
        """)

        # point_users (1 user -> 1 TT, 1 TT -> багато users)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS point_users (
            telegram_id BIGINT PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
            point_id INT NOT NULL REFERENCES points(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)

        # moves
        cur.execute("""
        CREATE TABLE IF NOT EXISTS moves (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            created_by BIGINT,
            operator_id BIGINT,
            status TEXT DEFAULT 'draft',

            from_point_id INT REFERENCES points(id),
            to_point_id INT REFERENCES points(id),

            photo_file_id TEXT,
            note TEXT,
            invoice_version INT DEFAULT 1,

            handed_at TIMESTAMP,
            handed_by BIGINT,
            received_at TIMESTAMP,
            received_by BIGINT,

            correction_status TEXT DEFAULT 'none',
            correction_note TEXT,
            correction_photo_file_id TEXT,
            correction_by BIGINT,
            correction_at TIMESTAMP
        );
        """)

        # ---- indexes for speed (safe to run many times) ----
        cur.execute("CREATE INDEX IF NOT EXISTS idx_points_city_id ON points(city_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_point_users_point_id ON point_users(point_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_moves_status ON moves(status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_moves_created_at ON moves(created_at DESC);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_moves_from_point ON moves(from_point_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_moves_to_point ON moves(to_point_id);")
