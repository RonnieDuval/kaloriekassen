# utils/generate_env_cookies.py
import browser_cookie3
import sys

def udtræk_mfp_cookies():
    print("Leder efter MyFitnessPal-cookies i din browser...")
    
    try:
        # Henter cookies specifikt for MyFitnessPal fra Chrome
        # (Skift til browser_cookie3.firefox() eller .safari() hvis nødvendigt)
        cj = browser_cookie3.chrome(domain_name="myfitnesspal.com")
    except Exception as e:
        print(f"Fejl: Kunne ikke læse browser-cookies. Er browseren lukket? ({e})")
        sys.exit(1)

    mfp_b = None
    mfp_session = None

    # Loop igennem de fundne cookies for at finde de to vitale
    for cookie in cj:
        if cookie.name == "b":
            mfp_b = cookie.value
        elif cookie.name == "user_session":
            mfp_session = cookie.value

    # Validering
    if not mfp_b or not mfp_session:
        print("\n[!] FEJL: Fandt ikke begge de nødvendige cookies.")
        print("Sørg for, at du er logget ind på myfitnesspal.com i din browser, og prøv igen.")
        sys.exit(1)

    # Output klar til din .env fil
    print("\n================ KOPIER LINJERNE HERUNDER CORREKT IND I DIN .env ================\n")
    print(f'MFP_COOKIE_B="{mfp_b}"')
    print(f'MFP_COOKIE_SESSION="{mfp_session}"')
    print("\n=================================================================================")

if __name__ == "__main__":
    udtræk_mfp_cookies()