import os
import time
import http.server
import socketserver
import threading
from playwright.sync_api import sync_playwright

os.makedirs('plots/video_screenshots', exist_ok=True)
PORT = 8089
Handler = http.server.SimpleHTTPRequestHandler
Handler.directory = 'signal_site'

def start_server():
    try:
        with socketserver.TCPServer(('', PORT), Handler) as httpd:
            httpd.serve_forever()
    except Exception as e:
        print("Server info:", e)

t = threading.Thread(target=start_server, daemon=True)
t.start()
time.sleep(1)

def safe_scroll_and_screenshot(page, selector, output_path, desc):
    try:
        loc = page.locator(selector)
        if loc.count() > 0:
            loc.first.scroll_into_view_if_needed()
            time.sleep(0.8)
        else:
            print(f"Selector {selector} not found, taking full viewport screenshot")
        page.screenshot(path=output_path)
        print(f"Captured {desc} -> {output_path}")
    except Exception as e:
        print(f"Error capturing {desc}: {e}")

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge')
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto(f'http://localhost:{PORT}/index.html')
    time.sleep(2)

    # 1. Hero Scene
    page.evaluate('window.scrollTo(0, 0)')
    time.sleep(0.5)
    page.screenshot(path='plots/video_screenshots/scene1_hero.png')
    print('Scene 1: Hero screenshot captured')

    # 2. Active Signals Scene
    safe_scroll_and_screenshot(page, '#signals', 'plots/video_screenshots/scene2_signals.png', 'Scene 2: Active Signals')

    # 3. Chart & Cumulative Return
    safe_scroll_and_screenshot(page, '#chart', 'plots/video_screenshots/scene3_chart.png', 'Scene 3: Live Chart')

    # 4. Performance & Track Record
    safe_scroll_and_screenshot(page, '#performance', 'plots/video_screenshots/scene3_trackrecord.png', 'Scene 3: Track Record')

    # 5. Methodology & Proof
    safe_scroll_and_screenshot(page, '#methodology', 'plots/video_screenshots/scene4_methodology.png', 'Scene 4: Methodology')
    safe_scroll_and_screenshot(page, '#compare', 'plots/video_screenshots/scene4_proof.png', 'Scene 4: Proof Table')

    # 6. Pricing Scene
    safe_scroll_and_screenshot(page, '#pricing', 'plots/video_screenshots/scene6_pricing.png', 'Scene 6: Pricing')

    # 7. Checkout Modal
    try:
        page.evaluate('document.getElementById("checkout-modal").classList.add("open")')
        time.sleep(0.8)
        page.screenshot(path='plots/video_screenshots/scene6_checkout_modal.png')
        print('Scene 6: Checkout Modal screenshot captured')
    except Exception as e:
        print('Modal screenshot error:', e)

    browser.close()

print('All screenshots captured successfully!')
