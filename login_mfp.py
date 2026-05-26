# login_mfp.py
import subprocess
import os
import sys
import pathlib

def main():
    p_dir = pathlib.Path("temp_chrome_profile")
    p_dir.mkdir(exist_ok=True)

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]

    chrome_path = None
    for p in chrome_paths:
        if os.path.exists(p):
            chrome_path = p
            break

    if not chrome_path:
        print("Fejl: Kunne ikke finde Google Chrome på dit system.")
        print("Sørg for, at Google Chrome er installeret, og prøv igen.")
        return

    print("\n=========================================================================")
    print("LOG IND MANUELT (Uden om Playwright):")
    print("Jeg åbner nu et helt normalt, isoleret Google Chrome-vindue.")
    print("Dette vindue har INGEN robot-flag, så Recaptcha/Cloudflare vil lade dig logge ind!")
    print("\n1. Log ind på din MyFitnessPal-konto i det vindue, der åbner.")
    print("2. Når du kan se din mad-dagbog, skal du blot LUKKE det Chrome-vindue igen.")
    print("=========================================================================\n")

    abs_profile = os.path.abspath(p_dir)
    
    # Kører en helt normal, ren Chrome uden nogen automatiserings- eller debugging-porte!
    subprocess.Popen([
        chrome_path,
        f"--user-data-dir={abs_profile}",
        "--no-first-run",
        "https://www.myfitnesspal.com/food/diary"
    ])

if __name__ == '__main__':
    main()
