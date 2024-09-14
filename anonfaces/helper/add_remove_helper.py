import subprocess
import sys
import time
import msvcrt
import os
import glob
import ctypes
import logging
import shutil
import stat
import webbrowser
import zipfile
import tkinter as tk
from tkinter import filedialog
import re
try:
    import requests
except ImportError:
    print()
    print("'requests' module not found.")
    print("Do you want to install it now?")
    print()
    choice = input("Enter your choice (y/n): ").strip().lower()

    if choice in ['y', 'yes']:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests
    else:
        print("The 'requests' module is required to continue. Exiting the script.")
        time.sleep(5)
        sys.exit(1)
    
    time.sleep(5)

    if sys.platform == "win32":
        os.system("cls")
    else:
        os.system("clear")


owner = "StealUrKill"
repo = "anonfaces"

def get_version_from_branch(branch_name):
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch_name}/pyproject.toml"
    response = requests.get(url)
    if response.status_code == 200:
        match = re.search(r'version\s*=\s*"([^"]+)"', response.text)
        if match:
            return match.group(1)
    return "unknown"

def install():
    # fetch available branches
    url = f"https://api.github.com/repos/{owner}/{repo}/branches"
    response = requests.get(url)
    branches = response.json()

    if response.status_code == 200:
        print()
        print("Available branches:")
        print()
        for i, branch in enumerate(branches):
            branch_name = branch['name']
            version = get_version_from_branch(branch_name)
            print(f"{i + 1}. {branch_name} (Version: {version})")
        
        print(f"\n0. Main Menu")
    else:
        print("Failed to retrieve any branch.")
        input("Press any key to exit...")
        exit(1)

    print()
    branch_choice = input(f"Enter the number of the branch to install from (1-{len(branches)} or 0 to exit): ")

    if branch_choice == '0':
        main()

    if sys.platform == "win32":
        os.system("cls")
    else:
        os.system("clear")
    try:
        selected_branch = branches[int(branch_choice) - 1]['name']
    except (IndexError, ValueError):
        print("Invalid choice. Exiting.")
        input("Press any key to exit...")
        exit(1)
    
    print()
    print("Select optional dependencies to install:")
    print()
    print("1. NO OPTIONAL DEPENDENCIES")
    print("2. STANDARD ONNXRUNTIME-1.19.0")
    print("3. CUDA 11.X ONNXRUNTIME-GPU-1.18.1")
    print("4. DirectML ONNXRUNTIM-DIRECTML-1.19.0")
    print("5. OpenVINO ONNXRUNTIME-OPENVINO-1.18.0/OPENVINO-2024.1.0")
    print("6. CUDA 12.X ONNXRUNTIME-GPU ORT Azure Devops Feed Latest")
    print("7. CUDA 12.X ONNXRUNTIME-GPU-1.18.2 ORT Azure Devops Feed")
    print()
    print("0. MAIN MENU")
    
    choice = input("Enter your choice (0/1/2/3/4/5/6/7 or Press Enter): ")

    clear_screen()
    optional_dependency = {
        "2": "standard",
        "3": "cuda",
        "4": "directml",
        "5": "openvino"
    }.get(choice, "")

    try:
        if optional_dependency:
            subprocess.run([
                "python", "-m", "pip", "install", 
                f"anonfaces[{optional_dependency}]@git+https://github.com/{owner}/{repo}.git@{selected_branch}"
            ])
            print("Installation complete.")
        elif choice == "6":
            install_custom6(selected_branch)
        elif choice == "7":
            install_custom7(selected_branch)
        elif choice == "0":
            main()
        elif choice == "1" or choice == "":
            print("Installing without any optional dependencies...")
            subprocess.run([
                "python", "-m", "pip", "install", 
                f"git+https://github.com/{owner}/{repo}.git@{selected_branch}"
            ])
    finally:
        print()
        wait_for_any_key("Press any key to exit...")
        main()

