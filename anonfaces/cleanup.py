import os

def remove_database():
    db_path = os.path.join(os.path.dirname(__file__), 'face_db.sqlite')
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed database: {db_path}")
    else:
        print(f"Database not found: {db_path}")

if __name__ == '__main__':
    remove_database()
