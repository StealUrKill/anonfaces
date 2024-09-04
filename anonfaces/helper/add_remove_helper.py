import subprocess
import sys
import time
import msvcrt
import os

# Ensure requests module is installed
try:
    import requests
except ImportError:
    print()  # Blank Line
    print("'requests' module not found.")
    print("Do you want to install it now?")
    print()  # Blank Line
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

import re

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
    # Fetch available branches
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
        
        # Add an option to exit
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
    
    print()  # Blank Line
    print("Select optional dependencies to install:")
    print("1. Standard")
    print("2. CUDA")
    print("3. DirectML")
    print("4. OpenVINO")

    choice = input("Enter your choice (1/2/3/4): ")

    if sys.platform == "win32":
        os.system("cls")
    else:
        os.system("clear")
    optional_dependency = {
        "1": "standard",
        "2": "cuda",
        "3": "directml",
        "4": "openvino"
    }.get(choice, "")

    try:
        if optional_dependency:
            subprocess.run([
                "python", "-m", "pip", "install", 
                f"anonfaces[{optional_dependency}]@git+https://github.com/{owner}/{repo}.git@{selected_branch}"
            ])
        else:
            subprocess.run([
                "python", "-m", "pip", "install", 
                f"git+https://github.com/{owner}/{repo}.git@{selected_branch}"
            ])
    finally:
        print()
        print("Installation complete.")
        wait_for_any_key("Press any key to exit...")
        main()

def get_installed_packages():
    """Returns a list of all installed pip packages."""
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
    elif choice == '0':
        main()
    else:
        print("Invalid choice. Please try again.")

    print()
    wait_for_any_key("Nothing to do here. Press any key to exit...")
    main()

def main():
    if sys.platform == "win32":
        os.system("cls")
    else:
        os.system("clear")
    while True:
        print()
        print("Menu:")
        print("1. Install Anonfaces w/args")
        print("2. Uninstall Anonfaces w/args")
        print()
        print("0. Exit")
        print()
        choice = input("Enter your choice (1/2/0): ").strip()

        if choice == '1':
            if sys.platform == "win32":
                os.system("cls")
            else:
                os.system("clear")
            install()
        elif choice == '2':
            if sys.platform == "win32":
                os.system("cls")
            else:
                os.system("clear")
            uninstall()
        elif choice == '0':
            exit(1)
        else:
            if sys.platform == "win32":
                os.system("cls")
            else:
                os.system("clear")
            print("Invalid choice. Please try again.")
            wait_for_any_key("Press any key to continue...")
            main()

if __name__ == "__main__":
    main()
