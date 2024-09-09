import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import subprocess
import signal
import sys
import os
import platform
from datetime import datetime
import anonfaces
from anonfaces import __version__

class AnonymizationApp:
    def __init__(self, root):
        self.root = root
        if root.tk.call("tk", "windowingsystem") == "x11": # linux needs special sizing for me. need input from others
            scaling_factor = 1
            root.tk.call('tk', 'scaling', scaling_factor)
            default_font = ("TkDefaultFont", 8)
            root.option_add("*Font", default_font)
        window_width = 800
        window_height = 700
        self.root.title(f"Anonfaces Anonymization Tool - v{__version__}")  
        self.log_text = None  # log widget is not ready initially
        self.log_queue = []  # queue to store log messages before the form is ready
        self.form_ready = False  # whether the form is fully initialized
        
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        # find the x and y coordinates to center the window
        position_x = (screen_width // 2) - (window_width // 2)
        position_y = (screen_height // 2) - (window_height // 2)
        
        # set center of the window (widthxheight+x+y)
        self.root.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")
        
        #disabling resize due to scaling issues - might look into creating new application later with auto sizing widgets and frames
        self.root.resizable(False, False)
        
        self.tooltips_enabled = True # tooltip enabled by default
        self.tooltips = []  # store all tooltips so i dont have to label all for the toggle.
        
        self.create_file_selection()

        self.create_options()

        self.control_frame = tk.Frame(root)
        self.control_frame.pack(pady=0)
        
        self.start_button = tk.Button(self.control_frame, text="Start Anonymization", command=self.start_anonymization)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(self.control_frame, text="Stop Anonymization", command=self.stop_anonymization)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.facedbgui_button = tk.Button(self.control_frame, text="Face Database GUI", command=self.facedbgui_launch)
        self.facedbgui_button.pack(side=tk.LEFT, padx=5)
        
        self.clearoptions_button = tk.Button(self.control_frame, text="Clear All Options", command=self.clear_options_launch)
        self.clearoptions_button.pack(side=tk.LEFT, padx=5)
        
        self.progress = ttk.Progressbar(root, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", pady=5)

        #self.log_text = tk.Text(root, width=98, height=15, state="disabled")
        #made the log text somewhat smaller to keep the width down. left stock above
        self.log_text = tk.Text(root, width=113, height=9.5, state="disabled", font=("TkDefaultFont", 9))
        self.log_text.pack(pady=0)
        
        # right-click menu (popup menu)
        self.log_menu = tk.Menu(self.log_text, tearoff=0)
        self.log_menu.add_command(label="Copy", command=self.copy_log)
        self.log_menu.add_command(label="Save", command=self.save_log)

        # right-click event to the log_text widget
        self.log_text.bind("<Button-3>", self.show_log_menu)
        
        # stdout and stderr to the log_text
        sys.stdout = TextRedirector(self.log_text, "stdout")
        sys.stderr = TextRedirector(self.log_text, "stderr")
        
        # the GUI initialized set form_ready to True
        self.form_ready = True
    
        # handle any queued log messages after form is ready
        self.process_log_queue()

        
    def copy_log(self):
        # Enable log_text temporarily to copy the content
        self.log_text.config(state="normal")
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log_text.get("1.0", tk.END))
        self.log_text.config(state="disabled")


    def save_log(self):
        # auto-populate the file name with app name, version, and current date in the save field
        app_name = "Anonfaces"
        version = __version__  # Version from your module
        current_date = datetime.now().strftime("%Y-%m-%d")
        default_filename = f"{app_name}_v{version}_{current_date}.txt"

        # open the file dialog to save the log content
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt", 
            filetypes=[("Text files", "*.txt")],
            initialfile=default_filename  # Set the default filename
        )
        if file_path:
            # enable log_text temporarily to read the content
            self.log_text.config(state="normal")
            with open(file_path, 'w') as f:
                f.write(self.log_text.get("1.0", tk.END))
            self.log_text.config(state="disabled")


    def show_log_menu(self, event):
        # shows the right-click log menu at the current mouse position
        try:
            self.log_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.log_menu.grab_release()

    
    def show_help(self):
        help_text = """
        Anonfaces Anonymization Tool - Info:
    
        1. Input:
           File path(s) or camera device name. It is possible to pass multiple paths by separating them
           by spaces or by using shell expansion (e.g. `$ anonfaces vids/*.mp4`). Alternatively, you
           can pass a directory as input, and all files in the directory will be used. If a camera is
           installed, start a live demo with `$ anonfaces cam` (shortcut for `$ anonfaces -p '<video0>'`).
           
           INFO:
           Short press to open file, long press to open directory.
           Automatically clears output if an output extension is present when input directory is set.
           Automatically clears output if an output directory is present when input file is set.
                       
        2. Output:
           Output file name. Defaults to input path + postfix "_anonymized".
           
           INFO:
           Automatically switches between file and directory from input.
           If a file is selected from the input, only the name of the file is needed as the output will
           automatically match the extension from the input file.
            
        3. Threshold:
           Detection threshold. Default is 0.2.
            
        4. Scale:
           Downscale images for inference. Format WxH (e.g., scale 640x360).
            
        5. Preview:
           Enable live preview GUI (may reduce performance).
            
        6. Boxes:
           Use boxes instead of ellipse masks.
            
        7. Detection Scores:
           Draw detection scores onto outputs.
            
        8. Mask Scale:
           Scale factor for face masks. Default: 1.3.
            
        9. Replace With:
           Face anonymization filter mode. Options: 'blur', 'solid', 'none', 'img', 'mosaic'. Default: 'blur'.
            
        10. Replace Image:
            Custom image for face replacement (requires replacewith img).
            
        11. Mosaic Size:
            Mosaic size for face replacement. Default: 20.
            
        12. Face Recognition:
            Face Recognition: Enable face recognition to not blur faces in Face GUI Database..
            Face Recognition Name: Enable face recognition names from image name in Face GUI Database.
            Face Recognition GUI: Launch face database GUI.
            Face Recognition Threshold: Set face recognition threshold. Default: 0.60.
            
        13. Audio:
            Distory Audio: Enable audio distortion in output video.
            Keep Audio: Keep audio from the video source.
            Copy Audio Codec: Keep the audio codec from the source.
            
        14. FFmpeg Config:
            JSON format for FFmpeg encoding options. Default: '{"codec": "libx264"}'.
            Windows example in GUI --ffmpeg-config {"fps": 10, "bitrate": "1000k"}
            See https://imageio.readthedocs.io/en/stable/format_ffmpeg.html#parameters-for-saving
            
        15. Backend:
            Select ONNX model execution backend. Options: 'auto', 'onnxrt', 'opencv'. Default: 'auto'.
            
        16. Execution Provider:
            Override the ONNX runtime execution provider. Only used if backend is onnxrt.
            If not specified, the presumably fastest available one will be automatically selected.
            See - https://onnxruntime.ai/docs/execution-providers/
                        
        17. Additional Options:
            Show Info: Show file input/output locations and ffmpeg command.
            Keep Metadata: Keep metadata from the original image. Default: False.
        """

        help_window = tk.Toplevel(self.root)
        help_window.title("Help")
        
        window_width = 950
        window_height = 750
    
        # get the screen dimensions to calculate the center position
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
    
        # find the x and y coordinates to center the window
        position_x = (screen_width // 2) - (window_width // 2)
        position_y = (screen_height // 2) - (window_height // 2)
    
        # set center of the window (widthxheight+x+y)
        help_window.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")
        
        # deciding to disable resize due to scaling issues.
        help_window.resizable(False, False)
        
        # frame to hold the text and scrollbar
        frame = tk.Frame(help_window)
        frame.pack(fill="both", expand=True)
    
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
    
        # widget for the help text
        text_widget = tk.Text(frame, wrap="word", yscrollcommand=scrollbar.set)
        text_widget.pack(side="left", fill="both", expand=True)
    
        # help text
        text_widget.insert(tk.END, help_text)
    
        # scrollbar for the text widget
        scrollbar.config(command=text_widget.yview)
    
        # text selection and copying but disable editing
        def disable_editing(event):
            return "break"  #prevents text from being modified
    
        # set certain keys to disable editing
        text_widget.bind("<Key>", disable_editing)
        text_widget.bind("<BackSpace>", disable_editing)
        text_widget.bind("<Delete>", disable_editing)
    
        # ctrl+c to copy the selected text
        text_widget.bind("<Control-c>", lambda e: text_widget.event_generate("<<Copy>>"))
    
        # right-click (context) menu for copying
        def show_context_menu(event):
            context_menu.tk_popup(event.x_root, event.y_root)
    
        context_menu = tk.Menu(help_window, tearoff=0)
        context_menu.add_command(label="Copy", command=lambda: text_widget.event_generate("<<Copy>>"))
    
        # right-click to show the context menu
        text_widget.bind("<Button-3>", show_context_menu)
    
        close_button = ttk.Button(help_window, text="Close", command=help_window.destroy)
        close_button.pack(pady=10)
    
        # help window modal
        help_window.transient(self.root)
        help_window.grab_set()
    
    
    def create_file_selection(self):
        self.file_frame = tk.Frame(self.root)
        self.file_frame.pack(pady=10, fill="x")

        self.help_button = tk.Button(self.file_frame, text="Help", command=self.show_help)
        self.help_button.place(x=740, y=7, height=26)
        
        # toggle button to enable/disable tooltips
        self.toggle_button = tk.Button(self.file_frame, text="Toogle Tooltips", command=self.toggle_tooltips)
        self.toggle_button.place(x=683.5, y=42, height=26)

        self.input_entry = tk.Entry(self.file_frame, width=70)
        self.input_entry.place(x=120, y=7, height=24, width=470)
        self.tooltips.append(ToolTip(self.input_entry, "To use cam, input cam here."))

        self.output_entry = tk.Entry(self.file_frame, width=70)
        self.output_entry.place(x=120, y=42, height=26, width=470)

        self.output_button = tk.Button(self.file_frame, text="Output", command=self.browse_output)
        self.output_button.grid(row=1, column=0, padx=40, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.output_button, 
            """Automatically switches between file and directory from input.
If file is selected, only the name of the file is needed as the
output will automatically match the extension from the input."""
            ))

        # switches between input and directory - names kept short
        self.select_type = tk.StringVar(value="file")
        self.select_button = tk.Button(self.file_frame, text="Input", command=self.select_path)
        self.select_button.grid(row=0, column=0, padx=40, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.select_button,
            """Short press to open file, long press to open directory.
Automatically clears output is output extension is present"""
            ))
        self.select_button.bind('<ButtonPress-1>', self.start_long_press)
        self.select_button.bind('<ButtonRelease-1>', self.end_long_press)

        self.long_press_timer = None
        self.long_press_duration = 300



    def create_options(self):
        self.options_frame = tk.Frame(self.root)
        self.options_frame.pack(pady=10, fill="x")  # fill="x" makes the frame expand horizontally
        
        self.options_frame.columnconfigure(0, weight=1)
        #self.options_frame.columnconfigure(1, weight=1)
        #self.options_frame.columnconfigure(2, weight=1)
        self.options_frame.columnconfigure(3, weight=1)

        # right column options/checkboxes
        self.preview_var = tk.BooleanVar()
        self.preview_check = tk.Checkbutton(self.options_frame, text="Enable Preview", variable=self.preview_var)
        self.preview_check.grid(row=0, column=2, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.preview_check, "Enable live preview GUI (can decrease performance)."))

        self.boxes_var = tk.BooleanVar()
        self.boxes_check = tk.Checkbutton(self.options_frame, text="Use Boxes Instead of Ellipse", variable=self.boxes_var)
        self.boxes_check.grid(row=1, column=2, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.boxes_check, "Use boxes instead of ellipse masks."))

        self.draw_scores_var = tk.BooleanVar()
        self.draw_scores_check = tk.Checkbutton(self.options_frame, text="Draw Detection Scores", variable=self.draw_scores_var)
        self.draw_scores_check.grid(row=2, column=2, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.draw_scores_check, "Draw detection scores onto outputs and previews."))

        self.face_recog_var = tk.BooleanVar()
        self.face_recog_check = tk.Checkbutton(self.options_frame, text="Enable Face Recognition", variable=self.face_recog_var)
        self.face_recog_check.grid(row=3, column=2, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.face_recog_check, "Enable face recognition to not blur faces in Face GUI Database."))

        self.fr_name_var = tk.BooleanVar()
        self.fr_name_check = tk.Checkbutton(self.options_frame, text="Enable Face Recognition With Names", variable=self.fr_name_var)
        self.fr_name_check.grid(row=4, column=2, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.fr_name_check, "Enable face recognition names from image name in Face GUI Database."))

        self.distort_audio_var = tk.BooleanVar()
        self.distort_audio_check = tk.Checkbutton(self.options_frame, text="Distort Audio", variable=self.distort_audio_var)
        self.distort_audio_check.grid(row=5, column=2, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.distort_audio_check, "Enable audio distortion for the output video. Applies pitch shift and gain effects to the audio."))

        self.keep_audio_var = tk.BooleanVar()
        self.keep_audio_check = tk.Checkbutton(self.options_frame, text="Keep Audio", variable=self.keep_audio_var)
        self.keep_audio_check.grid(row=6, column=2, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.keep_audio_check, "Keep audio from video source file and copy it over to the output (only applies to videos)."))

        self.copy_acodec_var = tk.BooleanVar()
        self.copy_acodec_check = tk.Checkbutton(self.options_frame, text="Copy Audio Codec", variable=self.copy_acodec_var)
        self.copy_acodec_check.grid(row=7, column=2, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.copy_acodec_check, "Keep the audio codec from video source file."))
        
        self.info_var = tk.BooleanVar()
        self.info_check = tk.Checkbutton(self.options_frame, text="Show Info", variable=self.info_var)
        self.info_check.grid(row=8, column=2, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.info_check, "Shows file input/output location and ffmpeg command. Default is off the clear clutter."))

        self.keep_metadata_var = tk.BooleanVar()
        self.keep_metadata_check = tk.Checkbutton(self.options_frame, text="Keep Metadata", variable=self.keep_metadata_var)
        self.keep_metadata_check.grid(row=9, column=2, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.keep_metadata_check, "Keep metadata of the original image. Default : False."))

        # left colummn options
        self.thresh_label = tk.Label(self.options_frame, text="Detection Threshold:")
        self.thresh_label.grid(row=0, column=1, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.thresh_label, "Detection threshold (tune this to trade off between false positive and false negative rate). Default: 0.2"))
        
        self.thresh_entry = tk.Entry(self.options_frame, width=17)
        self.thresh_entry.grid(row=0, column=1, padx=197, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.thresh_entry, "Detection threshold (tune this to trade off between false positive and false negative rate). Default: 0.2"))
        
        self.scale_label = tk.Label(self.options_frame, text="Scale (WxH):")
        self.scale_label.grid(row=1, column=1, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.scale_label, "Downscale images for network inference to this size (format: WxH, example: 640x360)."))
        
        self.scale_entry = tk.Entry(self.options_frame, width=17)
        self.scale_entry.grid(row=1, column=1, padx=197, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.scale_entry, "Downscale images for network inference to this size (format: WxH, example: 640x360)."))

        self.replacewith_label = tk.Label(self.options_frame, text="Replace With:")
        self.replacewith_label.grid(row=2, column=1, padx=0, pady=5, sticky="w")  
        self.tooltips.append(ToolTip(self.replacewith_label, 
            """Anonymization filter mode for face regions. "blur" applies a strong
gaussian blurring, "solid" draws a solid black box, "none" leaves the
input unchanged, "img" replaces the face with a custom image, and
"mosaic" replaces the face with mosaic. Default: "blur"."""
            ))#PS I HATE THE WAY THIS FORMATS IN THE TOOLTIP

        self.replacewith_var = tk.StringVar(value="")
        self.replacewith_menu = tk.OptionMenu(self.options_frame, self.replacewith_var, "blur", "solid", "none", "img", "mosaic")
        self.replacewith_menu.grid(row=2, column=1, padx=194, pady=5, sticky="w")
        self.replacewith_menu.config(width=11)
        self.tooltips.append(MenuToolTip(self.replacewith_menu, 
            """Anonymization filter mode for face regions. "blur" applies a strong
gaussian blurring, "solid" draws a solid black box, "none" leaves the
input unchanged, "img" replaces the face with a custom image, and
"mosaic" replaces the face with mosaic. Default: "blur"."""
            ))#PS I HATE THE WAY THIS FORMATS IN THE TOOLTIP

        self.replaceimg_button = tk.Button(self.options_frame, text="Replace Image", command=self.browse_replaceimg)
        self.replaceimg_button.grid(row=3, column=1, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.replaceimg_button, "Anonymization image for face regions. Requires --replacewith img option from above"))
        
        self.replaceimg_entry = tk.Entry(self.options_frame, width=33)
        self.replaceimg_entry.grid(row=3, column=1, padx=100, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.replaceimg_entry, "Anonymization image for face regions. Requires --replacewith img option from above"))
        
        self.mosaicsize_label = tk.Label(self.options_frame, text="Mosaic Size:")
        self.mosaicsize_label.grid(row=4, column=1, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.mosaicsize_label, "Setting the mosaic size. Requires --replacewith mosaic option from above. Default: 20"))
        
        self.mosaicsize_entry = tk.Entry(self.options_frame, width=17)
        self.mosaicsize_entry.grid(row=4, column=1, padx=197, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.mosaicsize_entry, "Setting the mosaic size. Requires --replacewith mosaic option from above. Default: 20"))
        
        self.maskscale_label = tk.Label(self.options_frame, text="Mask Scale:")
        self.maskscale_label.grid(row=5, column=1, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.maskscale_label, "Scale factor for face masks, to make sure that masks cover the complete face. Default: 1.3."))
        
        self.maskscale_entry = tk.Entry(self.options_frame, width=17)
        self.maskscale_entry.grid(row=5, column=1, padx=197, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.maskscale_entry, "Scale factor for face masks, to make sure that masks cover the complete face. Default: 1.3."))

        self.fr_thresh_label = tk.Label(self.options_frame, text="Face Recognition Threshold:")
        self.fr_thresh_label.grid(row=6, column=1, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.fr_thresh_label, "Set the face recognition threshold. Default is 0.60"))
        
        self.fr_thresh_entry = tk.Entry(self.options_frame, width=17)
        self.fr_thresh_entry.grid(row=6, column=1, padx=197, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.fr_thresh_entry, "Set the face recognition threshold. Default is 0.60"))

        self.backend_label = tk.Label(self.options_frame, text="Backend:")
        self.backend_label.grid(row=7, column=1, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.backend_label, "Backend for ONNX model execution. Default: auto (prefer onnxrt if available)"))
        
        self.backend_var = tk.StringVar(value="")
        self.backend_menu = tk.OptionMenu(self.options_frame, self.backend_var, "auto", "onnxrt", "opencv")
        self.backend_menu.grid(row=7, column=1, padx=194, pady=5, sticky="w")
        self.backend_menu.config(width=11)
        self.tooltips.append(MenuToolTip(self.backend_menu, "Backend for ONNX model execution. Default: auto (prefer onnxrt if available)"))

        self.ep_label = tk.Label(self.options_frame, text="Execution Provider:")
        self.ep_label.grid(row=8, column=1, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.ep_label, 
            """Override onnxrt execution provider see
https://onnxruntime.ai/docs/execution-providers/
If not specified, the presumably fastest available one will
be automatically selected. Only used if backend is onnxrt"""
            ))#PS I HATE THE WAY THIS FORMATS IN THE TOOLTIP

        available_providers = self.get_available_execution_providers()
        self.ep_var = tk.StringVar(value="")
        self.ep_menu = tk.OptionMenu(self.options_frame, self.ep_var, *available_providers)
        self.ep_menu.grid(row=8, column=1, padx=110, pady=5, sticky="w")
        self.ep_menu.config(width=25)
        self.tooltips.append(MenuToolTip(self.ep_menu, 
            """Override onnxrt execution provider see
https://onnxruntime.ai/docs/execution-providers/
If not specified, the presumably fastest available one will
be automatically selected. Only used if backend is onnxrt"""
            ))#PS I HATE THE WAY THIS FORMATS IN THE TOOLTIP

        self.ffmpeg_config_label = tk.Label(self.options_frame, text="FFmpeg Config (JSON):")
        self.ffmpeg_config_label.grid(row=9, column=1, padx=0, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.ffmpeg_config_label, 
            """FFMPEG config arguments for encoding output videos.
This argument is expected in JSON notation. For a list
of possible options, refer to the ffmpeg-imageio docs.
Default: '{"codec": "libx264"}'
Windows example in GUI --ffmpeg-config {"fps": 10, "bitrate": "1000k"}."""
            ))#PS I HATE THE WAY THIS FORMATS IN THE TOOLTIP
            
        self.ffmpeg_config_entry = tk.Entry(self.options_frame, width=27)
        self.ffmpeg_config_entry.grid(row=9, column=1, padx=136, pady=5, sticky="w")
        self.tooltips.append(ToolTip(self.ffmpeg_config_entry, 
            """FFMPEG config arguments for encoding output videos.
This argument is expected in JSON notation. For a list
of possible options, refer to the ffmpeg-imageio docs.
Default: '{"codec": "libx264"}'
Windows example in GUI --ffmpeg-config {"fps": 10, "bitrate": "1000k"}."""
            ))#PS I HATE THE WAY THIS FORMATS IN THE TOOLTIP
        

    def get_available_execution_providers(self):
        try:
            import onnx
            import onnxruntime
            providers = onnxruntime.get_available_providers()
            return providers if providers else ["No Providers Available"]
        except ImportError as e:
            self.log_message(f"Import Error: {e}")
            # onnxruntime is not installed, return this message
            return ["onnxruntime not available"]
        except Exception as e:
            # incase onnxruntime is not available or fails
            print(f"Error retrieving providers: {e}")
            return ["No Providers Available"]
   
   
    def start_long_press(self, event):
        # timer from create_file_selection
        self.long_press_timer = self.root.after(self.long_press_duration, self.switch_to_directory)


    def end_long_press(self, event):
        # cancels long press if button was released before timer
        if self.long_press_timer:
            self.root.after_cancel(self.long_press_timer)
            self.long_press_timer = None
            # normal button click
            if self.select_type.get() == "file":
                self.select_path()


    def switch_to_directory(self):
        # switches to directory to keep gui clean
        self.select_type.set("directory")
        self.select_button.config(text="Directory")

  
    def select_path(self):
        output_path = self.output_entry.get()
        if self.select_type.get() == "file":
            input_path = filedialog.askopenfilename()
            if input_path:
                self.input_entry.delete(0, tk.END)
                self.input_entry.insert(0, input_path)
                if os.path.isdir(output_path):
                    # clears the output_entry if the current output has a file extension input the input is a directory
                    messagebox.showinfo("File Selected", "Input file detected! \n\nClearing output due to output directory set.")
                    self.output_entry.delete(0, tk.END)                
        else:
            input_path = filedialog.askdirectory()
            if input_path:
                self.input_entry.delete(0, tk.END)
                self.input_entry.insert(0, input_path)
                
                # clears output_entry if input is a directory and output contains a file extension
                output_path = self.output_entry.get()
                if output_path and os.path.splitext(output_path)[1]:  # Check if the output path has an extension
                    messagebox.showinfo("Directory Selected", "Output extension detected!\n\nClearing output due to input directory set.")
                    self.output_entry.delete(0, tk.END)                
        # resets the button back to a file selection after completing the action
        self.select_type.set("file")
        self.select_button.config(text="Input")

    
    def browse_output(self):
        input_path = self.input_entry.get()
        if input_path:
            # check if the input path is a directory and ask to set output as a directory
            if os.path.isdir(input_path):
                messagebox.showinfo("Directory Selected", "Input directory detected! \n\nPlease choose an output directory.")
                output_dir = filedialog.askdirectory(title="Select Output Directory")
                
                if output_dir:
                    self.output_entry.delete(0, tk.END)
                    self.output_entry.insert(0, output_dir)
                    
            else:
                # if it's a file, get the file extension
                input_ext = os.path.splitext(input_path)[1]
                output_path = filedialog.asksaveasfilename(title="Select Output File")
                
                # if output file is selected, append the input file extension to the output file extension if needed
                if output_path:
                    if not output_path.endswith(input_ext):
                        output_path += input_ext
                    
                    self.output_entry.delete(0, tk.END)
                    self.output_entry.insert(0, output_path)


    def toggle_tooltips(self):
        self.tooltips_enabled = not self.tooltips_enabled
        for tooltip in self.tooltips:
            tooltip.toggle(self.tooltips_enabled)

        # update the tooltip button text
        if self.tooltips_enabled:
            self.toggle_button.config(text="Disable Tooltips")
        else:
            self.toggle_button.config(text="Enable Tooltips")
    
    
    def browse_replaceimg(self):
        replaceimg_path = filedialog.askopenfilename(title="Select Replace Image")
        self.replaceimg_entry.delete(0, tk.END)
        self.replaceimg_entry.insert(0, replaceimg_path)
 
 
    def facedbgui_launch(self):
        cmd = ["anonfaces", "--face-gui"]
        subprocess.run(cmd)
        

    def log_message(self, message):
        if not self.form_ready:
            # queue message if the form is not ready
            self.log_queue.append(message)
        else:
            # send message to the log widget
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")


    def process_log_queue(self):
        if self.form_ready:
            for message in self.log_queue:
                self.log_text.config(state="normal")
                self.log_text.insert(tk.END, message + "\n")
                self.log_text.see(tk.END)
                self.log_text.config(state="disabled")
            #  clear queue after processing
            self.log_queue.clear()

    
    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")


    def start_anonymization(self):
        self.clear_log()
        options = self.collect_options()
        threading.Thread(target=self.run_anonymization, args=(options,)).start()


    def stop_anonymization(self):
        if hasattr(self, 'process') and self.process is not None:
            if self.process.poll() is None:
                try:
                    self.log_message("Attempting to stop the process...")
                    if platform.system() == "Windows":
                        #import win32api
                        #import win32con
                        # CTRL+C to stop it from main.py script
                        #win32api.GenerateConsoleCtrlEvent(win32con.CTRL_C_EVENT, 0)
                        #seems to work without this now.
                        self.process_stopped = True
                    else:
                        self.process.terminate()
                        self.process_stopped = True
                except ImportError as e:
                    self.log_message(f"Import Error: {e}")
                except Exception as e:
                    self.log_message(f"Error stopping the process: {e}")
                finally:
                    self.process.terminate()
                    self.process.wait()
                    self.process = None
                    self.progress.stop()
                    self.log_message("Anonymization stopped.")
    
    
    def clear_options_launch(self):
        # clears the file selection fields
        self.input_entry.delete(0, tk.END)
        self.output_entry.delete(0, tk.END)
        self.replaceimg_entry.delete(0, tk.END)

        # set the options fields
        self.thresh_entry.delete(0, tk.END)
        self.scale_entry.delete(0, tk.END)
        self.mosaicsize_entry.delete(0, tk.END)
        self.maskscale_entry.delete(0, tk.END)
        self.fr_thresh_entry.delete(0, tk.END)
        self.ffmpeg_config_entry.delete(0, tk.END)

        # set checkboxes to unchecked
        self.preview_var.set(False)
        self.boxes_var.set(False)
        self.draw_scores_var.set(False)
        self.face_recog_var.set(False)
        self.fr_name_var.set(False)
        self.distort_audio_var.set(False)
        self.keep_audio_var.set(False)
        self.copy_acodec_var.set(False)
        self.info_var.set(False)
        self.keep_metadata_var.set(False)

        # set options with menus to default values
        self.replacewith_var.set("")
        self.backend_var.set("")
        self.ep_var.set("")
    
      
    def collect_options(self):
        options = {
            "input": self.input_entry.get(),
            "output": self.output_entry.get(),
            "thresh": self.thresh_entry.get(),
            "scale": self.scale_entry.get(),
            "replacewith": self.replacewith_var.get(),
            "replaceimg": self.replaceimg_entry.get(),
            "mosaicsize": self.mosaicsize_entry.get(),
            "mask_scale": self.maskscale_entry.get(),
            "face_recog": self.face_recog_var.get(),
            "fr_name": self.fr_name_var.get(),
            "distort_audio": self.distort_audio_var.get(),
            "keep_audio": self.keep_audio_var.get(),
            "copy_acodec": self.copy_acodec_var.get(),
            "fr_thresh": self.fr_thresh_entry.get(),
            "backend": self.backend_var.get(),
            "execution_provider": self.ep_var.get(),
            "ffmpeg_config": self.ffmpeg_config_entry.get(),
            "info": self.info_var.get(),
            "keep_metadata": self.keep_metadata_var.get(),
            "preview": self.preview_var.get(),
            "boxes": self.boxes_var.get(),
            "draw_scores": self.draw_scores_var.get(),
        }
        return options


    def run_anonymization(self, options):
        self.log_message("Starting anonymization...")
        self.progress.start()
        self.process_stopped = False

        args = []

        if options["input"]:
            args.append(options["input"])
        if options["output"]:
            args.extend(["--output", options["output"]])
        if options["thresh"]:
            args.extend(["--thresh", options["thresh"]])
        if options["scale"]:
            args.extend(["--scale", options["scale"]])
        if options["replacewith"]:
            args.extend(["--replacewith", options["replacewith"]])
        if options["replaceimg"]:
            args.extend(["--replaceimg", options["replaceimg"]])
        if options["mosaicsize"]:
            args.extend(["--mosaicsize", options["mosaicsize"]])
        if options["mask_scale"]:
            args.extend(["--mask-scale", options["mask_scale"]])
        if options["face_recog"]:
            args.append("--face-recog")
        if options["fr_name"]:
            args.append("--frn")
        if options["distort_audio"]:
            args.append("--distort-audio")
        if options["keep_audio"]:
            args.append("--keep-audio")
        if options["copy_acodec"]:
            args.append("--copy-acodec")
        if options["fr_thresh"]:
            args.extend(["--fr-thresh", options["fr_thresh"]])
        if options["backend"]:
            args.extend(["--backend", options["backend"]])
        if options["execution_provider"]:
            args.extend(["--execution-provider", options["execution_provider"]])
        if options["ffmpeg_config"]:
            args.extend(["--ffmpeg-config", options["ffmpeg_config"]])
        if options["info"]:
            args.append("--info")
        if options["keep_metadata"]:
            args.append("--keep-metadata")
        if options["preview"]:
            args.append("--preview")
        if options["boxes"]:
            args.append("--boxes")
        if options["draw_scores"]:
            args.append("--draw-scores")
        
        cmd = ["anonfaces"] + args
        
        def monitor_process():
            try:
                self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
                def read_stdout():
                    for line in iter(self.process.stdout.readline, ''):
                        self.log_message(line.strip())
    
                # seems normal output is stderr here...
                def read_stderr():
                    for line in iter(self.process.stderr.readline, ''):
                        self.log_message(line.strip())
    
                # begin threads to read stdout and stderr
                stdout_thread = threading.Thread(target=read_stdout, daemon=True)
                stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    
                stdout_thread.start()
                stderr_thread.start()
    
                # waitting for the process to finish in the separate thread
                self.process.wait()
    
                if not self.process_stopped:
                    self.log_message("Anonymization completed successfully.")
            except Exception as e:
                self.log_message(f"An error occurred: {e}")
            finally:
                self.progress.stop()
                self.process = None  # process is set to None after completion
            
        threading.Thread(target=monitor_process, daemon=True).start()


