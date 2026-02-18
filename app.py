
import streamlit as st
import requests
import re
import time

# --- API Helper Class ---
class ReverbManager:
    def __init__(self, token):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/hal+json",
            "Accept": "application/hal+json",
            "Accept-Version": "3.0"
        }
        self.base_url = "https://api.reverb.com/api"

    def get_listing_id(self, url):
        match = re.search(r'item/(\d+)', url)
        return match.group(1) if match else None

    def fetch_source(self, listing_id):
        res = requests.get(f"{self.base_url}/listings/{listing_id}", headers=self.headers)
        return res.json() if res.status_code == 200 else None

    def create_draft(self, src, ship_id):
        try:
            amount = float(src.get("price", {}).get("amount", "0").replace(",", ""))
            new_price = f"{(amount * 0.4):.2f}"
        except: new_price = "0.00"

        payload = {
            "make": src.get("make"),
            "model": src.get("model"),
            "title": src.get("title"),
            "description": src.get("description"),
            "offers_enabled": False,
            "shipping_profile_id": int(ship_id),
            "price": {"amount": new_price, "currency": src.get("price", {}).get("currency", "USD")}
        }
        if src.get("categories"): payload["categories"] = [{"uuid": src["categories"][0].get("uuid")}]
        if src.get("condition"): payload["condition"] = {"uuid": src["condition"].get("uuid")}
        
        photo_urls = []
        for p in src.get("photos", []):
            url = p.get("_links", {}).get("large_crop", {}).get("href") or p.get("_links", {}).get("full", {}).get("href")
            if url: photo_urls.append(url)
        payload["photos"] = photo_urls

        return requests.post(f"{self.base_url}/listings", headers=self.headers, json=payload)

    def get_drafts(self):
        res = requests.get(f"{self.base_url}/my/listings?state=draft", headers=self.headers)
        return res.json().get("listings", []) if res.status_code == 200 else []

    def publish(self, listing_id):
        res = requests.put(f"{self.base_url}/listings/{listing_id}", headers=self.headers, json={"publish": True})
        return res.status_code in [200, 201, 204]

# --- Streamlit Layout ---
st.set_page_config(page_title="Reverb Manager", layout="wide")

# 1. API Token Check
if "token" not in st.session_state:
    st.title("🔑 Reverb Login")
    token_input = st.text_input("Enter Reverb API Token:", type="password")
    if st.button("Connect"):
        if token_input:
            st.session_state.token = token_input
            st.rerun()
    st.stop()

# Initialize API
api = ReverbManager(st.session_state.token)

# 2. GLOBAL REFRESH BUTTON (Always at the top)
col_title, col_refresh = st.columns([0.85, 0.15])
with col_title:
    st.title("🎸 Reverb Listing Manager")
with col_refresh:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

st.divider()

# 3. TABS (Removed History Tab)
tab1, tab2 = st.tabs(["🆕 Create Drafts", "📋 Manage Drafts"])

# --- TAB 1: CLONING ---
with tab1:
    st.header("Bulk Clone at 50% Off")
    urls_input = st.text_area("Paste URLs (one per line or comma-separated)", height=150)
    ship_id = st.text_input("Shipping Profile ID")
    
    if st.button("🚀 Generate Drafts"):
        if not urls_input or not ship_id:
            st.warning("Please provide both URLs and a Shipping Profile ID.")
        else:
            urls = [u.strip() for u in urls_input.replace("\n", ",").split(",") if u.strip()]
            progress = st.progress(0)
            for i, url in enumerate(urls):
                l_id = api.get_listing_id(url)
                src = api.fetch_source(l_id)
                if src:
                    res = api.create_draft(src, ship_id)
                    if res.status_code in [201, 202]:
                        st.toast(f"Created: {src['title']}")
                    else:
                        st.error(f"Failed {url}: {res.status_code}")
                time.sleep(2) 
                progress.progress((i + 1) / len(urls))
            st.success("Batch Complete! Refresh the Manage tab to see them.")

# --- TAB 2: MANAGEMENT ---
with tab2:
    st.header("Drafts Ready to Publish")
    drafts = api.get_drafts()
    
    if not drafts:
        st.info("No drafts found on your account. Try creating some in the first tab!")
    else:
        for d in drafts:
            # Cards for each draft
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.write(f"**{d['title']}**")
                    st.caption(f"Price: {d['price']['amount']} {d['price']['currency']} | Draft ID: {d['id']}")
                with c2:
                    if st.button("🚀 Publish", key=f"p_{d['id']}", use_container_width=True):
                        if api.publish(d['id']):
                            st.success(f"Live!")
                            time.sleep(1) # Brief pause so the success message is visible
                            st.rerun() # Refresh to remove published item from list
                        else:
                            st.error("Error publishing.")
