from sqlalchemy import create_engine, text

e = create_engine("postgresql+psycopg://career_user:career_pass@localhost:5433/career_copilot_test")
with e.connect() as conn:
    r = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND column_name LIKE 'oauth%'"))
    rows = r.fetchall()
    print("OAuth columns:", [row[0] for row in rows])

    r2 = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'candidate_target_tracks'"))
    rows2 = r2.fetchall()
    print("Target tracks columns:", [row[0] for row in rows2])

    r3 = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'user_consents'"))
    rows3 = r3.fetchall()
    print("Consent columns:", [row[0] for row in rows3])
