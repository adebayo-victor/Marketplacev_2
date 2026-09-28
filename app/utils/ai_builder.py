import os
import re
import json
import urllib.request
import urllib.error

# 🛡️ THE BULLETPROOF INTERACTIVE ENGINE (WITH PURE CSS FAILSAFES - CAN NEVER LEAK ON SCREEN)
GUARANTEED_CART_ENGINE = """
<!-- ========================================== -->
<!-- BULLETPROOF SHOPPING BAG & CHECKOUT ENGINE -->
<!-- ========================================== -->
<style>
    /* Strict Failsafe CSS: Modal & Drawer can NEVER appear at the bottom of the page */
    #productModal {
        display: none !important;
        position: fixed !important;
        inset: 0 !important;
        background: rgba(0, 0, 0, 0.75) !important;
        backdrop-filter: blur(6px) !important;
        z-index: 999999 !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 16px !important;
        box-sizing: border-box !important;
    }
    #productModal.active {
        display: flex !important;
    }
    #cartOverlay {
        display: none !important;
        position: fixed !important;
        inset: 0 !important;
        background: rgba(0, 0, 0, 0.6) !important;
        backdrop-filter: blur(4px) !important;
        z-index: 999998 !important;
    }
    #cartOverlay.active {
        display: block !important;
    }
    #cartDrawer {
        position: fixed !important;
        top: 0 !important;
        right: 0 !important;
        height: 100% !important;
        width: 100% !important;
        max-width: 420px !important;
        background: #111218 !important;
        color: #f4f4f5 !important;
        border-left: 1px solid #27272a !important;
        box-shadow: -10px 0 30px rgba(0,0,0,0.6) !important;
        z-index: 999999 !important;
        transform: translateX(100%) !important;
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: space-between !important;
        padding: 24px !important;
        box-sizing: border-box !important;
    }
    #cartDrawer.open {
        transform: translateX(0%) !important;
    }
</style>

<script>
    window.KIOSK_PRODUCTS = {
        {% for p in (regular_products or []) + (flash_sales or []) %}
        "{{ p.id }}": {
            "id": {{ p.id }},
            "name": {{ p.name|tojson }},
            "price": {{ (p.current_price if p.current_price is defined else (p.original_price if p.original_price is defined else 0)) }},
            "image": {{ (p.image or "")|tojson }},
            "description": {{ (p.description or "")|tojson }},
            "attributes": {{ (p.get_attributes() if p.get_attributes is defined and callable(p.get_attributes) else {})|tojson }}
        },
        {% endfor %}
    };
</script>

<!-- Product Specs & Options Modal -->
<div id="productModal">
    <div class="bg-[#14161f] border border-stone-800 p-6 md:p-8 max-w-sm w-full rounded-3xl shadow-2xl relative text-white">
        <button type="button" onclick="closeProductModal()" class="absolute top-4 right-4 text-stone-400 hover:text-white font-bold text-xl cursor-pointer">&times;</button>
        <span class="text-[10px] font-mono text-amber-400 uppercase tracking-widest block mb-1">Select Specifications</span>
        <h3 id="modalProductName" class="font-bold text-lg text-white mb-2 uppercase"></h3>
        <p id="modalProductDesc" class="text-xs text-stone-400 mb-4 leading-relaxed"></p>
        <p id="modalProductPrice" class="font-mono text-2xl font-black text-amber-400 mb-6"></p>

        <div id="modalVariantsContainer" class="space-y-4 mb-6"></div>

        <button type="button" onclick="confirmAddToCart()" 
                class="w-full bg-amber-400 hover:bg-amber-300 text-black font-black py-4 rounded-xl text-xs uppercase tracking-wider transition cursor-pointer shadow-lg">
            ADD TO BAG &rarr;
        </button>
    </div>
</div>

<!-- Slide-Out Shopping Bag Drawer -->
<div id="cartOverlay" onclick="toggleCart()"></div>
<aside id="cartDrawer">
    <div>
        <div class="flex justify-between items-center pb-4 border-b border-stone-800 mb-6">
            <div>
                <h3 class="font-bold text-base uppercase tracking-wider text-white m-0">Your Shopping Bag</h3>
                <span class="text-[10px] text-stone-400 font-mono">Direct WhatsApp Intake</span>
            </div>
            <button type="button" onclick="toggleCart()" class="text-xs font-mono font-bold text-stone-400 hover:text-white cursor-pointer">&times; CLOSE</button>
        </div>
        <div id="cartItemsList" class="space-y-3 max-h-[40vh] overflow-y-auto pr-1"></div>
    </div>

    <div class="pt-6 border-t border-stone-800">
        <div class="flex justify-between items-center mb-6 font-mono">
            <span class="text-xs uppercase text-stone-400">Total:</span>
            <span id="cartTotalPrice" class="font-black text-2xl text-amber-400">{{ (store.currency if store is defined and store.currency else '₦') }}0.00</span>
        </div>

        <form id="checkoutForm" onsubmit="handleCheckout(event)" class="space-y-3">
            <input type="text" id="custName" required placeholder="Your Full Name" 
                   class="w-full p-3 bg-[#181a24] border border-stone-800 rounded-xl text-xs text-white outline-none focus:border-amber-400">
            <input type="text" id="custPhone" required placeholder="WhatsApp Number (e.g. 08012345678)" 
                   class="w-full p-3 bg-[#181a24] border border-stone-800 rounded-xl text-xs text-white outline-none focus:border-amber-400">
            <textarea id="custAddress" required placeholder="Delivery Address / City / Notes" rows="2" 
                      class="w-full p-3 bg-[#181a24] border border-stone-800 rounded-xl text-xs text-white outline-none focus:border-amber-400"></textarea>

            <button type="submit" id="checkoutBtn" 
                    class="w-full bg-[#16a34a] hover:bg-[#15803d] text-white font-black py-4 rounded-xl text-xs uppercase tracking-wider transition cursor-pointer shadow-lg">
                COMPLETE ORDER ON WHATSAPP &rarr;
            </button>
        </form>
    </div>
</aside>

<script>
    const storeSlug = {{ (store.slug if store is defined else '')|tojson }};
    const storeCurrency = {{ (store.currency if store is defined and store.currency else '₦')|tojson }};
    let cart = [];
    let currentModalProduct = null;

    function toggleCart() {
        const drawer = document.getElementById('cartDrawer');
        const overlay = document.getElementById('cartOverlay');
        if (drawer) drawer.classList.toggle('open');
        if (overlay) overlay.classList.toggle('active');
    }

    function filterProducts(query) {
        const q = (query || '').toLowerCase().trim();
        const cards = document.querySelectorAll('.product-card');
        cards.forEach(card => {
            const name = card.getAttribute('data-name') || card.innerText || '';
            if (name.toLowerCase().includes(q)) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    }

    function openProductModal(productId) {
        const product = window.KIOSK_PRODUCTS[productId];
        if (!product) return;

        currentModalProduct = product;
        document.getElementById('modalProductName').innerText = product.name;
        document.getElementById('modalProductDesc').innerText = product.description || '';
        document.getElementById('modalProductPrice').innerText = `${storeCurrency}${Number(product.price).toLocaleString()}`;

        const container = document.getElementById('modalVariantsContainer');
        container.innerHTML = '';

        const attrs = product.attributes || {};
        const attrKeys = Object.keys(attrs);

        if (attrKeys.length > 0) {
            for (const [attr, opts] of Object.entries(attrs)) {
                if (!Array.isArray(opts) || opts.length === 0) continue;
                const group = document.createElement('div');
                group.innerHTML = `
                    <label class='block font-mono text-[10px] uppercase text-amber-400 mb-1 font-bold'>${attr}</label>
                    <select class='variant-select w-full p-2.5 bg-[#181a24] border border-stone-800 text-white font-mono text-xs rounded-xl outline-none focus:border-amber-400' data-attr='${attr}'>
                        ${opts.map(o => `<option value="${o}">${o}</option>`).join('')}
                    </select>
                `;
                container.appendChild(group);
            }
        }

        const modal = document.getElementById('productModal');
        if (modal) modal.classList.add('active');
    }

    function closeProductModal() {
        const modal = document.getElementById('productModal');
        if (modal) modal.classList.remove('active');
        currentModalProduct = null;
    }

    function confirmAddToCart() {
        if (!currentModalProduct) return;

        const selected = [];
        document.querySelectorAll('.variant-select').forEach(s => {
            selected.push(`${s.getAttribute('data-attr')}: ${s.value}`);
        });

        cart.push({
            product_id: currentModalProduct.id,
            name: currentModalProduct.name,
            price: currentModalProduct.price,
            variants: selected.join(' | '),
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

        if (badge) badge.innerText = cart.length;
        if (!list) return;

        list.innerHTML = '';
        let total = 0;

        cart.forEach((item, idx) => {
            total += item.price * item.quantity;
            const d = document.createElement('div');
            d.className = 'flex justify-between items-start p-3 bg-[#181a24] border border-stone-800 rounded-xl text-xs font-mono';
            d.innerHTML = `
                <div>
                    <strong class="text-white block font-bold">${item.name}</strong>
                    ${item.variants ? `<span class="text-[10px] text-amber-400 block">${item.variants}</span>` : ''}
                    <span class="text-emerald-400 font-bold mt-1 block">${storeCurrency}${Number(item.price).toLocaleString()}</span>
                </div>
                <button type="button" onclick="cart.splice(${idx}, 1); updateCartUI();" class="text-rose-400 hover:text-rose-300 font-bold ml-3 text-base cursor-pointer">&times;</button>
            `;
            list.appendChild(d);
        });

        if (totalEl) totalEl.innerText = `${storeCurrency}${total.toLocaleString()}`;
    }

    async function handleCheckout(e) {
        e.preventDefault();
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
"""


