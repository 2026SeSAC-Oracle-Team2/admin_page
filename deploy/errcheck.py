from app import db
try:
    db.execute_dml('DELETE FROM "SPEECHAPP_USER"."APP_USER" WHERE "ID" = 999999')
    print("deleted?!")
except Exception as e:
    print(type(e).__name__, "||", repr(str(e))[:220])