def install_custom6(selected_branch):
    print()
    print("Running CUDA 12.X ONNXRUNTIME-GPU ORT Azure Devops Feed Latest subprocess...")
    subprocess.run([
                "python", "-m", "pip", "uninstall", 
                "onnxruntime-gpu",
                "-y"
            ])
    subprocess.run([
                "python", "-m", "pip", "install", 
                f"git+https://github.com/{owner}/{repo}.git@{selected_branch}"
            ])
    subprocess.run([
                "python", "-m", "pip", "install", 
                "onnxruntime-gpu", 
                "--extra-index-url", 
                "https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/"
            ])
    print()
    print("Installation complete.")
    wait_for_any_key("Press any key to exit...")
    main()
    
def install_custom7(selected_branch):
    print()
    print("Running CUDA 12.X ONNXRUNTIME-GPU-1.18.2 ORT Azure Devops Feed subprocess...")
    subprocess.run([
                "python", "-m", "pip", "uninstall", 
                "onnxruntime-gpu",
                "-y"
            ])
    subprocess.run([
                "python", "-m", "pip", "install", 
                f"git+https://github.com/{owner}/{repo}.git@{selected_branch}"
            ])
    subprocess.run([
                "python", "-m", "pip", "install", 
                "onnxruntime-gpu==1.18.1", 
                "--extra-index-url", 
                "https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/"
            ])
    print()
    print("Installation complete.")
    wait_for_any_key("Press any key to exit...")
    main()    

def get_python_version():
    return f"{sys.version_info.major}{sys.version_info.minor}"

