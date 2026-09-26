import os
import re
import json
import urllib.request
import urllib.error

def clean_html_fences(raw_text: str) -> str:
    raw_text = re.sub(r'^```html\s*', '', raw_text.strip())
    raw_text = re.sub(r'```$', '', raw_text).strip()
    return raw_text


def query_openrouter(prompt_instruction: str, api_key: str) -> str:
    """Queries OpenRouter using high-speed flash models that complete in ~2-3 seconds."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://marketplace-beryl-delta.vercel.app",
        "X-Title": "Marketplace Kiosk Engine"
    }

    # Fast 2.5-second model to comfortably beat Vercel's execution window
    model_name = os.environ.get('OPENROUTER_MODEL') or 'google/gemini-2.0-flash-001'

    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt_instruction}
        ]
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data['choices'][0]['message']['content']
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode('utf-8')
        print(f"OpenRouter HTTP {e.code} Error Details: {error_msg}")
        return None
    except Exception as e:
        print(f"OpenRouter Connection Error: {e}")
        return None


def generate_kiosk_template(kiosk_name: str, bio: str, prompt: str, logo_url: str = '', hero_url: str = '', bg_url: str = '', currency: str = '₦') -> str:
    system_instruction = (
        f'You are an expert web designer creating a custom storefront website for a brand named "{kiosk_name}".\n'
        f'Merchant Design Instructions: "{prompt}"\n'
        f'Merchant Bio: "{bio}"\n\n'
        f'Brand Assets: Logo="{logo_url}", Hero="{hero_url}", Background="{bg_url}", Currency="{currency}".\n'
        'Write a COMPLETE, BEAUTIFUL, MOBILE-FIRST HTML5 page using Tailwind CSS via CDN and Google Fonts.\n'
        'CRITICAL JINJA2 & JAVASCRIPT CONTRACT (DO NOT DEVIATE):\n'
        '1. In the <head> or top of <body>, you MUST declare this exact dictionary to store products safely:\n'
        '   <script>\n'
        '     window.KIOSK_PRODUCTS = {\n'
        '       {% for p in regular_products + flash_sales %}\n'
        '         "{{ p.id }}": {\n'
        '           "id": {{ p.id }},\n'
        '           "name": {{ p.name|tojson }},\n'
        '           "price": {{ p.current_price }},\n'
        '           "description": {{ p.description|tojson }},\n'
        '           "attributes": {{ p.get_attributes()|tojson }}\n'
        '         },\n'
        '       {% endfor %}\n'
        '     };\n'
        '   </script>\n'
        '2. Product Buttons: Every product card order button MUST call: onclick="openProductModal({{ p.id }})"\n'
        '3. Slide-Out Shopping Bag: Include <aside id="cartDrawer"> with <div id="cartItemsList">, <span id="cartTotalPrice">, '
        'and the checkout form (<form onsubmit="handleCheckout(event)">) with #custName, #custPhone, #custAddress, and #checkoutBtn.\n'
        '4. Interactive Script: Include the complete functions for toggleCart(), openProductModal(id), closeProductModal(), '
        'confirmAddToCart(), updateCartUI(), and handleCheckout(event) sending POST to /{{ store.slug }}/checkout.\n'
        'Output ONLY pure HTML.'
    )

    # 1. Primary: Google Gemini
    gemini_key = (os.environ.get('AI_API_KEY') or '').strip()
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(system_instruction)
            raw_html = clean_html_fences(response.text)
            if raw_html:
                print("Generated custom kiosk via Primary: Gemini!")
                return raw_html
        except Exception as e:
            print(f"Gemini API error: {e}")

    # 2. Fast Backup: OpenRouter
    openrouter_key = (os.environ.get('OPENROUTER_API_KEY') or '').strip()
    if openrouter_key:
        raw_response = query_openrouter(system_instruction, openrouter_key)
        if raw_response:
            raw_html = clean_html_fences(raw_response)
            if raw_html:
                print("Generated custom kiosk via Backup: OpenRouter!")
                return raw_html

    # 3. Bulletproof Tailored Fallback Template
    bg_style = f"background-image: url('{bg_url}'); background-size: cover; background-attachment: fixed;" if bg_url else "background-color: #fdfcfb;"
    logo_img = f"<img src='{logo_url}' class='h-10 w-10 object-contain rounded-full'>" if logo_url else ""
    hero_div = f"<div class='max-w-6xl mx-auto px-6 mt-6 w-full'><img src='{hero_url}' class='w-full h-48 md:h-64 object-cover rounded-2xl shadow-sm'></div>" if hero_url else ""

    fallback_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ store.name }} // Official Store</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
    <style>body { font-family: 'Montserrat', sans-serif; __BG_STYLE__ }</style>

    <script>
        window.KIOSK_PRODUCTS = {
            {% for p in regular_products + flash_sales %}
            "{{ p.id }}": {
                "id": {{ p.id }},
                "name": {{ p.name|tojson }},
                "price": {{ p.current_price }},
                "description": {{ p.description|tojson }},
                "attributes": {{ p.get_attributes()|tojson }}
            },
            {% endfor %}
        };
    </script>
</head>
<body class="min-h-screen text-stone-900 flex flex-col justify-between">
    <header class="bg-white/95 backdrop-blur border-b border-stone-200 py-4 px-6 sticky top-0 z-40">
        <div class="max-w-6xl mx-auto flex items-center justify-between">
            <div class="flex items-center gap-3">
                __LOGO_IMG__
                <div>
                    <h1 class="text-lg font-bold tracking-tight text-stone-900 m-0">{{ store.name }}</h1>
                    <p class="text-xs text-stone-500 m-0">{{ store.bio }}</p>
                </div>
            </div>
            <button onclick="toggleCart()" class="bg-stone-900 hover:bg-black text-white text-xs font-bold px-4 py-2 rounded-xl flex items-center gap-2">
                <span>BAG</span>
                <span id="cartCountBadge" class="bg-amber-500 text-stone-900 px-1.5 py-0.5 rounded-full text-[10px]">0</span>
            </button>
        </div>
    </header>

    __HERO_DIV__

    <main class="max-w-6xl mx-auto px-6 py-10 w-full flex-grow">
        {% if flash_sales %}
        <div class="mb-10">
            <h2 class="text-sm font-bold uppercase tracking-wider text-rose-600 mb-4">🔥 Flash Deals</h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                {% for p in flash_sales %}
                <div class="bg-white p-5 rounded-2xl shadow-sm border border-stone-100 flex flex-col justify-between">
                    <div>
                        <img src="{{ p.image if p.image.startswith('http') else url_for('static', filename='uploads/products/' + p.image) }}" class="h-44 w-full object-cover rounded-xl mb-3">
                        <h3 class="font-bold text-sm">{{ p.name }}</h3>
                        <p class="text-xs text-stone-400 mb-2">{{ p.description }}</p>
                    </div>
                    <div>
                        <div class="mb-3">
                            <span class="line-through text-stone-400 text-xs">{{ store.currency }}{{ "{:,.2f}".format(p.original_price) }}</span>
                            <span class="font-bold text-rose-600 text-base ml-1">{{ store.currency }}{{ "{:,.2f}".format(p.current_price) }}</span>
                        </div>
                        <button type="button" onclick="openProductModal({{ p.id }})" class="w-full bg-rose-600 hover:bg-rose-700 text-white font-bold py-2.5 rounded-xl text-xs uppercase cursor-pointer">
                            SELECT & ORDER
                        </button>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        <h2 class="text-lg font-bold text-stone-800 mb-6">Catalog</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
            {% for p in regular_products %}
            <div class="bg-white p-5 rounded-2xl shadow-sm border border-stone-100 flex flex-col justify-between">
                <div>
                    <img src="{{ p.image if p.image.startswith('http') else url_for('static', filename='uploads/products/' + p.image) }}" class="h-44 w-full object-cover rounded-xl mb-3">
                    <h3 class="font-bold text-sm text-stone-900">{{ p.name }}</h3>
                    <p class="text-xs text-stone-400 mb-3">{{ p.description }}</p>
                </div>
                <div>
                    <div class="font-bold text-stone-900 text-sm mb-3">{{ store.currency }}{{ "{:,.2f}".format(p.current_price) }}</div>
                    {% if p.stock > 0 %}
                    <button type="button" onclick="openProductModal({{ p.id }})" class="w-full bg-stone-900 hover:bg-black text-white font-bold py-2.5 rounded-xl text-xs uppercase tracking-wider cursor-pointer">
                        VIEW SPECS & ORDER
                    </button>
                    {% else %}
                    <button disabled class="w-full bg-stone-100 text-stone-400 py-2.5 rounded-xl text-xs uppercase">Sold Out</button>
                    {% endif %}
                </div>
            </div>
            {% else %}
            <p class="text-xs italic text-stone-400 col-span-3">No products available in this kiosk yet.</p>
            {% endfor %}
        </div>
    </main>

    <!-- Product Modal -->
    <div id="productModal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4 hidden">
        <div class="bg-white p-6 max-w-sm w-full rounded-2xl shadow-2xl relative">
            <button type="button" onclick="closeProductModal()" class="absolute top-3 right-3 text-stone-400 font-bold text-xl cursor-pointer">&times;</button>
            <h3 id="modalProductName" class="font-bold text-base mb-1 text-stone-900"></h3>
            <p id="modalProductDesc" class="text-xs text-stone-500 mb-3 leading-relaxed"></p>
            <p id="modalProductPrice" class="text-emerald-600 font-bold text-base mb-4"></p>
            <div id="modalVariantsContainer" class="space-y-3 mb-5"></div>
            <button type="button" onclick="confirmAddToCart()" class="w-full bg-stone-900 hover:bg-black text-white font-bold py-3 rounded-xl text-xs uppercase cursor-pointer">
                ADD TO BAG &rarr;
            </button>
        </div>
    </div>

    <!-- Shopping Bag Drawer -->
    <div id="cartOverlay" onclick="toggleCart()" class="fixed inset-0 bg-black/40 z-40 hidden"></div>
    <aside id="cartDrawer" class="fixed top-0 right-0 h-full w-full max-w-md bg-white z-50 shadow-2xl p-6 flex flex-col justify-between translate-x-ful
