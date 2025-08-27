import sqlite3
import os

def update_model_name(db_path, model_id, new_name):
    """
    Updates the name of a model in the database.

    :param db_path: Path to the SQLite database file.
    :param model_id: The ID of the model to update.
    :param new_name: The new name for the model.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if the model exists
        cursor.execute("SELECT model_name FROM models WHERE model_id = ?", (model_id,))
        model = cursor.fetchone()

        if model:
            print(f"Found model with ID '{model_id}'. Current name: '{model[0]}'")
            
            # 1. Update the models table
            cursor.execute("UPDATE models SET model_name = ? WHERE model_id = ?", (new_name, model_id))
            print(f"Updating models table for model_id: {model_id}")

            # 2. Update the battles table for model_a
            cursor.execute("UPDATE battles SET model_a_name = ? WHERE model_a_id = ?", (new_name, model_id))
            if cursor.rowcount > 0:
                print(f"Updated {cursor.rowcount} records in battles table (as model_a).")

            # 3. Update the battles table for model_b
            cursor.execute("UPDATE battles SET model_b_name = ? WHERE model_b_id = ?", (new_name, model_id))
            if cursor.rowcount > 0:
                print(f"Updated {cursor.rowcount} records in battles table (as model_b).")

            conn.commit()
            print(f"Successfully updated all tables for model '{model_id}' to name '{new_name}'")
        else:
            print(f"Error: Model with ID '{model_id}' not found.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # The path to the database is relative to the project root
    db_file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'arena.db')
    
    target_model_id = "gemini-2.5-pro-deepthink"
    new_model_name = "Gemini 2.5 Pro Deepthink"

    update_model_name(db_file_path, target_model_id, new_model_name)