def remove_readonly(func, path, excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def cuda_install_options():
    clear_screen()
    print()
    print("Select option to download or install:")
    print()
    print("1. CUDA Toolkit Website")
    print("2. CUDNN Website")
    print("3. TensorRT Website")
    print("4. Install All Downloaded (Version Cuda 12.X & CUDNN 9.X")
    print("5. Install All Downloaded (Version Cuda 11.X & CUDNN 8.X - Placehholder will not work")
    print("0. Main Menu")
    print()    
    choice = input("Enter your choice (0/1/2/3/4 or Press Enter): ")

    clear_screen()
    if choice == "1":
        cuda_custom1()
    elif choice == "2":
        cuda_custom2()
    elif choice == "3":
        cuda_custom3()
    elif choice == "4":
        cuda_custom4()
    elif choice == "0" or choice == "":
        main()
    else:
        clear_screen()
        print()
        print("Invalid choice. Please try again.")
        wait_for_any_key("Press any key to continue...")
        cuda_install_options()

def cuda_custom1():
    url = "https://developer.nvidia.com/cuda-toolkit-archive"
    webbrowser.open(url)
    cuda_install_options()

def cuda_custom2():
    url = "https://developer.nvidia.com/cudnn-archive"
    webbrowser.open(url)
    cuda_install_options()

def cuda_custom3():
    url = "https://developer.nvidia.com/tensorrt/download"
    webbrowser.open(url)
    cuda_install_options()

def extract_zips_in_directory(directory):
    for file_name in os.listdir(directory):
        if file_name.endswith('.zip'):
            zip_file_path = os.path.join(directory, file_name)
            print(f"Extracting {file_name}...")
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(directory)
            print(f"Extracted {file_name}.")

def find_and_run_cuda_exe(directory):
    for file_name in os.listdir(directory):
        if file_name.startswith('cuda_') and re.search(r'\d', file_name) and file_name.endswith('.exe'):
            exe_file_path = os.path.join(directory, file_name)
            print()
            print(f"Found CUDA installer: {file_name}")

            command = [exe_file_path, "-s", '--components="driver,cuda,tools"', "--override"]

            try:
                print()
                print(f"Running {file_name} with silent install options...")
                # run the CUDA installer
                subprocess.run(command, check=True)
                print()
                print(f"Installation of {file_name} complete.")
            except subprocess.CalledProcessError as e:
                print(f"Failed to run {file_name}: {e}")
            return
    print("No valid CUDA installer found.")
    
def find_and_run_cudnn_exe(directory):
    for file_name in os.listdir(directory):
        if file_name.startswith('cudnn_') and re.search(r'\d', file_name) and file_name.endswith('.exe'):
            exe_file_path = os.path.join(directory, file_name)
            print()
            print(f"Found CUDNN installer: {file_name}")

            command = [exe_file_path, "-s", "--override"]

            try:
                print()
                print(f"Running {file_name} with silent install options...")
                subprocess.run(command, check=True)
                print()
                print(f"Installation of {file_name} complete.")
            except subprocess.CalledProcessError as e:
                print(f"Failed to run {file_name}: {e}")
            return
    print("No valid CUDNN installer found.")
    
def copy_cudnn_12_x_files():
    base_dir = r"C:\Program Files\NVIDIA\CUDNN"
    
    # find v9.x directory
    cudnn_dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and d.startswith("v9.")]
    
    if not cudnn_dirs:
        print("No valid v9.x directory found in CUDNN.")
        return

    for cudnn_dir in cudnn_dirs:
        cudnn_path = os.path.join(base_dir, cudnn_dir)

        bin_dir = os.path.join(cudnn_path, "bin")
        include_dir = os.path.join(cudnn_path, "include")
        lib_dir = os.path.join(cudnn_path, "lib")

        # look for 12.x directories in bin, include, and lib
        for folder, sub_dir in [("bin", bin_dir), ("include", include_dir), ("lib", lib_dir)]:
            if os.path.exists(sub_dir):
                sub_dirs = [d for d in os.listdir(sub_dir) if os.path.isdir(os.path.join(sub_dir, d)) and d.startswith("12.")]
                for sub_12_x in sub_dirs:
                    src_12_x_path = os.path.join(sub_dir, sub_12_x)
                    parent_dir = sub_dir  # Copy files to the parent directory

                    # handling for lib\x64 subdirectory if exist
                    if folder == "lib":
                        # look for the next directory under lib\12.x (e.g., x64)
                        lib_sub_dirs = os.listdir(src_12_x_path)
                        for lib_sub_dir in lib_sub_dirs:
                            lib_sub_dir_path = os.path.join(src_12_x_path, lib_sub_dir)
                            if os.path.isdir(lib_sub_dir_path):
                                # copy files from lib\12.x\x64 to lib
                                files_in_x64 = os.listdir(lib_sub_dir_path)
                                for file_name in files_in_x64:
                                    src_file_path = os.path.join(lib_sub_dir_path, file_name)
                                    dest_file_path = os.path.join(lib_dir, file_name)
                                    try:
                                        shutil.copy2(src_file_path, dest_file_path)
                                        print(f"Copied {file_name} from {os.path.normpath(src_file_path)} to {os.path.normpath(dest_file_path)}")
                                    except Exception as e:
                                        print(f"Failed to copy {file_name}: {e}")

                    else:
                        files_in_12_x = os.listdir(src_12_x_path)
                        for file_name in files_in_12_x:
                            src_file_path = os.path.join(src_12_x_path, file_name)
                            dest_file_path = os.path.join(parent_dir, file_name)
                            try:
                                shutil.copy2(src_file_path, dest_file_path)
                                print(f"Copied {file_name} from {os.path.normpath(src_file_path)} to {os.path.normpath(dest_file_path)}")
                            except Exception as e:
                                print(f"Failed to copy {file_name}: {e}")

def add_to_system_path(directory):
    # fetch the current system path
    current_path = os.environ.get('PATH', '')
    
    # is the directory is already in the PATH
    if directory not in current_path:
        # lets add the directory to system path permanently (Windows only)
        subprocess.run(f'setx PATH "%PATH%;{directory}"', shell=True)
        print(f"Added '{directory}' to system PATH")
    else:
        print(f"'{directory}' is already in system PATH")

