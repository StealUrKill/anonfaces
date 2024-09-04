import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
from PIL import Image, ImageTk
import sqlite3
import io
import os

# Will add a bunch of comments as this is my first gui
# One DB - Two Tables - Simple
conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'face_db.sqlite'))

cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS persons (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE
)
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY,
    person_id INTEGER,
    image BLOB,
    FOREIGN KEY (person_id) REFERENCES persons(id)
)
''')
conn.commit()

class FaceDatabaseApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Face Database Manager")
        self.root.resizable(True, True)

        # Top 3 Buttons
        self.button_frame = tk.Frame(root)
        self.button_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        self.open_button = tk.Button(self.button_frame, text="Single Image Enroll", command=self.open_file_dialog)
        self.open_button.pack(side=tk.LEFT, padx=5)
        
        self.batch_button = tk.Button(self.button_frame, text="Batch Image Enroll", command=self.batch_enroll_dialog)
        self.batch_button.pack(side=tk.LEFT, padx=5) 
        
        # DELETE ALL OF COURSE
        self.batch_button = tk.Button(self.button_frame, text="Clear Database", command=self.delete_all_dialog)
        self.batch_button.pack(side=tk.RIGHT, padx=50)
        
        self.content_frame = tk.Frame(root)
        self.content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # vert scrollbar
        self.v_scrollbar = tk.Scrollbar(self.content_frame, orient=tk.VERTICAL)
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # hori scrollbar
        self.h_scrollbar = tk.Scrollbar(self.content_frame, orient=tk.HORIZONTAL)
        self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # canvas inside the content_frame from above
        self.canvas = tk.Canvas(self.content_frame, yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # scrollbars control the canvas
        self.v_scrollbar.config(command=self.canvas.yview)
        self.h_scrollbar.config(command=self.canvas.xview)

        # wigets and images frame
        self.images_frame = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.images_frame, anchor="nw")

        # Bind the frame's configuration event to update the scroll region
        self.images_frame.bind("<Configure>", self.on_frame_configure)

        self.load_images()



    def on_frame_configure(self, event=None):
        # update scroll region to encompass the entire frame size
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.update_root_size()



    def update_root_size(self):
        # find the size of the canvas content
        bbox = self.canvas.bbox("all")
        content_width = bbox[2]  # bbox[2] is the right most coordinate
        content_height = bbox[3] # bbox[3] is the bottom most coordinate
        
        # screen width and height
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # allowed percentage of the screen
        max_width = int(screen_width * .98)
        max_height = int(screen_height * .8)
        
        # set the new size for the root window, limiting to screen size
        new_width = min(content_width + 50, max_width)
        new_height = min(content_height + 60, max_height)
        
        # window centering of screen
        position_x = (screen_width // 2) - (new_width // 2)
        position_y = (screen_height // 2) - (new_height // 2)
    
        # geometry for the root window with position
        self.root.geometry(f"{new_width}x{new_height}+{position_x}+{position_y}")



    def open_file_dialog(self):
        file_path = filedialog.askopenfilename(
            title="Select an Image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png")]
        )

        if file_path:
            self.process_image(file_path)



    def batch_enroll_dialog(self):
        file_paths = filedialog.askopenfilenames(
            title="Select Images",
            filetypes=[("Image files", "*.jpg *.jpeg *.png")]
        )

        if file_paths:
            name = simpledialog.askstring("Input", "Enter the name for these faces:", parent=self.root)
            if name:
                for file_path in file_paths:
                    self.process_image(file_path, name)
            else:
                messagebox.showwarning("No Name", "No name provided, skipping batch enroll.")



    def process_image(self, file_path, name=None):
        if name is None:
            name = simpledialog.askstring("Input", "Enter the name for this face:", parent=self.root)
    
        if name:
            # count how many images are already associated with this person to limit the db
            cursor.execute('SELECT id FROM persons WHERE name = ?', (name,))
            person_id_row = cursor.fetchone()
            if person_id_row:
                person_id = person_id_row[0]
                cursor.execute('SELECT COUNT(*) FROM images WHERE person_id = ?', (person_id,))
                image_count = cursor.fetchone()[0]
                if image_count >= 5:
                    messagebox.showwarning("Limit Reached", "This person already has 5 images. No more can be added.")
                    return
            else:
                cursor.execute('INSERT OR IGNORE INTO persons (name) VALUES (?)', (name,))
                cursor.execute('SELECT id FROM persons WHERE name = ?', (name,))
                person_id = cursor.fetchone()[0]
    
            with open(file_path, 'rb') as file:
                image_data = file.read()
    
            # db insert image associated with the person
            cursor.execute('INSERT INTO images (person_id, image) VALUES (?, ?)', (person_id, image_data))
            conn.commit()
            self.load_images()  # refreshes images
        else:
            messagebox.showwarning("No Name", "No name provided, skipping.")



    def delete_all_dialog(self):
        confirm = messagebox.askyesno("Confirm Delete All", "Are you sure you want to delete all users and images?", parent=self.root)
        
        if confirm:
            try:
                cursor.execute('DELETE FROM images')
                cursor.execute('DELETE FROM persons')
                conn.commit()
                messagebox.showinfo("Success", "All users and images have been deleted.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred while deleting data: {e}", parent=self.root)
            
            self.load_images()  # refreshes images
        else:
            messagebox.showinfo("Cancelled", "Deletion cancelled.", parent=self.root)
    
    

    def load_images(self):
        # clears frame to load
        for widget in self.images_frame.winfo_children():
            widget.destroy()

        cursor.execute('''
            SELECT persons.id, persons.name, images.id, images.image 
            FROM persons 
            JOIN images ON persons.id = images.person_id
            ORDER BY persons.name, images.id
        ''')

        current_name = None
        image_row_frame = None

        for record in cursor.fetchall():
            person_id, name, image_id, image_data = record

            # new row for new name
            if name != current_name:
                current_name = name
                image_row_frame = tk.Frame(self.images_frame)
                image_row_frame.pack(fill=tk.X, pady=5)

                # side by side images
                images_container = tk.Frame(image_row_frame)
                images_container.pack(side=tk.LEFT)

                # name by images
                name_label = tk.Label(image_row_frame, text=name, width=20, anchor="w")
                name_label.pack(side=tk.LEFT, padx=10)

                # contiainer for frame buttons - Rename/Export/Delete...etc
                buttons_frame = tk.Frame(image_row_frame)
                buttons_frame.pack(side=tk.RIGHT, padx=5)

                rename_button = tk.Button(buttons_frame, text="Rename", command=lambda id=image_id: self.rename_person(id))
                rename_button.pack(side=tk.LEFT, padx=5)

                export_button = tk.Button(buttons_frame, text="Export", command=lambda id=person_id: self.export_image(id))
                export_button.pack(side=tk.LEFT, padx=5)

                delete_single_button = tk.Button(buttons_frame, text="Delete Image", command=lambda id=person_id: self.delete_single_image(id))
                delete_single_button.pack(side=tk.LEFT, padx=5)
                
                delete_button = tk.Button(buttons_frame, text="Delete", command=lambda id=image_id: self.delete_all(id))
                delete_button.pack(side=tk.LEFT, padx=5)

            # binary data back to an image
            image_stream = io.BytesIO(image_data)
            img = Image.open(image_stream)
            img.thumbnail((100, 200))  # thumbnail size images
            img_tk = ImageTk.PhotoImage(img)

            # puts the image in the above container
            img_label = tk.Label(images_container, image=img_tk)
            img_label.image = img_tk  # reference to avoid garbage collection
            img_label.pack(side=tk.LEFT, padx=5)



    def rename_person(self, image_id):
        new_name = simpledialog.askstring("Input", "Enter the new name for this face:", parent=self.root)
        
        if new_name:
            # find the current person_id and name associated with the image
            cursor.execute('SELECT person_id FROM images WHERE id = ?', (image_id,))
            current_person_id = cursor.fetchone()
            
            if current_person_id:
                current_person_id = current_person_id[0]
                cursor.execute('SELECT name FROM persons WHERE id = ?', (current_person_id,))
                old_name = cursor.fetchone()[0]
            
                # does person with the new name already exists?
                cursor.execute('SELECT id FROM persons WHERE name = ?', (new_name,))
                existing_person = cursor.fetchone()
            
                if existing_person:
                    new_person_id = existing_person[0]
                    
                    # image count for this person
                    cursor.execute('SELECT COUNT(*) FROM images WHERE person_id = ?', (new_person_id,))
                    image_count = cursor.fetchone()[0]
                    
                    if image_count >= 5:
                        messagebox.showerror("Error", "Cannot add more than 5 images to the same person.")
                        return
                    else:
                        # update the person_id for this image to the existing person - add image into existing
                        cursor.execute('UPDATE images SET person_id = ? WHERE id = ?', (new_person_id, image_id))
                        conn.commit()
                        messagebox.showinfo("Success", f"Image added to existing person '{new_name}'.")
                        
                        # see if the old person_id has any remaining images and delete person is image count is 0
                        cursor.execute('SELECT COUNT(*) FROM images WHERE person_id = ?', (current_person_id,))
                        remaining_images_count = cursor.fetchone()[0]
                        
                        if remaining_images_count == 0:
                            cursor.execute('DELETE FROM persons WHERE id = ?', (current_person_id,))
                            conn.commit()
                            #uncomment for cleanup message
                            #messagebox.showinfo("Cleanup", f"Old name '{old_name}' removed from the database.")
                else:
                    # update the person's name for this image's person - ?
                    cursor.execute('''
                        UPDATE persons 
                        SET name = ? 
                        WHERE id = ?
                    ''', (new_name, current_person_id))
                    conn.commit()
                    messagebox.showinfo("Success", "Name updated.")
            
            self.load_images()  # image refresh
        else:
            messagebox.showwarning("No Name", "No new name provided, modification skipped.")



    def export_image(self, person_id):
        # find the person's name based on person_id
        cursor.execute('SELECT name FROM persons WHERE id = ?', (person_id,))
        person_name = cursor.fetchone()

        if not person_name:
            messagebox.showwarning("No Person Found", "No person found with the specified ID.")
            return
    
        name = person_name[0].replace(" ", "_")  # no junk names please
        # find this persons images
        cursor.execute('SELECT id, image FROM images WHERE person_id = ?', (person_id,))
        images = cursor.fetchall()
        
        if not images:
            messagebox.showwarning("No Images", "No images found for this person.")
            return
    
        directory_path = filedialog.askdirectory(title="Select Directory to Save Images")
    
        if directory_path:
            for index, (image_id, image_data) in enumerate(images):
                # new generated filename from persons.name and images.id
                file_path = os.path.join(directory_path, f"{name}_{image_id}.jpg")
                
                with open(file_path, 'wb') as file:
                    file.write(image_data)
    
            messagebox.showinfo("Success", f"All images exported successfully to {directory_path}.")
        else:
            messagebox.showinfo("Cancelled", "Export cancelled.")



    def delete_all(self, image_id):
        
        # find persons.id from images.id
        cursor.execute('SELECT person_id FROM images WHERE id = ?', (image_id,))
        person_id = cursor.fetchone()[0]
        # now we have the persons.id lets find the name
        cursor.execute('SELECT name FROM persons WHERE id = ?', (person_id,))
        person_name = cursor.fetchone()[0]
        
        confirm = messagebox.askyesno(f"Confirm Deletion of {person_name}", f"Are you sure you want to delete {person_name} and all the associated images?")
        if confirm:
            # get the person associated with the image
            cursor.execute('SELECT person_id FROM images WHERE id = ?', (image_id,))
            person_id = cursor.fetchone()[0]
            if person_id:
                
                # find persons.id from images.id
                cursor.execute('SELECT person_id FROM images WHERE id = ?', (image_id,))
                person_id = cursor.fetchone()[0]
                # now we have the persons.id lets find the name
                cursor.execute('SELECT name FROM persons WHERE id = ?', (person_id,))
                person_name = cursor.fetchone()[0]
                
                # delete this persons images from images
                cursor.execute('DELETE FROM images WHERE person_id = ?', (person_id,))
                # delete this person from person
                cursor.execute('DELETE FROM persons WHERE id = ?', (person_id,))
                conn.commit()
                messagebox.showinfo("Success", f"{person_name} and all associated images were deleted.")
            else:
                messagebox.showwarning("Error", "Failed to find the person associated with this image.")
            
            self.load_images()  # refresh images
        else:
            messagebox.showinfo("Cancelled", "Deletion cancelled.")
        

  
    def delete_single_image(self, person_id):
        print(f"Deleting images for person_id: {person_id}")
        # Open a new window to display all images associated with this person in a grid
        self.image_list_window = tk.Toplevel(self.root)
        self.image_list_window.title("Select Image to Delete")
        
        # canvas to hold the images and scrollbar
        canvas = tk.Canvas(self.image_list_window)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # vert scrollbar
        v_scrollbar = tk.Scrollbar(self.image_list_window, orient=tk.VERTICAL, command=canvas.yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        canvas.configure(yscrollcommand=v_scrollbar.set)
        
        # frame inside the canvas to hold the images - why did i reverse this from other?
        image_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=image_frame, anchor="nw")
        
        image_frame.bind("<Configure>", lambda event: self.update_scroll_region(canvas))
        
        # gets this persons images
        cursor.execute('SELECT id, image FROM images WHERE person_id = ?', (person_id,))
        images = cursor.fetchall()
        
        # shows the images in a grid with 5 columns
        columns = 5
        for index, (image_id, image_data) in enumerate(images):
            image_stream = io.BytesIO(image_data)
            img = Image.open(image_stream)
            img.thumbnail((100, 200))  # thumbnail size
            img_tk = ImageTk.PhotoImage(img)
        
            img_button = tk.Button(image_frame, image=img_tk, command=lambda id=image_id: confirm_delete_image(id))
            img_button.image = img_tk
            img_button.grid(row=index // columns, column=index % columns, padx=5, pady=5)
        
        # Update the window size based on the content
        self.image_list_window.update_idletasks()
        
        # find the size of the content inside the image_frame
        content_width = image_frame.winfo_reqwidth()
        content_height = image_frame.winfo_reqheight()
        
        # screen width and height
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # allowed percentage of the screen
        max_width = int(screen_width * .98)
        max_height = int(screen_height * .8)
        
        # limiting to screen size
        new_width = min(content_width + 20, max_width)
        new_height = min(content_height + 20, max_height)
        
        # window centering of screen
        position_x = (screen_width // 2) - (new_width // 2)
        position_y = (screen_height // 2) - (new_height // 2)
        
        # geometry for the image_list_window with position
        self.image_list_window.geometry(f"{new_width}x{new_height}+{position_x}+{position_y}")


        def confirm_delete_image(image_id):
            # find persons.id from images.id
            cursor.execute('SELECT person_id FROM images WHERE id = ?', (image_id,))
            person_id = cursor.fetchone()[0]
            # now we have the persons.id lets find the name
            cursor.execute('SELECT name FROM persons WHERE id = ?', (person_id,))
            person_name = cursor.fetchone()[0]
            confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete this image from '{person_name}'?", parent=self.image_list_window)
            
            if confirm:
                # find persons.id from images.id
                cursor.execute('SELECT person_id FROM images WHERE id = ?', (image_id,))
                person_id = cursor.fetchone()[0]
                # now we have the persons.id lets find the name
                cursor.execute('SELECT name FROM persons WHERE id = ?', (person_id,))
                person_name = cursor.fetchone()[0]
                #delete image
                cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))
                conn.commit()   
                # make sure this person have no more images because if so they will be deleted. 
                cursor.execute('SELECT COUNT(*) FROM images WHERE person_id = ?', (person_id,))
                remaining_images_count = cursor.fetchone()[0]
                
                if remaining_images_count == 0:
                    # If no other images exist, delete the person
                    cursor.execute('DELETE FROM persons WHERE id = ?', (person_id,))
                    conn.commit()
                    messagebox.showinfo("Person Deleted", f"The person '{person_name}' has been deleted because they have no more associated images.", parent=self.image_list_window)
                else:
                    messagebox.showinfo("Success", f"Image deleted from '{person_name}'.", parent=self.image_list_window)
                
                self.image_list_window.destroy()
                self.load_images()  # refresh images again
        
    
       
    def update_scroll_region(self, canvas):
        canvas.configure(scrollregion=canvas.bbox("all"))
    
    

    def confirm_delete_image(self, image_id):
        confirm = messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this image?")
        if confirm:
            cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))
            conn.commit()
            messagebox.showinfo("Success", "Image deleted.")
            self.image_list_window.destroy()
            self.load_images()  # refresh images for the last time
    


    def close_app(self):
        conn.close()
        self.root.destroy()



if __name__ == "__main__":
    root = tk.Tk()
    app = FaceDatabaseApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close_app)
    root.mainloop()
