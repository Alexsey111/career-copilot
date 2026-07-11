from sqlalchemy import create_engine, text
e = create_engine("postgresql+psycopg://career_user:career_pass@localhost:5434/career_copilot")
with e.connect() as conn:
    r = conn.execute(text("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name = 'file_extractions' AND column_name = 'source_file_id'"))
    for row in r:
        print(row)
