#CREATING FOR NEW ADDITIONS/GUI
import argparse
import sys
import tkinter as tk

from anonfaces.gui.dbfacegui import FaceDatabaseApp
from anonfaces.gui.gui import AnonymizationApp
from anonfaces.main.main import main as main_script
from anonfaces.helper.cleanup import remove_database
#from main.main import main  #to run as standalone uncomment then comment the one above. see main.py as well

def run_anonfaces_gui():
    root = tk.Tk()
    app = AnonymizationApp(root)
    root.mainloop()

def run_face_database_gui():
    root = tk.Tk()
    app = FaceDatabaseApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close_app)
    root.mainloop()
    

def run_face_dbcleanup():
    remove_database()
   

def main():
    if len(sys.argv) == 1:
        main_script()  # no args so run the main script
        return

    # check args for anything listed
    mode = sys.argv[1]
    if mode == 'gui':
        run_anonfaces_gui()
    elif mode == 'dbgui':
        run_face_database_gui()
    elif mode == 'cleanup':
        run_face_dbcleanup()
    else:
        # pass anything else not from above
        main_script()
        
        
if __name__ == '__main__':
    main()
