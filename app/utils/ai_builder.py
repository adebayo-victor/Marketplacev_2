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
    #productModal.active { display: flex !important; }
    #cartOverlay {
        display: none !important;
        position: fixed !important;
        inset: 0 !important;
        background: rgba(0, 0, 0, 0.6) !important;
        backdrop-filter: blur(4px) !important;
        z-index: 999998 !important;
    }
    #cartOverlay.active { display: block !important; }
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
    #cartDrawer.open { transform: translateX(0%) !important; }
</style>

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
            <span id="cartTotalPrice" class="font-black text-2xl text-amber-400">{{ store.currency }}0.00</span>
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
    const storeSlug = {{ store.slug|tojson }};
    const storeCurrency = {{ store.currency|tojson }};
    let cart = [];
    let currentModalProduct = null;

    function toggleCart() {
        const drawer = document.getElementById('cartDrawer');
        const overlay = document.getElementById('cartOverlay');
        if (drawer) drawer.classList.toggle('open');
        if (overlay) overlay.classList.toggle('active');
    }
    function openProductModal(productId) {
        const product = window.KIOSK_PRODUCTS[productId];
        if (!product) return;
        currentModalProduct = product;
        document.getElementById('modalProductName').innerText = product.name;
        document.getElementById('modalProductDesc').innerText = product.description || '';
        document.getElementById('modalProductPrice').innerText = `${storeCurrency}${product.price.toLocaleString()}`;
        const container = document.getElementById('modalVariantsContainer');
        container.innerHTML = '';
        const attrs = product.attributes || {};
        for (const [attr, opts] of Object.entries(attrs)) {
            const group = document.createElement('div');
            group.innerHTML = `
                <label class='block font-mono text-[10px] uppercase text-amber-400 mb-1 font-bold'>${attr}</label>
                <select class='variant-select w-full p-2.5 bg-[#181a24] border border-stone-800 text-white font-mono text-xs rounded-xl outline-none focus:border-amber-400' data-attr='${attr}'>
                    ${opts.map(o => `<option value="${o}">${o}</option>`).join('')}
                </select>
            `;
            container.appendChild(group);
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
                    <span class="text-emerald-400 font-bold mt-1 block">${storeCurrency}${item.price.toLocaleString()}</span>
                </div>
                <button type="button" onclick="cart.splice(${idx}, 1); updateCartUI();" class="text-rose-400 hover:text-rose-300 font-bold ml-3 text-base cursor-pointer">&times;</button>
            `;
            list.appendChild(d);
        });
        if (totalEl) totalEl.innerText = `${storeCurrency}${total.toLocaleString()}`;
    }
    async function handleCheckout(e) {
        e.preventDefault();
        if (cart.length === 0) { alert('Your bag is empty.'); return; }
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
            alert('Connection error.');
            btn.innerText = 'COMPLETE ORDER ON WHATSAPP →';
            btn.disabled = false;
        }
    }
</script>
"""


def clean_html_fences(raw_text: str) -> str:
    raw_text = re.sub(r'^```html\s*', '', raw_text.strip(), flags=re.IGNORECASE)
    raw_text = re.sub(r'```$', '', raw_text.strip())
    return raw_text


def inject_bulletproof_chassis(html_content: str, kiosk_name: str = '', bio: str = '', meta_img: str = '') -> str:
    safe_title = kiosk_name.strip() if kiosk_name else "{{ store.name }}"
    safe_desc = bio.strip().replace('"', '&quot;') if bio else "{{ store.tagline or 'Explore our catalog on Marketplace' }}"
    safe_img = meta_img.strip() if meta_img else "{{ store.image_url or '' }}"

    meta_tags = f"""
    <title>{safe_title}</title>
    <meta name="description" content="{safe_desc}">
    <meta property="og:type" content="website">
    <meta property="og:title" content="{safe_title}">
    <meta property="og:description" content="{safe_desc}">
    <meta property="og:image" content="{safe_img}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{safe_title}">
    <meta name="twitter:description" content="{safe_desc}">
    <meta name="twitter:image" content="{safe_img}">
    """

    if '<head>' in html_content:
        html_content = re.sub(r'<meta\s+property=["\']og:[^>]+>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+name=["\']twitter:[^>]+>', '', html_content, flags=re.IGNORECASE)
        injection = f"<head>\n{meta_tags}"
        if 'cdn.tailwindcss.com' not in html_content:
            injection += '\n<script src="https://cdn.tailwindcss.com"></script>'
        html_content = html_content.replace('<head>', injection, 1)

    html_content = re.sub(r'<img[^>]+src=["\']\s*["\'][^>]*>', '', html_content)
    html_content = re.sub(r'<img[^>]+src=["\']None["\'][^>]*>', '', html_content)
    html_content = re.sub(r'<div id="productModal".*?</div>\s*</div>', '', html_content, flags=re.DOTALL)
    html_content = re.sub(r'<aside id="cartDrawer".*?</aside>', '', html_content, flags=re.DOTALL)

    if '</body>' in html_content:
        return html_content.replace('</body>', GUARANTEED_CART_ENGINE + '\n</body>', 1)
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
        "messages": [{"role": "user", "content": prompt_instruction}]
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data['choices'][0]['message']['content']
    except urllib.error.HTTPError as e:
        print("OpenRouter HTTP Error: " + str(e.code))
        return None
    except Exception as e:
        print("OpenRouter Connection Error: " + str(e))
        return None


def generate_kiosk_template(kiosk_name: str, bio: str, prompt: str, logo_url: str = '', hero_url: str = '', bg_url: str = '', currency: str = '₦') -> str:
    """
    FULL DATA-MODEL-AWARE PROMPT:
    AI now knows every field in Store, Product, Order, StoreAd so it can render
    flash sale badges, discount prices, stock indicators, variants, ads, etc.
    """
    primary_meta_img = hero_url or logo_url or bg_url or ''

    system_instruction = (
        "ROLE & PERSONA:\n"
        "You are 'Aura-Dev,' an elite Creative Director and Senior Full-Stack Engineer specializing in luxury e-commerce experiences. Your mandate is to create breathtaking, trustworthy websites that showcase REAL PRODUCTS using REAL DATA.\n\n"
        
        "CRITICAL RULES - NO FAKE CONTENT:\n"
        "1. NEVER invent fake statistics, achievements, or credentials.\n"
        "2. NEVER use external image URLs (Unsplash, Pexels, placeholder.com, etc.). Only use provided brand assets.\n"
        "3. NEVER create fake product cards. Only showcase real products via the Jinja loops.\n"
        "4. NEVER generate broken <img> tags. If no image is provided, use CSS-only alternatives.\n\n"
        
        "═══════════════════════════════════════════════\n"
        "📦 COMPLETE DATA MODEL REFERENCE (USE THESE FIELDS)\n"
        "═══════════════════════════════════════════════\n\n"
        
        "--- STORE OBJECT (available as `store`) ---\n"
        "• store.name — Brand name\n"
        "• store.slug — URL slug\n"
        "• store.bio — Tagline / description\n"
        "• store.logo — Logo filename (use: url_for('static', filename='uploads/logos/' + store.logo))\n"
        "• store.hero_image — Hero banner filename\n"
        "• store.background_image — Background wallpaper filename\n"
        "• store.whatsapp_number — Contact number for orders\n"
        "• store.currency — Currency symbol (e.g. '₦', '$')\n"
        "• store.views_count — Total visits (integer)\n"
        "• store.show_public_stats — Boolean, whether to display visit count\n"
        "• store.receipt_theme — 'classic' or 'cyber'\n"
        "• store.is_active — Boolean, whether store is live\n"
        "• store.build_status — 'building' or 'ready'\n"
        "• store.is_section_active('hero') — Returns True/False\n"
        "• store.is_section_active('flash_sales') — Returns True/False\n"
        "• store.is_section_active('ads') — Returns True/False\n\n"
        
        "--- PRODUCT OBJECT (available as `p` in loops) ---\n"
        "• p.id — Product ID (use in onclick='openProductModal({{ p.id }})')\n"
        "• p.name — Product name\n"
        "• p.description — Product description\n"
        "• p.image — Product image filename\n"
        "• p.original_price — Regular price (float)\n"
        "• p.discount_price — Sale price (float, may be None)\n"
        "• p.current_price — Property: returns discount_price if set, else original_price\n"
        "• p.has_discount — Property: True if discount_price < original_price\n"
        "• p.is_flash_sale — Boolean: True if pinned as flash deal \n"
        "• p.is_unlimited_stock — Boolean: True for made-to-order / food / digital\n"
        "• p.stock — Integer: units remaining (ignored if is_unlimited_stock)\n"
        "• p.is_available — Property: True if unlimited OR stock > 0\n"
        "• p.get_attributes() — Returns dict of variants, e.g. {'Size': ['S','M','L'], 'Color': ['Red','Black']}\n\n"
        
        "--- PRODUCT LOOPS (TWO SEPARATE LISTS) ---\n"
        "• `flash_sales` — List of products where p.is_flash_sale == True (render in a dedicated FLASH DEALS section with red/fire styling)\n"
        "• `regular_products` — List of all non-flash-sale products (render in main catalog)\n"
        "• Combined loop: {% for p in regular_products + flash_sales %} (used internally by cart engine)\n\n"
        
        "--- ADS OBJECT (available as `ad_slots` dict, keyed by slot_number 1, 2, 3) ---\n"
        "• ad_slots[1].banner_image — Header ad image\n"
        "• ad_slots[1].target_link — Click destination URL\n"
        "• ad_slots[1].clicks_count — Integer\n"
        "• ad_slots[3].banner_image — Footer ad image\n"
        "• Use: {% if store.is_section_active('ads') and 1 in ad_slots %} ... {% endif %}\n"
        "• Click tracking link: /ad/click/{{ ad_slots[1].id }}\n\n"
        
        "═══════════════════════════════════════════════\n"
        "🎨 HOW TO RENDER EACH PRODUCT FIELD\n"
        "═══════════════════════════════════════════════\n\n"
        
        "1. **FLASH SALE BADGE**: If `p.is_flash_sale` is True, render a red/fire badge:\n"
        "   {% if p.is_flash_sale %}<span class='bg-red-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full'>🔥 FLASH SALE</span>{% endif %}\n\n"
        
        "2. **DISCOUNT PRICING**: If `p.has_discount` is True, show strikethrough original + bold discount:\n"
        "   {% if p.has_discount %}\n"
        "     <span class='line-through text-stone-400 text-xs'>{{ store.currency }}{{ p.original_price }}</span>\n"
        "     <span class='font-bold text-red-600'>{{ store.currency }}{{ p.discount_price }}</span>\n"
        "   {% else %}\n"
        "     <span class='font-bold'>{{ store.currency }}{{ p.original_price }}</span>\n"
        "   {% endif %}\n\n"
        
        "3. **STOCK INDICATOR**: \n"
        "   {% if p.is_unlimited_stock %}\n"
        "     <span class='text-emerald-600 text-xs font-bold'>● Always in Stock / Made-to-Order</span>\n"
        "   {% elif p.stock > 0 %}\n"
        "     <span class='text-stone-400 text-xs'>{{ p.stock }} units left</span>\n"
        "   {% else %}\n"
        "     <span class='text-red-600 text-xs font-bold'>OUT OF STOCK</span>\n"
        "   {% endif %}\n\n"
        
        "4. **VARIANT SELECTOR**: When user clicks 'Add to Bag', the auto-injected modal reads `p.get_attributes()` and builds dropdowns automatically. Just ensure your button calls: onclick='openProductModal({{ p.id }})'\n\n"
        
        "5. **IMAGE RENDERING**: \n"
        "   <img src=\"{{ p.image if p.image.startswith('http') else url_for('static', filename='uploads/products/' + p.image) }}\" alt=\"{{ p.name }}\">\n"
        "   ONLY render <img> if p.image exists and is not 'default_product.png'. Otherwise use a CSS gradient placeholder with the product initials.\n\n"
        
        "═══════════════════════════════════════════════\n"
        "️ MANDATORY SECTIONS (IN THIS ORDER)\n"
        "═══════════════════════════════════════════════\n\n"
        
        "1. **STICKY NAVIGATION**: Logo (store.logo or text), menu (Home, About, Collections, Contact), CART button with <span id='cartCountBadge'>0</span> calling onclick='toggleCart()'\n\n"
        
        "2. **HERO SECTION** (only if store.is_section_active('hero')):\n"
        "   - Large serif headline (text-5xl md:text-7xl)\n"
        "   - Tagline from store.bio\n"
        "   - CTA button 'Shop Collection'\n"
        "   - Background: use store.hero_image if provided, else CSS gradient\n"
        "   - Ghost word: oversized brand name at opacity-5 in background\n"
        "   - Niche badge matching category (e.g. '✨ FRAGRANCE', '🔥 GOURMET', '⚡ TECH')\n\n"
        
        "3. **FLASH DEALS SECTION** (only if store.is_section_active('flash_sales') AND flash_sales list is not empty):\n"
        "   - Red/fire themed section header '🔥 Flash Deals'\n"
        "   - Loop: {% for p in flash_sales %}\n"
        "   - Each card: image, name, description, DISCOUNT PRICING (strikethrough + red sale price), FLASH SALE badge, 'Select & Order' button\n\n"
        
        "4. **AD SLOT #1** (only if store.is_section_active('ads') and 1 in ad_slots):\n"
        "   - Full-width banner with 'AD' corner badge\n"
        "   - <a href='/ad/click/{{ ad_slots[1].id }}' target='_blank'>\n"
        "   - <img src with ad banner image>\n\n"
        
        "5. **CATALOG HEADER** with search bar placeholder\n\n"
        
        "6. **REGULAR PRODUCTS GRID**:\n"
        "   - Loop: {% for p in regular_products %}\n"
        "   - Each card: image (or CSS placeholder), name, description, DISCOUNT PRICING if applicable, STOCK INDICATOR, 'View & Order' button calling onclick='openProductModal({{ p.id }})'\n"
        "   - If product not available, show disabled 'Out of Stock' button\n\n"
        
        "7. **AD SLOT #3** (footer banner, same pattern as slot #1)\n\n"
        
        "8. **WHY CHOOSE US** (CSS-only, 4 Lucide icons with real benefits — NO fake numbers)\n\n"
        
        "9. **ABOUT / BRAND STORY** (CSS-only, uses store.bio)\n\n"
        
        "10. **NEWSLETTER** (CSS-only email signup)\n\n"
        
        "11. **FOOTER**: Logo, menu links, social icons, copyright with store.name\n\n"
        
        "═══════════════════════════════════════════════\n"
        "🎨 DESIGN PHILOSOPHY\n"
        "═══════════════════════════════════════════════\n"
        "- Luxury aesthetic: charcoal (#0a0a0a), cream (#f5f0eb), gold accents (#d4af37)\n"
        "- Typography: Playfair Display (serif headlines) + Inter (body)\n"
        "- Generous whitespace (py-20, py-32)\n"
        "- Subtle shadows, thin borders, smooth hover transitions\n"
        "- Mobile-first responsive (sm:, md:, lg: breakpoints)\n"
        "- CSS-only decorative elements (gradients, patterns) — NO fake images\n\n"
        
        "═══════════════════════════════════════════════\n"
        "⚙️ TECHNICAL REQUIREMENTS\n"
        "═══════════════════════════════════════════════\n"
        "1. Tailwind CSS CDN: <script src='https://cdn.tailwindcss.com'></script>\n"
        "2. Google Fonts: Playfair Display + Inter\n"
        "3. Lucide Icons CDN: <script src='https://unpkg.com/lucide@latest'></script> + lucide.createIcons()\n"
        "4. Semantic HTML5, mobile-first, OpenGraph + Twitter meta tags, JSON-LD\n"
        "5. Output ONLY pure HTML. NO markdown code blocks.\n\n"
        
        "═══════════════════════════════════════════════\n"
        "🚫 NON-NEGOTIABLE KIOSK ENGINE RULES\n"
        "═══════════════════════════════════════════════\n"
        "1. CART button must call onclick='toggleCart()' with <span id='cartCountBadge'>0</span>\n"
        "2. Every product card button must call onclick='openProductModal({{ p.id }})'\n"
        "3. Only render <img> for hero if store.hero_image is provided and non-empty\n"
        "4. Embed oversized brand name with opacity-5 in hero background\n"
        "5. Niche badge MUST match category\n"
        "6. DO NOT write modal or cart drawer — auto-injected by backend\n"
        "7. Use {% if p.is_available %} to conditionally show order buttons\n\n"
        
        "FINAL INSTRUCTION:\n"
        "Create a complete, production-ready e-commerce website. Use EVERY field from the data model appropriately — flash sale badges, discount pricing, stock indicators, variant support, ad slots, section toggles. Focus on showcasing REAL PRODUCTS with honest, premium design. Make it stunning, functional, and conversion-focused."
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
                print("Generated data-aware showcase via Primary: Gemini!")
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
                print("Generated data-aware showcase via Backup: OpenRouter!")
                return inject_bulletproof_chassis(raw_html, kiosk_name, bio, primary_meta_img)

    # 3. Clean Native Fallback
    print("AI generation skipped or unavailable. Falling back to default catalog.html template.")
    return ""
