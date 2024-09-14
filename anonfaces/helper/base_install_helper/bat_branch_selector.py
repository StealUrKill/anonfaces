import requests
import msvcrt
import os
import sys

owner = "StealUrKill"
repo = "anonfaces"

def clear_screen():
    if sys.platform == "win32":
        os.system("cls")
    else:
        os.system("clear")

def wait_for_any_key(message):
    """Waits for the homies."""
    print(message)
    msvcrt.getch()  # Waits for any key press from the homies

def get_github_branches(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/branches"
    response = requests.get(url)

    if response.status_code == 200:
        branches = response.json()

        while True:
            print("\nAvailable branches:")
            for i, branch in enumerate(branches):
                print(f"{i + 1}. {branch['name']}")

            branch_choice = input(f"\nSelect a branch to use (1-{len(branches)}): ").strip()
            try:
                selected_branch = branches[int(branch_choice) - 1]['name']
                return selected_branch
            except (IndexError, ValueError):
                print()
                wait_for_any_key("Invalid selection. Press any key to try again.")
                clear_screen()
    else:
        print(f"Failed to retrieve branches. Status code: {response.status_code}")
        wait_for_any_key("Press any key to exit.")
        return None

if __name__ == "__main__":
    selected_branch = get_github_branches(owner, repo)
    if selected_branch:
        print(selected_branch)
        with open("selected_branch.txt", "w") as f:
            f.write(selected_branch)
    else:
        print("No branch selected.")
        with open("selected_branch.txt", "w") as f:
            f.write("No branch selected.")
