import datetime as dt
import myfitnesspal
from sys import exit
import settings

def hent_nutrition_data():
    # 1. Hent cookies fra miljøet (.env)
    mfp_b = settings.MFP_COOKIE_B
    mfp_session = settings.MFP_COOKIE_SESSION

    if not mfp_b or not mfp_session:
        print("FEJL: Miljøvariablerne MFP_COOKIE_B og MFP_COOKIE_SESSION skal være sat.")
        exit(1)

    # 2. Forbered cookie-dict til klienten
    cookie_dict = {
        "b": mfp_b,
        "user_session": mfp_session
    }

    try:
        print("Forbinder til MyFitnessPal via injected sessions-cookies...")
        client = myfitnesspal.Client(cookies=cookie_dict)
        
        # Hent data for i dag
        i_dag = dt.date.today()
        day = client.get_date(i_dag)
        
        # 3. Træk de rå værdier ud
        totals = day.totals
        
        # Returner et rent dictionary, som du nemt kan sende videre i dit projekt
        nutrition_payload = {
            "date": i_dag.isoformat(),
            "calories": totals.get("calories", 0),
            "protein": totals.get("protein", 0),
            "carbohydrates": totals.get("carbohydrates", 0),
            "fat": totals.get("fat", 0)
        }
        
        print(f"Succes! Hentet data for {i_dag}: {nutrition_payload['calories']} kcal")
        return nutrition_payload

    except Exception as e:
        print(f"Fejl under hentning af data fra MyFitnessPal: {e}")
        print("Tjek om dine cookies i Docker-miljøet er udløbet.")
        exit(1)

if __name__ == "__main__":
    data = hent_nutrition_data()
    print("\nPayload klar til næste step i projektet:")
    print(data)