def copy_tensorrt_x_files(destination_dir):
    base_cudnn_dir = r"C:\Program Files\NVIDIA\CUDNN"
    
    cudnn_dirs = [d for d in os.listdir(base_cudnn_dir) if os.path.isdir(os.path.join(base_cudnn_dir, d)) and d.startswith("v9.")]
    
    if not cudnn_dirs:
        print("No valid v9.x directory found in CUDNN.")
        return
    
    cudnn_path = os.path.join(base_cudnn_dir, cudnn_dirs[0])
    cudnn_lib_dir = os.path.join(cudnn_path, "lib")  # Path to CuDNN's 'lib' directory

    # adding CuDNN 'lib' directory to system PATH per tensorrt instructions here https://docs.nvidia.com/deeplearning/tensorrt/install-guide/index.html#installing-zip
    # we can copy lib to bin like stated but due to possible other issues if compiling, we will just add a path for now
    print(f"Adding CuDNN 'lib' directory to system PATH: {cudnn_lib_dir}")
    add_to_system_path(cudnn_lib_dir)

    for item in os.listdir(destination_dir):
        extracted_path = os.path.join(destination_dir, item)
        if os.path.isdir(extracted_path) and item.startswith("TensorRT-") and "10." in item:
            print(f"Found TensorRT 10.x directory: {extracted_path}")
            
            for sub_item in os.listdir(extracted_path):
                sub_item_path = os.path.join(extracted_path, sub_item)
                dest_sub_dir = os.path.join(cudnn_path, sub_item)
                
                try:
                    if os.path.isdir(sub_item_path):
                        if os.path.exists(dest_sub_dir):
                            for sub_file in os.listdir(sub_item_path):
                                src_file_path = os.path.join(sub_item_path, sub_file)
                                dest_file_path = os.path.join(dest_sub_dir, sub_file)
                                shutil.copy2(src_file_path, dest_file_path)
                                print(f"Copied {sub_file} from {os.path.normpath(src_file_path)} to {os.path.normpath(dest_file_path)}")
                        else:
                            shutil.copytree(sub_item_path, dest_sub_dir)
                            print(f"Copied {sub_item} from {os.path.normpath(sub_item_path)} to {os.path.normpath(dest_sub_dir)}")
                    else:
                        shutil.copy2(sub_item_path, dest_sub_dir)
                        print(f"Copied {sub_item} from {os.path.normpath(sub_item_path)} to {os.path.normpath(dest_sub_dir)}")
                except Exception as e:
                    print(f"Failed to copy {sub_item} from {os.path.normpath(sub_item_path)} to {os.path.normpath(dest_sub_dir)}: {e}")

def copy_cudnn9_file():
    # directories for CuDNN and CUDA - not using cuda path as the terminal has not refreshed to get the updated path
    cudnn_base_dir = r"C:\Program Files\NVIDIA\CUDNN"
    cuda_base_dir = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"
    
    # get the latest version directory based on a version prefix (v9 for CuDNN or v12 for CUDA)
    def find_latest_version_dir(base_path, version_prefix):
        version_dirs = [
            d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d)) and d.startswith(version_prefix)
        ]
        if not version_dirs:
            return None
        version_dirs.sort(key=lambda v: [int(x) for x in re.findall(r'\d+', v)], reverse=True)
        return os.path.join(base_path, version_dirs[0])

    # get the latest CuDNN 9.x version
    cudnn_bin_dir = find_latest_version_dir(cudnn_base_dir, "v9")
    if cudnn_bin_dir:
        cudnn_bin_dir = os.path.join(cudnn_bin_dir, "bin")
    else:
        print("No valid CuDNN v9.x directory found.")
        return

    # get the latest CUDA 12.x version
    cuda_bin_dir = find_latest_version_dir(cuda_base_dir, "v12")
    if cuda_bin_dir:
        cuda_bin_dir = os.path.join(cuda_bin_dir, "bin")
    else:
        print("No valid CUDA v12.x directory found.")
        return

    if not os.path.exists(cudnn_bin_dir):
        print(f"Source directory '{cudnn_bin_dir}' does not exist.")
        return
    if not os.path.exists(cuda_bin_dir):
        print(f"Destination directory '{cuda_bin_dir}' does not exist.")
        return

    # find 'cudnn64_X.dll' file (X can be any number)
    for file_name in os.listdir(cudnn_bin_dir):
        if re.match(r'cudnn64_\d+\.dll', file_name):
            source_file = os.path.join(cudnn_bin_dir, file_name)
            destination_file = os.path.join(cuda_bin_dir, file_name)
            
            # if the file already exists in the destination
            if os.path.exists(destination_file):
                print(f"File '{file_name}' already exists in '{cuda_bin_dir}', skipping...")
                continue

            try:
                shutil.copy2(source_file, destination_file)
                print(f"Copied '{file_name}' to '{cuda_bin_dir}'")
            except Exception as e:
                print(f"Error copying file: {e}")
            return

    print("No 'cudnn64_X.dll' file found in the source directory.")