class TextRedirector:
    #redirects stdout and stderr to log_text
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, message):
        self.widget.config(state="normal")
        self.widget.insert(tk.END, message)
        self.widget.see(tk.END)
        self.widget.config(state="disabled")

    def flush(self):
        pass  #needed to ensure compatibility with sys.stdout


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.enabled = True  # tooltip enabled by default
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if not self.enabled:  # check if tooltips are enabled
            return
        if self.tooltip_window or not self.text:
            return

        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 40
        y += self.widget.winfo_rooty() + 40

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)  # removes window decorations
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip_window, text=self.text, background="yellow", relief="solid", borderwidth=1)
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def toggle(self, enabled):
        self.enabled = enabled


class MenuToolTip:
    def __init__(self, widget, text, delay=1000):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.delay = delay
        self.show_tooltip_id = None
        self.enabled = True  # tooltip enabled by default
        self.widget.bind("<Enter>", self.schedule_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def schedule_tooltip(self, event=None):
        self.show_tooltip_id = self.widget.after(self.delay, self.show_tooltip)

    def show_tooltip(self, event=None):
        if not self.enabled:  # check if tooltips are enabled
            return
        if self.tooltip_window or not self.text:
            return

        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 40
        y += self.widget.winfo_rooty() + 40

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)  # removes window decorations
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip_window, text=self.text, background="yellow", relief="solid", borderwidth=1)
        label.pack()

    def hide_tooltip(self, event=None):
        if self.show_tooltip_id:
            self.widget.after_cancel(self.show_tooltip_id)
            self.show_tooltip_id = None
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
            
    def toggle(self, enabled):
        self.enabled = enabled


if __name__ == "__main__":
    root = tk.Tk()
    app = AnonymizationApp(root)
    root.mainloop()
