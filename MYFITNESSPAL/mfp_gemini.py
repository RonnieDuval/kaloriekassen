import datetime as dt
import os
import re
import shutil
from playwright.sync_api import sync_playwright

def hent_kalorier_kontor(dato_streng="2026-05-13"):
    # 1. Definer stier til din rigtige Chrome-profil på Ubuntu
    home = os.path.expanduser("~")
    original_chrome_dir = os.path.join(home, ".config/google-chrome")
    
    # Vi opretter en isoleret arbejdskopi i din kaloriekassen-mappe
    temp_chrome_dir = os.path.join(os.getcwd(), "temp_chrome_profile")
    
    # 2. Kopier profilen hvis den mangler, så vi arver dine cookies uden at låse browseren
    if not os.path.exists(temp_chrome_dir):
        print("Kopierer din Chrome-profil til projektmappen for at omgå låse (kun første gang)...")
        os.makedirs(temp_chrome_dir, exist_ok=True)
        orig_default = os.path.join(original_chrome_dir, "Default")
        temp_default = os.path.join(temp_chrome_dir, "Default")
        
        if os.path.exists(orig_default):
            shutil.copytree(orig_default, temp_default, ignore=shutil.ignore_patterns("Cache*", "Code Cache", "GPUCache"))
        else:
            shutil.copytree(original_chrome_dir, temp_chrome_dir, ignore=shutil.ignore_patterns("Cache*", "Code Cache", "GPUCache"))

    # 3. Oprydning i Ubuntus fil-låse i kopien, så browseren aldrig fryser på about:blank
    for root, dirs, files in os.walk(temp_chrome_dir):
        for file in files:
            if "lock" in file.lower() or file == "SingletonCookie":
                try: 
                    os.remove(os.path.join(root, file))
                except: 
                    pass

    url = f"https://www.myfitnesspal.com/food/diary?date={dato_streng}"
    
    with sync_playwright() as p:
        try:
            # Starter browseren usynligt (headless=True) nu hvor vi VED det virker!
            context = p.chromium.launch_persistent_context(
                user_data_dir=temp_chrome_dir,
                headless=True,
                channel="chrome",
                viewport={"width": 1280, "height": 1024}
            )
            
            page = context.new_page()
            
            # Fjern 'webdriver'-flaget i browserens JS-kerne inden siden loades
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Find bund-rækkerne
            total_rows = page.locator("tr.bottom")
            total_rows.first.wait_for(state="visible", timeout=15000)
            
            # Giv lige React tid til at smide tallene ind
            page.wait_for_timeout(1000)
            
            nutrition_payload = None
            antat_raekker = total_rows.count()
            
            for i in range(antat_raekker):
                cells = total_rows.nth(i).locator("td").all_inner_texts()
                
                # Hvis rækken har data og celle 1 indeholder et reelt tal (ikke tom eller bare space)
                if len(cells) > 1 and cells[1].strip() != "" and re.search(r"\d+", cells[1]):
                    def rens_tal(tekst):
                        match = re.search(r"(-?\d+)", tekst.replace(",", ""))
                        return int(match.group(1)) if match else 0

                    nutrition_payload = {
                        "date": dato_streng,
                        "calories": rens_tal(cells[1]),
                        "carbohydrates": rens_tal(cells[2]),
                        "fat": rens_tal(cells[3]),
                        "protein": rens_tal(cells[4]),
                    }
                    break

            if not nutrition_payload:
                nutrition_payload = {"date": dato_streng, "calories": 0, "carbohydrates": 0, "fat": 0, "protein": 0}
            
            context.close()
            return nutrition_payload

        except Exception as e:
            print(f"[FEJL] Fejl under hentning: {e}")
            if 'context' in locals():
                context.close()
            return None

if __name__ == "__main__":
    data = hent_kalorier_kontor("2026-05-13")
    print("\nResultat afviklet i terminalen:")
    print(data)