def cuda_custom4():
    print()
    print("This Expects only three files total in the directory that you chose.")
    print()
    print("Be sure to only have 1 of each CUDA 12.x, CUDNN 9.x, and TENSORRT for 12.x.")
    print()
    print("Also be sure to have the correct versions that work with each other!")
    print()
    print("This will cause issues and errors if not!!!")
    print()
    wait_for_any_key("Press any key to continue...")
    root = tk.Tk()
    root.withdraw()
    selected_dir = filedialog.askdirectory(title="Select the folder where you downloaded the CUDA files")

    if not selected_dir:
        print("\nNo folder selected.")
        wait_for_any_key("Press any key to exit...")
        clear_screen()
        return
    
    print(f"\nSelected directory: {os.path.normpath(selected_dir)}")

    destination_dir = os.path.join(selected_dir, "Python_Cuda_Install")
    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir)

    file_patterns = {
        "cuda": "cuda_",
        "cudnn": "cudnn_",
        "tensorrt": "TensorRT-"
    }

    file_counter = {
        "cuda": 0,
        "cudnn": 0,
        "tensorrt": 0
    }

    allowed_extensions = {".zip", ".exe"}
    files_in_directory = os.listdir(selected_dir)
    for file_name in files_in_directory:
        file_ext = os.path.splitext(file_name)[1].lower()  # get file extension and convert to lowercase
        if file_ext in allowed_extensions:  # does the file has an allowed extension
            for key, prefix in file_patterns.items():
                if file_name.startswith(prefix) and file_counter[key] < 1:
                    src_file_path = os.path.join(selected_dir, file_name)
                    dest_file_path = os.path.join(destination_dir, file_name)
                    shutil.copy2(src_file_path, dest_file_path)
                    file_counter[key] += 1
                    print()
                    print(f"Copied {file_name} to {os.path.normpath(dest_file_path)}")  # normalize path before printing due to wrong /\

    extract_zips_in_directory(destination_dir)
    find_and_run_cuda_exe(destination_dir)
    find_and_run_cudnn_exe(destination_dir)
    print()
    # copy 12.x files to parent directories - this will not work with cudnn 11.x
    copy_cudnn_12_x_files()
    print()
    copy_tensorrt_x_files(destination_dir)
    print()
    copy_cudnn9_file()
    print()
    try:
        shutil.rmtree(destination_dir)
        print(f"Deleted directory: {destination_dir}")
    except Exception as e:
        print(f"Error deleting directory {destination_dir}: {e}")
    print()
    wait_for_any_key("Press any key to exit...")
    clear_screen()
    cuda_install_options()


    

    
def get_installed_packages():
    result = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], stdout=subprocess.PIPE, text=True)
    return result.stdout.splitlines()

def wait_for_any_key(message):
    """Waits for the homies."""
    print(message)
    msvcrt.getch()  # Waits for any key press from the homies

def uninstall_package(package_name):
    """Uninstalls the specified package."""
    subprocess.run([sys.executable, '-m', 'pip', 'uninstall', '-y', package_name])