def clean_html_fences(raw_text: str) -> str:
    raw_text = re.sub(r'^```html\s*', '', raw_text.strip(), flags=re.IGNORECASE)
    raw_text = re.sub(r'^```\s*', '', raw_text.strip())
    raw_text = re.sub(r'```$', '', raw_text.strip())
    return raw_text.strip()


def inject_bulletproof_chassis(html_content: str, kiosk_name: str = '', bio: str = '', meta_img: str = '') -> str:
    """
    1. Guarantees Open Graph, Twitter cards, and SEO meta tags in <head>.
    2. Guarantees Tailwind CSS CDN in <head>.
    3. Strips broken/empty <img> tags so broken icon boxes never display.
    4. Strips duplicated/broken AI-written modals.
    5. Injects the guaranteed pure-CSS-hidden cart & modal engine.
    """
    safe_title = kiosk_name.strip() if kiosk_name else "{{ store.name }}"
    safe_desc = bio.strip().replace('"', '&quot;') if bio else "{{ store.bio or 'Explore our catalog on Marketplace' }}"
    safe_img = meta_img.strip() if meta_img else "{{ store.logo or store.hero_image or '' }}"

    meta_tags = (
        '    <meta charset="UTF-8">\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f'    <title>{safe_title}</title>\n'
        f'    <meta name="description" content="{safe_desc}">\n'
        '    <meta property="og:type" content="website">\n'
        '    <meta property="og:site_name" content="Marketplace">\n'
        f'    <meta property="og:title" content="{safe_title}">\n'
        f'    <meta property="og:description" content="{safe_desc}">\n'
        f'    <meta property="og:image" content="{safe_img}">\n'
        '    <meta name="twitter:card" content="summary_large_image">\n'
        f'    <meta name="twitter:title" content="{safe_title}">\n'
        f'    <meta name="twitter:description" content="{safe_desc}">\n'
        f'    <meta name="twitter:image" content="{safe_img}">'
    )

    # 1. Guarantee Meta Tags and Tailwind CDN in <head>
    if re.search(r'<head[^>]*>', html_content, re.IGNORECASE):
        html_content = re.sub(r'<title>.*?</title>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
        html_content = re.sub(r'<meta\s+property=["\']og:[^>]+>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+name=["\']twitter:[^>]+>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+name=["\']description["\'][^>]+>', '', html_content, flags=re.IGNORECASE)
        
        injection = f"<head>\n{meta_tags}"
        if 'cdn.tailwindcss.com' not in html_content:
            injection += '\n    <script src="https://cdn.tailwindcss.com"></script>'
        html_content = re.sub(r'<head[^>]*>', injection, html_content, count=1, flags=re.IGNORECASE)

    # 2. Strip any broken/empty image tags
    html_content = re.sub(r'<img[^>]+src=["\']\s*["\'][^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<img[^>]+src=["\'](None|null|undefined)["\'][^>]*>', '', html_content, flags=re.IGNORECASE)

    # 3. Strip any broken modals the AI tried to write
    html_content = re.sub(r'<div id="productModal".*?</div>\s*</div>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<aside id="cartDrawer".*?</aside>', '', html_content, flags=re.DOTALL | re.IGNORECASE)

    # 4. Inject guaranteed interactive cart engine
    if re.search(r'</body>', html_content, re.IGNORECASE):
        return re.sub(r'</body>', GUARANTEED_CART_ENGINE + '\n</body>', html_content, count=1, flags=re.IGNORECASE)
    return html_content + '\n' + GUARANTEED_CART_ENGINE


def query_openrouter(prompt_instruction: str, api_key: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": "Bearer " + api_key.strip(),
        "Content-Type": "application/json",
        "HTTP-Referer": "https://marketplace-beryl-delta.vercel.app",
        "X-Title": "Marketplace Kiosk Engine"
    }

    model_name = os.environ.get('OPENROUTER_MODEL') or 'google/gemini-2.0-flash-001'

    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt_instruction}
        ]
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data['choices'][0]['message']['content']
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode('utf-8')
        print("OpenRouter HTTP Error: " + str(e.code) + " - " + error_msg)
        return None
    except Exception as e:
        print("OpenRouter Connection Error: " + str(e))
        return None


