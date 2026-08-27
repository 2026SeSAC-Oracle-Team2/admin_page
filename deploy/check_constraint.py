from app import db
# PROBLEM_TYPE 체크 제약 확인
rows = db.fetch_all("""
    SELECT constraint_name, search_condition_vc
    FROM all_constraints
    WHERE owner = 'SPEECHAPP_CONTENT' AND constraint_type = 'C'
      AND constraint_name LIKE 'CHK%'
""")
for r in rows:
    print(r["CONSTRAINT_NAME"], "=>", r["SEARCH_CONDITION_VC"])