def uninstall():
    direct_list = [
        'anonfaces', 'imageio', 'imageio-ffmpeg', 'numpy', 'onnx', 
        'onnxruntime', 'openvino', 'pedalboard', 'pillow', 'scikit-image', 'tqdm'
    ]

    wildcard_list = ['onnxruntime', 'openvino']

    additional_list = [
        'colorama', 'coloredlogs', 'decorator', 'flatbuffers', 'humanfriendly', 
        'lazy_loader', 'moviepy', 'mpmath', 'networkx', 'opencv-python', 
        'packaging', 'proglog', 'protobuf', 'pyreadline3', 'scipy', 'sympy', 'tifffile'
    ]

    installed_packages = get_installed_packages()

    def filter_packages(package_list, patterns):
        filtered = []
        for package in installed_packages:
            # are packages installed via Git
            if " @ git+" in package:
                package_name = package.split(' @ ')[0]  # get the name before ' @ git+'
                if package_name in package_list:
                    filtered.append(package_name)
            else:
                package_name = package.split('==')[0]
                if package_name in package_list or any(package_name.startswith(pattern) for pattern in patterns):
                    filtered.append(package_name)
                    
        return filtered

    direct_install = filter_packages(direct_list, wildcard_list)
    additional_install = filter_packages(additional_list, [])

    print(f"\n{'Direct Install Packages':<40} {'Additional Install Packages':<40}")
    print(f"{'-'*40} {'-'*40}")
    
    max_len = max(len(direct_install), len(additional_install))
    
    for i in range(max_len):
        left = direct_install[i] if i < len(direct_install) else ''
        right = additional_install[i] if i < len(additional_install) else ''
        print(f"{left:<40} {right:<40}")

    print()
    choice = input("Choose an option:\n"
                   "1 - Uninstall Direct Install packages\n"
                   "2 - Uninstall Additional Install packages\n"
                   "3 - Uninstall both\n"
                   "4 - Uninstall DLIB\n"
                   "0 - Main Menu\n"
                   "Your choice: ").strip()

    if choice == '1':
        for package in direct_install:
            uninstall_package(package)
            print(f"Uninstalled: {package}")
    elif choice == '2':
        for package in additional_install:
            uninstall_package(package)
            print(f"Uninstalled: {package}")
    elif choice == '3':
        for package in set(direct_install + additional_install):
            uninstall_package(package)
            print(f"Uninstalled: {package}")
    elif choice == '4':
        uninstall_package("dlib")
        print("Uninstalled: DLIB")
    elif choice == '0':
        main()
    else:
        print("Invalid choice. Please try again.")

    print()
    wait_for_any_key("Nothing to do here. Press any key to exit...")
    clear_screen()
    main()




def dlib_install_custom_mahud():
    print()
    print("Continuing will clone the repo and install the version according to python.")
    wait_for_any_key("Press and key to continue.")
    clear_screen()
    python_version = get_python_version()
    print(f"Detected Python version: {python_version}")
    print()
    repo_url = "https://github.com/z-mahmud22/Dlib_Windows_Python3.x.git"
    clone_dir = os.path.join(os.getcwd(), "Dlib_Windows_Python3.x")
    print()
    print(f"Cloning the repository from {repo_url}...")
    subprocess.run(["git", "clone", repo_url])
    print()
    wheel_file_pattern = f"*cp{python_version}*-win_amd64.whl"
    wheel_files = glob.glob(os.path.join(clone_dir, wheel_file_pattern))
    
    if not wheel_files:
        print(f"No matching wheel found for Python {python_version}. Exiting.")
        return
    
    wheel_file_path = wheel_files[0]
    print(f"Found wheel file: {wheel_file_path}")
    print()
    try:
        subprocess.run([
            "python", "-m", "pip", "install", wheel_file_path
        ])
        print()
        print(f"Successfully installed {os.path.basename(wheel_file_path)}")
    except Exception as e:
        print(f"Failed to install the wheel file: {str(e)}")
    finally:
        try:
            os.chdir("..")
            if os.path.exists(clone_dir):
                shutil.rmtree(clone_dir, onerror=remove_readonly)
                print()
                print("Repository deleted.")
        except Exception as e:
            print(f"Error deleting the directory {clone_dir}: {str(e)}")
        print()
        print("Installation complete.")
        clear_screen()
        main()

