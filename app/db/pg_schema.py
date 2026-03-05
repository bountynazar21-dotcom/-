# app/db/pg_schema.py
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

            -- legacy/single photo (може лишитися для сумісності)
            photo_file_id TEXT,

            -- ✅ PDF накладної (незалежно від фото)
            invoice_pdf_file_id TEXT,

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

        # ✅ МІГРАЦІЯ: якщо moves вже було створено раніше без invoice_pdf_file_id
        cur.execute("ALTER TABLE moves ADD COLUMN IF NOT EXISTS invoice_pdf_file_id TEXT;")

        # ---- indexes ----
        cur.execute("CREATE INDEX IF NOT EXISTS idx_points_city_id ON points(city_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_point_users_point_id ON point_users(point_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_moves_status ON moves(status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_moves_created_at ON moves(created_at DESC);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_moves_from_point ON moves(from_point_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_moves_to_point ON moves(to_point_id);")

        # move_invoices (історія версій накладних)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS move_invoices (
            id SERIAL PRIMARY KEY,
            move_id INT NOT NULL REFERENCES moves(id) ON DELETE CASCADE,
            version INT NOT NULL,
            photo_file_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(move_id, version)
        );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_move_invoices_move_id ON move_invoices(move_id);")

        # ------------------------------------------------------------
        # ✅ move_invoice_photos (multi-photo) + міграції зі старих схем
        # ------------------------------------------------------------

        # 1) створюємо таблицю (для нових баз)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS move_invoice_photos (
            id SERIAL PRIMARY KEY,
            move_id INT NOT NULL REFERENCES moves(id) ON DELETE CASCADE,
            version INT NOT NULL,
            idx INT,
            photo_file_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_move_invoice_photos_move_id ON move_invoice_photos(move_id);")

        # 2) якщо існувала стара колонка position — переносимо в idx
        cur.execute("""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='move_invoice_photos' AND column_name='position'
          ) THEN
            -- position у тебе був 0..N-1, робимо idx = position+1
            EXECUTE 'UPDATE move_invoice_photos
                     SET idx = COALESCE(idx, position + 1)
                     WHERE idx IS NULL';
          END IF;
        END $$;
        """)

        # 3) якщо idx все ще NULL (або його не було взагалі) — пронумеруємо по (move_id, version)
        cur.execute("""
        WITH ranked AS (
          SELECT id,
                 ROW_NUMBER() OVER (PARTITION BY move_id, version ORDER BY id) AS rn
          FROM move_invoice_photos
        )
        UPDATE move_invoice_photos t
        SET idx = r.rn
        FROM ranked r
        WHERE t.id = r.id AND t.idx IS NULL;
        """)

        # 4) гарантуємо, що idx існує і NOT NULL
        cur.execute("ALTER TABLE move_invoice_photos ADD COLUMN IF NOT EXISTS idx INT;")
        cur.execute("ALTER TABLE move_invoice_photos ALTER COLUMN idx SET NOT NULL;")

        # 5) унікальність (move_id, version, idx)
        # --- MIGRATION: old schema had "position" instead of "idx" ---
        cur.execute("""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='move_invoice_photos' AND column_name='position'
          )
          AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='move_invoice_photos' AND column_name='idx'
          ) THEN
            ALTER TABLE move_invoice_photos RENAME COLUMN position TO idx;
          END IF;
        END $$;
        """)