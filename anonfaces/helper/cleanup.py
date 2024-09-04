import os
import time

def remove_database():
    
    database_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'database',
    'face_db.sqlite'
    )

    print()
    confirmation = input("Are you sure you want to delete the database? (yes/no) or (y/n): ").strip().lower()

    if confirmation in ['yes', 'y']:
        if os.path.exists(database_path):
            os.remove(database_path)
            print(f"Removed database: {database_path}")
            time.sleep(6)
        else:
            print(f"Database not found: {database_path}")
            time.sleep(3)
    else:
        print("Database deletion canceled.")
        time.sleep(3)

if __name__ == '__main__':
    remove_database()