def dlib_install_custom(package_name):
    python_version = f"Python{sys.version_info.major}{sys.version_info.minor}"  # Python311 or Python312 only
    path = f"anonfaces/prebuilts/{python_version}"

    # fetch available branches
    url = f"https://api.github.com/repos/{owner}/{repo}/branches"
    response = requests.get(url)

    if response.status_code == 200:
        branches = response.json()
        print("\nAvailable branches:")
        print()
        for i, branch in enumerate(branches):
            branch_name = branch['name']
            version = get_version_from_branch(branch_name)
            print(f"{i + 1}. {branch_name} (Version: {version})")
        print("\n0. DLIB Menu")
        print()
        branch_choice = input(f"Enter the number of the branch to explore (1-{len(branches)} or 0 to go back): ").strip()

        if branch_choice == '0':
            clear_screen()
            dlib_install_options()

        try:
            selected_branch = branches[int(branch_choice) - 1]['name']
        except (IndexError, ValueError):
            clear_screen()
            print()
            wait_for_any_key("Invalid choice. Press any key to return.")
            clear_screen()
            dlib_install_custom("dlib")
        
        # gitHub API URL with branch
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={selected_branch}"

        # gitHub API request to get the directory contents
        response = requests.get(api_url)

        if response.status_code == 200:
            contents = response.json()
            clear_screen()
            version = get_version_from_branch(selected_branch)
            print(f"\nFolders in the '{selected_branch}' branch (Version: {version}) at '{path}':")
            print()
            directories = [item for item in contents if item['type'] == 'dir']
            if not directories:
                print("No subfolders found.")
                return

            for i, item in enumerate(directories):
                print(f"{i + 1}. {item['name']}")

            folder_choice = input(f"\nSelect a folder to explore (1-{len(directories)} or 0 to go back): ").strip()

            if folder_choice == '0':
                clear_screen()
                dlib_install_custom("dlib")

            try:
                selected_folder = directories[int(folder_choice) - 1]['name']
            except (IndexError, ValueError):
                clear_screen()
                print()
                wait_for_any_key("Invalid choice. Press any key to return.")
                clear_screen()
                dlib_install_custom("dlib")

            folder_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}/{selected_folder}?ref={selected_branch}"
            folder_response = requests.get(folder_url)

            if folder_response.status_code == 200:
                folder_contents = folder_response.json()
                clear_screen()
                # list the files and find the whls
                whl_files = [file for file in folder_contents if file['name'].endswith('.whl') and package_name in file['name']]

                if not whl_files:
                    clear_screen()
                    print()
                    wait_for_any_key(f"No .whl files found for '{package_name}' in the selected folder. Press any key to return.")
                    clear_screen()
                    dlib_install_options()

                print("\nAvailable .whl files:")
                for i, file in enumerate(whl_files):
                    print(f"{i + 1}. {file['name']}")

                # select a whl to download
                whl_choice = input(f"\nSelect a file to download (1-{len(whl_files)} or 0 to exit): ").strip()

                if whl_choice == '0':
                    clear_screen()
                    dlib_install_options()

                try:
                    selected_whl = whl_files[int(whl_choice) - 1]
                except (IndexError, ValueError):
                    clear_screen()
                    print()
                    wait_for_any_key("Invalid Choice. Press any key to continue...")
                    clear_screen()
                    dlib_install_custom("dlib")
                clear_screen()
                
                # download the whl
                download_url = selected_whl['download_url']
                file_name = selected_whl['name']

                print(f"\nDownloading {file_name} from {download_url}...")
                whl_response = requests.get(download_url)

                # save the whl
                if whl_response.status_code == 200:
                    with open(file_name, 'wb') as file:
                        file.write(whl_response.content)
                    print(f"Downloaded {file_name} successfully.")

                    # uninstall the existing package
                    print(f"\nUninstalling existing '{package_name}' package...")
                    subprocess.run([sys.executable, "-m", "pip", "uninstall", package_name, "-y"])

                    # install the whl
                    print(f"\nInstalling {file_name}...")
                    install_result = subprocess.run([sys.executable, "-m", "pip", "install", file_name])

                    # if the installation was successful delete the whl
                    if install_result.returncode == 0:
                        try:
                            os.remove(file_name)
                            print()
                            print(f"Deleted {file_name} after successful installation.")
                            wait_for_any_key("Press any key to continue...")
                            dlib_install_options()
                        except Exception as e:
                            print(f"Error deleting {file_name}: {e}")
                            wait_for_any_key("Press any key to continue...")
                            dlib_install_options()
                    else:
                        clear_screen()
                        print()
                        print(f"Failed to install {file_name}.")
                        wait_for_any_key("Press any key to continue...")
                        clear_screen()
                        dlib_install_custom("dlib")
                else:
                    clear_screen()
                    print()
                    print(f"Failed to download the file. Status code: {whl_response.status_code}")
                    wait_for_any_key("Press any key to continue...")
                    clear_screen()
                    dlib_install_custom("dlib")
            else:
                clear_screen()
                print()
                print(f"Failed to fetch the selected folder contents. Status code: {folder_response.status_code}")
                wait_for_any_key("Press any key to continue...")
                clear_screen()
                dlib_install_custom("dlib")
        else:
            clear_screen()
            print()
            print(f"Failed to fetch directory contents. Status code: {response.status_code}")
            wait_for_any_key("Press any key to continue...")
            clear_screen()
            dlib_install_custom("dlib")
    else:
        clear_screen()
        print()
        print(f"Failed to retrieve branches. Status code: {response.status_code}")
        wait_for_any_key("Press any key to continue...")
        dlib_install_options()