def generate_kiosk_template(kiosk_name: str, bio: str, prompt: str, logo_url: str = '', hero_url: str = '', bg_url: str = '', currency: str = '₦') -> str:
    """
    MASTER DESIGN AGENCY PROMPT:
    Strictly aligns with Product(image, current_price, name, description)
    and Store(logo, hero_image, bio, name) models.
    """
    # Priority for meta previews: Brand Logo -> Hero Banner -> Background
    primary_meta_img = logo_url or hero_url or bg_url or ''

    system_instruction = (
        f'You are an elite creative director designing a bespoke storefront website for "{kiosk_name}".\n'
        'You NEVER build generic, plain, or cookie-cutter templates.\n\n'
        'CLIENT BRIEF & ASSETS:\n'
        f'- Brand Name: "{kiosk_name}"\n'
        f'- Design Instructions: "{prompt}"\n'
        f'- Brand Bio / Slogan: "{bio}"\n'
        f'- Brand Assets: Logo="{logo_url}", Hero="{hero_url}", Background="{bg_url}", Currency="{currency}"\n\n'
        'CRITICAL RULES & DATA SCHEMA:\n'
        '1. IN <head>:\n'
        '   - Include Google Fonts matching the niche and <script src="https://cdn.tailwindcss.com"></script>.\n'
        '2. HERO SECTION:\n'
        '   - Pre-headline pill badge MUST MATCH THE NICHE (e.g. Perfume: "✨ ARTISANAL EXTRAIT // RARE SCENTS", Food: "🔥 FRESH FLAME GRILLED", Tech: "⚡ VERIFIED GEAR").\n'
        '   - Ensure high contrast: If a hero image is rendered, wrap text in a dark glassmorphic card (e.g. bg-stone-900/85 backdrop-blur-md) so text is ALWAYS easily readable!\n'
        '   - Only render hero <img> if Hero asset is non-empty.\n'
        '3. HEADER & SEARCH:\n'
        '   - Top bar: Brand logo ("' + logo_url + '") and Name, an optional search input calling oninput="filterProducts(this.value)", and a BAG button with onclick="toggleCart()" containing <span id="cartCountBadge">0</span>.\n'
        '4. PRODUCTS LOOP (DATABASE MODEL ALIGNED):\n'
        '   Iterate products using:\n'
        '   {% for p in regular_products %}\n'
        '   <div class="product-card" data-name="{{ p.name }}">\n'
        '       <!-- Product Image: ALWAYS USE p.image -->\n'
        '       <img src="{{ p.image }}" alt="{{ p.name }}" onerror="this.onerror=null; this.parentElement.innerHTML=\'<div class=\\\'p-8 text-center text-xs font-mono text-stone-500\\\'>NO PREVIEW</div>\';">\n'
        '       <h3>{{ p.name }}</h3>\n'
        '       <p>{{ p.description }}</p>\n'
        '       <span>{{ store.currency }}{{ "{:,.0f}".format(p.current_price) }}</span>\n'
        '       <!-- Order / Add button: MUST call openProductModal(p.id) -->\n'
        '       <button onclick="openProductModal({{ p.id }})">ORDER NOW</button>\n'
        '   </div>\n'
        '   {% endfor %}\n'
        '5. DO NOT write your own checkout drawer or modal. The engine is automatically injected.\n'
        'Output ONLY pure valid HTML. No markdown backticks.'
    )

    # 1. Primary: Google Gemini
    gemini_key = (os.environ.get('AI_API_KEY') or '').strip()
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(system_instruction)
            
            raw_text = ""
            if response and hasattr(response, 'text'):
                try:
                    raw_text = response.text
                except Exception:
                    pass
            
            raw_html = clean_html_fences(raw_text)
            if raw_html:
                print("Generated bespoke showcase via Primary: Gemini!")
                return inject_bulletproof_chassis(raw_html, kiosk_name, bio, primary_meta_img)
        except Exception as e:
            print("Gemini API notice: " + str(e))

    # 2. Fast Backup: OpenRouter
    openrouter_key = (os.environ.get('OPENROUTER_API_KEY') or '').strip()
    if openrouter_key:
        raw_response = query_openrouter(system_instruction, openrouter_key)
        if raw_response:
            raw_html = clean_html_fences(raw_response)
            if raw_html:
                print("Generated bespoke showcase via Backup: OpenRouter!")
                return inject_bulletproof_chassis(raw_html, kiosk_name, bio, primary_meta_img)

    # 3. Clean Native Fallback
    print("AI generation skipped or unavailable. Falling back to default catalog.html template.")
    return ""
