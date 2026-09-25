import os
import re
import json
import urllib.request
import urllib.error

def clean_html_fences(raw_text: str) -> str:
    """Strips markdown code fences like ```html ... ```."""
    raw_text = re.sub(r'^```html\s*', '', raw_text.strip())
    raw_text = re.sub(r'```$', '', raw_text).strip()
    return raw_text


def query_openrouter(prompt_instruction: str, api_key: str) -> str:
    """Queries OpenRouter API (Failover engine)."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://marketplace.local",
        "X-Title": "Marketplace Kiosk Engine"
    }

    model_name = os.environ.get('OPENROUTER_MODEL', 'qwen/qwen-2.5-72b-instruct')

    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt_instruction}
        ]
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=45) as response:
        res_data = json.loads(response.read().decode('utf-8'))
        return res_data['choices'][0]['message']['content']


def generate_kiosk_template(kiosk_name: str, bio: str, prompt: str, logo_url: str = '', hero_url: str = '', bg_url: str = '', currency: str = '₦') -> str:
    """
    Master AI Kiosk Generator:
    Takes merchant instructions & Cloudinary assets, and generates a complete,
    interactive, high-converting storefront via Gemini or OpenRouter.
    """
    
    # 🎯 THE MASTER SYSTEM PROMPT CONTRACT
    system_instruction = (
        f'You are an elite Lead UI/UX Engineer and Web Designer creating an exclusive, high-converting storefront website for a merchant named "{kiosk_name}".\n\n'
        f'MERCHANT DESIGN INSTRUCTIONS:\n'
        f'- Vibe & Style Request: "{prompt}"\n'
        f'- Merchant Bio: "{bio}"\n'
        f'- Brand Assets Available:\n'
        f'  • Logo URL: "{logo_url}"\n'
        f'  • Hero Showcase Banner URL: "{hero_url}"\n'
        f'  • Background Wallpaper URL: "{bg_url}"\n'
        f'  • Currency Symbol: "{currency}"\n\n'
        'YOUR OBJECTIVE:\n'
        'Generate a COMPLETE, STANDALONE, MOBILE-FIRST HTML5 page using Tailwind CSS via CDN and Google Fonts that strictly matches the merchant\'s requested aesthetic (e.g. cyber dark-mode, luxury minimalist, or vibrant boutique).\n\n'
        'CRITICAL ARCHITECTURAL CONTRACT (DO NOT OMIT ANY OF THESE):\n\n'
        '1. HEADER & NAVIGATION:\n'
        '   - Sticky top bar with brand logo/name and a live "BAG" button.\n'
        '   - The bag button MUST contain an element with ID "cartCountBadge" displaying the item count.\n\n'
        '2. HERO SHOWCASE:\n'
        '   - High-impact visual hero section matching the merchant\'s prompt (using hero_url if provided, or a sleek container).\n'
        '   - Prominent headline, sub-headline, and an instant delivery/trust badge.\n\n'
        '3. PRODUCT CATALOG & ORDER BUTTONS:\n'
        '   - You MUST iterate over regular products using this exact Jinja2 syntax:\n'
        '     {% for p in regular_products %}\n'
        '       ... Display product image ({{ p.image if p.image.startswith("http") else url_for("static", filename="uploads/products/" + p.image) }}), '
        'title ({{ p.name }}), description ({{ p.description }}), '
        'and pricing with strikethrough if discounted.\n'
        '       ... You MUST include an order button calling:\n'
        '           openProductModal(p.id, p.name, p.current_price, p.get_attributes(), p.description)\n'
        '     {% endfor %}\n\n'
        '4. FLASH SALES CAROUSEL:\n'
        '   - Include: {% if flash_sales %} ... {% for p in flash_sales %} ... {% endfor %} {% endif %}\n\n'
        '5. PRODUCT SPECS & VARIANT MODAL:\n'
        '   - Include a hidden modal (<div id="productModal" class="hidden ...">) containing:\n'
        '     • Title element with ID: "modalProductName"\n'
        '     • Description element with ID: "modalProductDesc"\n'
        '     • Price element with ID: "modalProductPrice"\n'
        '     • Dynamic variants container with ID: "modalVariantsContainer"\n'
        '     • Confirm button calling confirmAddToCart()\n'
        '     • Close button calling closeProductModal()\n\n'
        '6. SLIDE-OUT SHOPPING BAG DRAWER:\n'
        '   - Include an aside drawer (<aside id="cartDrawer" ...>) containing:\n'
        '     • Close button calling toggleCart()\n'
        '     • Cart items container with ID: "cartItemsList"\n'
        '     • Total display with ID: "cartTotalPrice"\n'
        '     • The Customer Checkout Form (<form onsubmit="handleCheckout(event)">) with:\n'
        '       - Full Name input (id="custName", required)\n'
        '       - WhatsApp Number input (id="custPhone", required)\n'
        '       - Delivery Notes/Address input (id="custAddress", required)\n'
        '       - Submit button (id="checkoutBtn") with text "COMPLETE ORDER ON WHATSAPP →"\n\n'
        '7. COMPLETE JAVASCRIPT ENGINE (MANDATORY - DO NOT OMIT):\n'
        '   - You MUST include the full implementations for:\n'
        '     • toggleCart()\n'
        '     • openProductModal(id, name, price, attributes, desc)\n'
        '     • closeProductModal()\n'
        '     • confirmAddToCart()\n'
        '     • updateCartUI()\n'
        '     • handleCheckout(event) — submits JSON to /{{ store.slug }}/checkout via POST and redirects to data.whatsapp_url upon success.\n\n'
        'OUTPUT FORMAT RULES:\n'
        '- Output ONLY clean HTML5 markup.\n'
        '- Do NOT wrap in markdown code fences.\n'
        '- Every single interactive component (modal, drawer, buttons, JS engine) MUST be fully written out. No placeholders.'
    )

    # -------------------------------------------------------------
    # TIER 1: GOOGLE GEMINI API
    # -------------------------------------------------------------
    gemini_key = os.environ.get('AI_API_KEY')
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(system_instruction)
            raw_html = clean_html_fences(response.text)
            if raw_html and '<body' in raw_html:
                print("Generated kiosk template using Primary: Google Gemini!")
                return raw_html
        except Exception as e:
            print(f"Tier 1 (Gemini) notice: {e}. Failing over to Tier 2 (OpenRouter)...")

    # -------------------------------------------------------------
    # TIER 2: OPENROUTER API (FAILOVER)
    # -------------------------------------------------------------
    openrouter_key = os.environ.get('OPENROUTER_API_KEY')
    if openrouter_key:
        try:
            raw_response = query_openrouter(system_instruction, openrouter_key)
            raw_html = clean_html_fences(raw_response)
            if raw_html and '<body' in raw_html:
                print("Generated kiosk template using Backup: OpenRouter (Qwen/Llama)!")
                return raw_html
        except Exception as e:
            print(f"Tier 2 (OpenRouter) notice: {e}. Using tailored fallback template.")

    # -------------------------------------------------------------
    # TIER 3: TAILORED FALLBACK TEMPLATE
    # -------------------------------------------------------------
    bg_style = f"background-image: url('{bg_url}'); background-size: cover; background-attachment: fixed;" if bg_url else "background-color: #09090b;"
    logo_img = f"<img src='{logo_url}' class='h-10 w-10 object-contain rounded-xl border border-cyan-500/30'>" if logo_url else "<div class='h-10 w-10 bg-cyan-950 border border-cyan-500/40 rounded-xl flex items-center justify-center font-mono font-bold text-cyan-400'>&lt;/&gt;</div>"
    hero_div = f"<div class='max-w-6xl mx-auto px-6 mt-8 w-full'><img src='{hero_url}' class='w-full h-48 md:h-64 object-cover rounded-3xl shadow-sm border border-stone-800'></div>" if hero_url else ""

    fallback_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ store.name }} // Official Store</title>
    <meta property="og:title" content="{{ store.name }}">
    <meta property="og:description" content="{% if store.show_public_stats %}Over {{ '{:,}'.format(store.views_count) }} visits • Verified Merchant{% else %}{{ store.bio }}{% endif %}">
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { 
            font-family: 'Montserrat', sans-serif; 
            __BG_STYLE__
            color: #f4f4f5;
        }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
        .cyber-border {
            border: 1px solid rgba(6, 182, 212, 0.2);
            transition: all 0.3s ease;
        }
        .cyber-border:hover {
            border-color: rgba(6, 182, 212, 0.6);
            box-shadow: 0 0 20px rgba(6, 182, 212, 0.15);
        }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between selection:bg-cyan-500 selection:text-black">
    <header class="bg-[#0e0e12]/90 backdrop-blur border-b border-cyan-950/60 py-4 px-6 sticky top-0 z-40">
        <div class="max-w-6xl mx-auto flex items-center justify-between">
            <div class="flex items-center gap-3">
                __LOGO_IMG__
                <div>
                    <h1 class="text-base font-bold tracking-tight text-white font-mono m-0 flex items-center gap-2">
                        {{ store.name }}
                        <span class="text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded font-mono font-semibold">VERIFIED</span>
                    </h1>
                    <p class="text-xs text-stone-400 m-0">{{ store.bio }}</p>
                </div>
            </div>
            <button onclick="toggleCart()" class="bg-cyan-500 hover:bg-cyan-400 text-black font-mono font-bold text-xs px-4 py-2.5 rounded-xl uppercase tracking-wider flex items-center gap-2 transition shadow-lg shadow-cyan-500/20">
                <span>BAG</span>
                <span id="cartCountBadge" class="bg-black text-cyan-400 px-2 py-0.5 rounded-full text-[10px] font-bold">0</span>
            </button>
        </div>
    </header>

    __HERO_DIV__

    <main class="max-w-6xl mx-auto px-6 py-12 w-full flex-grow">
        {% if flash_sales %}
        <div class="mb-12">
            <div class="flex items-center gap-2 mb-6">
                <span class="bg-rose-950 text-rose-400 border border-rose-500/30 font-mono text-xs font-bold px-3 py-1 rounded-md uppercase tracking-wider">
                    🔥 Flash Deal
                </span>
                <span class="text-xs text-stone-400 font-mono">Limited license inventory</span>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                {% for p in flash_sales %}
                <div class="bg-[#121217] cyber-border p-6 rounded-2xl flex flex-col justify-between">
                    <div>
                        <img src="{{ p.image if p.image.startswith('http') else url_for('static', filename='uploads/products/' + p.image) }}" class="h-48 w-full object-cover rounded-xl mb-4 border border-stone-800">
                        <span class="text-[10px] font-mono text-cyan-400 uppercase tracking-wider block mb-1">[FEATURED ASSET]</span>
                        <h3 class="font-bold text-base text-white mb-2">{{ p.name }}</h3>
                        <p class="text-xs text-stone-400 mb-4 line-clamp-2">{{ p.description }}</p>
                    </div>
                    <div>
                        <div class="mb-4 font-mono">
                            <span class="line-through text-stone-500 text-xs">{{ store.currency }}{{ "{:,.2f}".format(p.original_price) }}</span>
                            <span class="font-bold text-rose-400 text-lg ml-2">{{ store.currency }}{{ "{:,.2f}".format(p.current_price) }}</span>
                        </div>
                        <button onclick='openProductModal({{ p.id }}, {{ p.name|tojson }}, {{ p.current_price }}, {{ p.get_attributes()|tojson }}, {{ p.description|tojson }})' 
                                class="w-full bg-rose-600 hover:bg-rose-500 text-white font-mono font-bold py-3 rounded-xl text-xs uppercase tracking-wider transition">
                            SELECT & ORDER &rarr;
                        </button>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        <div class="flex items-center justify-between mb-8 pb-4 border-b border-stone-800">
            <h2 class="text-lg font-bold font-mono uppercase tracking-wider text-white">Catalog</h2>
            <span class="text-xs text-stone-400 font-mono">{{ regular_products|length }} verified items</span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
            {% for p in regular_products %}
            <div class="bg-[#121217] cyber-border p-6 rounded-2xl flex flex-col justify-between">
                <div>
                    <img src="{{ p.image if p.image.startswith('http') else url_for('static', filename='uploads/products/' + p.image) }}" class="h-48 w-full object-cover rounded-xl mb-4 border border-stone-800">
                    <span class="text-[10px] font-mono text-emerald-400 uppercase tracking-wider block mb-1">[READY FOR ORDER]</span>
                    <h3 class="font-bold text-base text-white mb-2">{{ p.name }}</h3>
                    <p class="text-xs text-stone-400 mb-4 leading-relaxed">{{ p.description }}</p>
                </div>
                <div>
                    <div class="font-mono mb-4">
                        {% if p.has_discount %}
                            <span class="line-through text-stone-500 text-xs">{{ store.currency }}{{ "{:,.2f}".format(p.original_price) }}</span>
                            <span class="font-bold text-cyan-400 text-lg ml-1">{{ store.currency }}{{ "{:,.2f}".format(p.discount_price) }}</span>
                        {% else %}
                            <span class="font-bold text-cyan-400 text-lg">{{ store.currency }}{{ "{:,.2f}".format(p.original_price) }}</span>
                        {% endif %}
                        <span class="text-[10px] text-stone-500 block font-mono mt-0.5">{{ p.stock }} units available</span>
                    </div>

                    {% if p.stock > 0 %}
                    <button onclick='openProductModal({{ p.id }}, {{ p.name|tojson }}, {{ p.current_price }}, {{ p.get_attributes()|tojson }}, {{ p.description|tojson }})' 
                            class="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-mono font-bold py-3 rounded-xl text-xs uppercase tracking-wider transition shadow-lg shadow-cyan-500/10">
                        VIEW SPECS & ORDER &rarr;
                    </button>
                    {% else %}
                    <button disabled class="w-full bg-stone-800 text-stone-500 font-mono py-3 rounded-xl text-xs uppercase">SOLD OUT</button>
                    {% endif %}
                </div>
            </div>
            {% else %}
            <p class="text-xs italic text-stone-500 col-span-3">No regular items listed yet.</p>
            {% endfor %}
        </div>
    </main>

    <!-- Product Specs & Variants Modal -->
    <div id="productModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 hidden">
        <div class="bg-[#121217] border border-cyan-800/60 p-8 max-w-md w-full rounded-3xl shadow-2xl relative">
            <button onclick="closeProductModal()" class="absolute top-4 right-4 text-stone-400 hover:text-white font-bold text-xl">&times;</button>
            <span class="text-[10px] font-mono text-cyan-400 uppercase tracking-widest block mb-1">Configuration & Specs</span>
            <h3 id="modalProductName" class="font-bold text-lg text-white mb-2"></h3>
            <p id="modalProductDesc" class="text-xs text-stone-400 mb-4 leading-relaxed"></p>
            <p id="modalProductPrice" class="font-mono text-xl font-black text-cyan-400 mb-6"></p>
            <div id="modalVariantsContainer" class="space-y-4 mb-6"></div>
            <button onclick="confirmAddToCart()" class="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-mono font-bold py-3.5 rounded-xl text-xs uppercase tracking-wider transition">
                CONFIRM & ADD TO BAG &rarr;
            </button>
        </div>
    </div>

    <!-- Slide-Out Shopping Bag Drawer with Real WhatsApp Checkout -->
    <div id="cartOverlay" onclick="toggleCart()" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 hidden"></div>
    <aside id="cartDrawer" class="fixed top-0 right-0 h-full w-full max-w-md bg-[#121217] border-l border-stone-800 z-50 p-6 flex flex-col justify-between translate-x-full transition-transform duration-300">
        <div>
            <div class="flex justify-between items-center pb-4 border-b border-stone-800 mb-6">
                <div>
                    <h3 class="font-mono font-bold text-sm uppercase tracking-wider text-white m-0">Your Bag</h3>
                    <span class="text-[10px] text-stone-400 font-mono">Order Intake</span>
                </div>
                <button onclick="toggleCart()" class="text-xs font-mono font-bold text-stone-400 hover:text-white">&times; CLOSE</button>
            </div>
            <div id="cartItemsList" class="space-y-3 max-h-[40vh] overflow-y-auto pr-1"></div>
        </div>

        <div class="pt-6 border-t border-stone-800">
            <div class="flex justify-between items-center mb-6 font-mono">
                <span class="text-xs uppercase text-stone-400">Total:</span>
                <span id="cartTotalPrice" class="font-bold text-xl text-cyan-400">{{ store.currency }}0.00</span>
            </div>

            <form onsubmit="handleCheckout(event)" class="space-y-3">
                <div>
                    <label class="block text-[10px] font-mono uppercase text-stone-400 mb-1">Your Full Name</label>
                    <input type="text" id="custName" required placeholder="e.g. Alex Trader" 
                           class="w-full p-3 bg-[#18181f] border border-stone-800 rounded-xl text-xs text-white outline-none focus:border-cyan-500">
                </div>
                <div>
                    <label class="block text-[10px] font-mono uppercase text-stone-400 mb-1">WhatsApp Phone (For Delivery)</label>
                    <input type="text" id="custPhone" required placeholder="e.g. 08012345678" 
                           class="w-full p-3 bg-[#18181f] border border-stone-800 rounded-xl text-xs text-white outline-none focus:border-cyan-500">
                </div>
                <div>
                    <label class="block text-[10px] font-mono uppercase text-stone-400 mb-1">Delivery Destination / Email / Notes</label>
                    <textarea id="custAddress" required placeholder="Enter delivery details, address, or email" rows="2" 
                              class="w-full p-3 bg-[#18181f] border border-stone-800 rounded-xl text-xs text-white outline-none focus:border-cyan-500"></textarea>
                </div>

                <button type="submit" id="checkoutBtn" 
                        class="w-full bg-emerald-500 hover:bg-emerald-400 text-black font-mono font-bold py-4 rounded-xl text-xs uppercase tracking-wider transition shadow-lg shadow-emerald-500/20">
                    COMPLETE ORDER ON WHATSAPP &rarr;
                </button>
            </form>
        </div>
    </aside>

    <footer class="bg-[#0e0e12] border-t border-stone-900 py-8 text-center text-xs font-mono text-stone-500">
        Powered by <a href="/" class="text-cyan-400 font-bold hover:underline">Marketplace</a>
    </footer>

    <script>
        const storeSlug = {{ store.slug|tojson }};
        const storeCurrency = {{ store.currency|tojson }};
        let cart = [];
        let currentModalProduct = null;

        function toggleCart() {
            document.getElementById('cartDrawer').classList.toggle('translate-x-full');
            document.getElementById('cartOverlay').classList.toggle('hidden');
        }

        function openProductModal(id, name, price, attributes, desc) {
            currentModalProduct = { id, name, price, attributes };
            document.getElementById('modalProductName').innerText = name;
            document.getElementById('modalProductDesc').innerText = desc || 'Item details.';
            document.getElementById('modalProductPrice').innerText = `${storeCurrency}${price.toLocaleString()}`;

            const container = document.getElementById('modalVariantsContainer');
            container.innerHTML = '';

            if (attributes && Object.keys(attributes).length > 0) {
                for (const [attrName, options] of Object.entries(attributes)) {
                    const group = document.createElement('div');
                    group.innerHTML = `
                        <label class="block font-mono text-[10px] uppercase text-cyan-400 mb-1 font-bold">${attrName}</label>
                        <select class="variant-select w-full p-2.5 bg-[#18181f] border border-stone-800 text-white font-mono text-xs rounded-lg outline-none focus:border-cyan-500" data-attr="${attrName}">
                            ${options.map(opt => `<option value="${opt}">${opt}</option>`).join('')}
                        </select>
                    `;
                    container.appendChild(group);
                }
            }

            document.getElementById('productModal').classList.remove('hidden');
        }

        function closeProductModal() {
            document.getElementById('productModal').classList.add('hidden');
            currentModalProduct = null;
        }

        function confirmAddToCart() {
            if (!currentModalProduct) return;

            const selectedVariants = [];
            document.querySelectorAll('.variant-select').forEach(select => {
                selectedVariants.push(`${select.getAttribute('data-attr')}: ${select.value}`);
            });

            cart.push({
                product_id: currentModalProduct.id,
                name: currentModalProduct.name,
                price: currentModalProduct.price,
                variants: selectedVariants.join(' | '),
                quantity: 1
            });

            updateCartUI();
            closeProductModal();
            toggleCart();
        }

        function updateCartUI() {
            const list = document.getElementById('cartItemsList');
            const badge = document.getElementById('cartCountBadge');
            const totalEl = document.getElementById('cartTotalPrice');

            badge.innerText = cart.length;
            list.innerHTML = '';
            let total = 0;

            cart.forEach((item, index) => {
                total += item.price * item.quantity;
                const div = document.createElement('div');
                div.className = 'flex justify-between items-start p-3 bg-[#18181f] border border-stone-800 rounded-xl text-xs font-mono';
                div.innerHTML = `
                    <div>
                        <strong class="text-white block">${item.name}</strong>
                        ${item.variants ? `<span class="text-[10px] text-cyan-400 block">${item.variants}</span>` : ''}
                        <span class="text-emerald-400 font-bold mt-1 block">${storeCurrency}${item.price.toLocaleString()}</span>
                    </div>
                    <button onclick="cart.splice(${index}, 1); updateCartUI();" class="text-rose-400 hover:text-rose-300 font-bold ml-3 text-base">&times;</button>
                `;
                list.appendChild(div);
            });

            totalEl.innerText = `${storeCurrency}${total.toLocaleString()}`;
        }

        async function handleCheckout(event) {
            event.preventDefault();
            if (cart.length === 0) {
                alert('Your bag is empty. Please select an item first.');
                return;
            }

            const btn = document.getElementById('checkoutBtn');
            btn.innerText = 'GENERATING WHATSAPP RECEIPT...';
            btn.disabled = true;

            const payload = {
                customer_name: document.getElementById('custName').value,
                customer_phone: document.getElementById('custPhone').value,
                delivery_address: document.getElementById('custAddress').value,
                cart: cart
            };

            try {
                const res = await fetch(`/${storeSlug}/checkout`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await res.json();
                if (data.status === 'success') {
                    cart = [];
                    updateCartUI();
                    window.location.href = data.whatsapp_url;
                } else {
                    alert(data.message || 'Error creating order.');
                    btn.innerText = 'COMPLETE ORDER ON WHATSAPP →';
                    btn.disabled = false;
                }
            } catch (err) {
                alert('Connection error. Please try again.');
                btn.innerText = 'COMPLETE ORDER ON WHATSAPP →';
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>"""

    return fallback_html.replace("__BG_STYLE__", bg_style).replace("__LOGO_IMG__", logo_img).replace("__HERO_DIV__", hero_div)