def dlib_install_options():
    clear_screen()
    print()  # Blank Line
    print("Select option to install:")
    print()
    print("1. PYTHON 311/312 PREBUILTS")
    print("2. Z-MAHUD PREBUILTS")
    print("0. Main Menu")
    print()    
    choice = input("Enter your choice (0/1/2 or Press Enter to go back): ")

    clear_screen()
    if choice == "1":
        clear_screen()
        dlib_install_custom("dlib")
    elif choice == "2":
        clear_screen()
        dlib_install_custom_mahud()
    elif choice == "0" or choice == "":
        main()
    else:
        clear_screen()
        print()
        print("Invalid choice. Please try again.")
        wait_for_any_key("Press any key to continue...")
        dlib_install_options()




def main():
    clear_screen()
    while True:
        print()
        print("Menu:")
        print()
        print("1. Install Anonfaces w/args")
        print("2. Uninstall Anonfaces w/args")
        print("3. CUDA Toolkit Install Options")
        print("4. Install Prebuilt DLIB with CUDA/AVX/AVX2/MKL (May NOT work on all machines)")
        print("0. Exit")
        print()
        choice = input("Enter your choice (1/2/3/4/0) or Press Enter to exit: ").strip()

        if choice == '1':
            clear_screen()
            install()
        elif choice == '2':
            clear_screen()
            uninstall()
        elif choice == '3':
            clear_screen()
            cuda_install_options()
        elif choice == '4':
            clear_screen()
            dlib_install_options()
        elif choice == "0" or choice == "":
            sys.exit(0)
        else:
            clear_screen()
            print("Invalid choice. Please try again.")
            wait_for_any_key("Press any key to continue...")
            main()

def is_admin():
    """Check if the script is running with administrative privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def clear_screen():
    if sys.platform == "win32":
        os.system("cls")
    else:
        os.system("clear")
        
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if is_admin():
        main()
    else:
        # re-run the script with admin privileges
        logging.info("Elevating script to administrator privileges...")
        try:
            script = os.path.abspath(sys.argv[0])
            params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script}" {params}', None, 1)
        except Exception as e:
            logging.error(f"Failed to elevate privileges: {e}")
            sys.exit(1)
        sys.exit()
