import myfitnesspal
import browser_cookie3

cookies = browser_cookie3.chrome(domain_name="myfitnesspal.com")

MFP_SESSION_TOKEN = None
MFP_CF_CLEARANCE = None

for cookie in cookies:
    if cookie.name == "__Secure-next-auth.session-token":
        mfp_b = cookie.value
    elif cookie.name == "cf_clearance":
        mfp_session = cookie.value

print(f'MFP_SESSION_TOKEN="{mfp_b}"')
print(f'MFP_CF_CLEARANCE="{mfp_session}"')

# client = myfitnesspal.Client()

# day = client.get_date(2026, 5, 2)

breakpoint()