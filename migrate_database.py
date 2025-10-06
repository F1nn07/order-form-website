import sqlite3
import os

# Path to your database
db_path = os.path.join('data', 'inventory.db')

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Starting database migration...")

# Check if columns already exist
cursor.execute("PRAGMA table_info('order')")
columns = [column[1] for column in cursor.fetchall()]

migrations_needed = []

if 'status' not in columns:
    migrations_needed.append('status')
if 'admin_comment' not in columns:
    migrations_needed.append('admin_comment')
if 'confirmed_at' not in columns:
    migrations_needed.append('confirmed_at')
if 'deleted_at' not in columns:
    migrations_needed.append('deleted_at')

if not migrations_needed:
    print("✅ Database is already up to date!")
    conn.close()
    exit()

print(f"Adding columns: {', '.join(migrations_needed)}")

try:
    # Add new columns
    if 'status' in migrations_needed:
        cursor.execute("ALTER TABLE 'order' ADD COLUMN status VARCHAR(20) DEFAULT 'pending'")
        print("✓ Added 'status' column")
    
    if 'admin_comment' in migrations_needed:
        cursor.execute("ALTER TABLE 'order' ADD COLUMN admin_comment TEXT")
        print("✓ Added 'admin_comment' column")
    
    if 'confirmed_at' in migrations_needed:
        cursor.execute("ALTER TABLE 'order' ADD COLUMN confirmed_at DATETIME")
        print("✓ Added 'confirmed_at' column")
    
    if 'deleted_at' in migrations_needed:
        cursor.execute("ALTER TABLE 'order' ADD COLUMN deleted_at DATETIME")
        print("✓ Added 'deleted_at' column")
    
    # Update existing orders to have 'pending' status
    cursor.execute("UPDATE 'order' SET status = 'pending' WHERE status IS NULL")
    print("✓ Updated existing orders to 'pending' status")
    
    # Commit changes
    conn.commit()
    print("\n✅ Migration completed successfully!")
    print("You can now restart your Flask application.")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Migration failed: {e}")
    print("Your database has been rolled back to its previous state.")

finally:
    conn.close()