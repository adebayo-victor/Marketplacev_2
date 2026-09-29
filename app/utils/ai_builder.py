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
    raw_text = re.sub(r'```$', '', raw_text.strip())
    return raw_text


def inject_bulletproof_chassis(html_content: str, kiosk_name: str = '', bio: str = '', meta_img: str = '') -> str:
    """
    1. Guarantees Open Graph, Twitter cards, and SEO meta tags in <head>.
    2. Guarantees Tailwind CSS CDN in <head>.
    3. Strips broken/empty <img> tags so broken icon boxes never display.
    4. Strips duplicated/broken AI-written modals.
    5. Injects the guaranteed pure-CSS-hidden cart & modal engine.
    """
    # Build dynamic Open Graph / Meta tags
    safe_title = kiosk_name.strip() if kiosk_name else "{{ store.name }}"
    safe_desc = bio.strip().replace('"', '&quot;') if bio else "{{ store.tagline or 'Explore our catalog on Marketplace' }}"
    safe_img = meta_img.strip() if meta_img else "{{ store.image_url or '' }}"

    meta_tags = f"""
    <!-- Dynamic Social & SEO Meta Tags -->
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

    # 1. Guarantee Meta Tags and Tailwind CDN in <head>
    if '<head>' in html_content:
        # Strip existing meta og tags if AI duplicated them
        html_content = re.sub(r'<meta\s+property=["\']og:[^>]+>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<meta\s+name=["\']twitter:[^>]+>', '', html_content, flags=re.IGNORECASE)
        
        injection = f"<head>\n{meta_tags}"
        if 'cdn.tailwindcss.com' not in html_content:
            injection += '\n<script src="https://cdn.tailwindcss.com"></script>'
        html_content = html_content.replace('<head>', injection, 1)

    # 2. Strip any broken/empty image tags where src is empty or missing
    html_content = re.sub(r'<img[^>]+src=["\']\s*["\'][^>]*>', '', html_content)
    html_content = re.sub(r'<img[^>]+src=["\']None["\'][^>]*>', '', html_content)

    # 3. Strip any broken modals the AI tried to write
    html_content = re.sub(r'<div id="productModal".*?</div>\s*</div>', '', html_content, flags=re.DOTALL)
    html_content = re.sub(r'<aside id="cartDrawer".*?</aside>', '', html_content, flags=re.DOTALL)

    # 4. Inject guaranteed interactive cart engine
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
        print("OpenRouter HTTP Error: " + str(e.code) + " - " + error_msg)
        return None
    except Exception as e:
        print("OpenRouter Connection Error: " + str(e))
        return None


def generate_kiosk_template(kiosk_name: str, bio: str, prompt: str, logo_url: str = '', hero_url: str = '', bg_url: str = '', currency: str = '₦') -> str:
    """
    ENHANCED LUXURY DESIGN PROMPT:
    Creates stunning, high-end websites with premium aesthetics even with minimal input.
    """
    # Pick the best available image for metadata card previews
    primary_meta_img = hero_url or logo_url or bg_url or ''

    #  ENHANCED AURA-DEV PERSONA WITH LUXURY DESIGN MANDATE
    system_instruction = (
        "ROLE & PERSONA:\n"
        "You are 'Aura-Dev,' an elite Creative Director and Senior Full-Stack Engineer specializing in luxury brand experiences. Your mandate is to create breathtaking, award-winning websites that rival Awwwards sites. Every design must exude sophistication, premium quality, and meticulous attention to detail.\n\n"
        
        "DESIGN PHILOSOPHY (APPLY EVEN WITH MINIMAL INPUT):\n"
        "1. **Luxury Aesthetic Default**: Always default to high-end, sophisticated designs regardless of category. Use:\n"
        "   - Color Palettes: Deep charcoal (#0a0a0a, #1a1a1a), warm cream (#f5f0eb, #faf8f5), gold/amber accents (#d4af37, #c9a961), rich browns\n"
        "   - Typography: Elegant serif fonts (Playfair Display, Cormorant Garamond) for headlines + clean sans-serif (Inter, Montserrat) for body\n"
        "   - Spacing: Generous whitespace (py-20, py-32), breathing room between sections\n"
        "   - Shadows: Subtle, refined shadows (shadow-2xl with low opacity)\n"
        "   - Borders: Ultra-thin borders (border border-white/10)\n"
        "   - Gradients: Subtle linear gradients for depth\n\n"
        
        "2. **MANDATORY SECTIONS** (Build all of these):\n"
        "   - **Sticky Navigation**: Logo left, menu center (Home, About, Collections/Products, Journal, Contact), icons right (search, account, cart with badge)\n"
        "   - **Hero Section**: Full-screen or near full-screen. Large serif typography (text-5xl md:text-7xl). Subtle tagline. Primary CTA button + secondary 'Watch Tour' button with play icon. Navigation dots or arrows. Background image with dark overlay if provided.\n"
        "   - **Category Grid**: 4-column grid (Living Room, Dining Room, Bedroom, Outdoor or relevant categories). Each card: image + overlay + title. Hover effects.\n"
        "   - **Featured Collection**: Large section with headline, description, image on one side, content on other. CTA button.\n"
        "   - **Services/Features**: 4-icon grid showing key benefits (Premium Quality, Custom Made, Worldwide Delivery, Timeless Design). Icons + title + short description.\n"
        "   - **Stats Section**: Numbers that build credibility (200+ Projects, 15+ Years, 98% Satisfaction). Large numbers with icons.\n"
        "   - **Testimonial**: Quote section with customer photo, name, title. Elegant quotation marks.\n"
        "   - **Newsletter**: Email signup section with heading 'Be The First To Know'. Input field + subscribe button.\n"
        "   - **Footer**: Multi-column layout. Logo, description, menu links, social icons, copyright.\n\n"
        
        "3. **INTERACTION DETAILS**:\n"
        "   - Smooth hover transitions (transition-all duration-300)\n"
        "   - Button styles: Outlined with hover fill, or solid with subtle lift\n"
        "   - Image hover: Slight scale (hover:scale-105) with overflow-hidden\n"
        "   - Scroll animations: Fade-in effects (use opacity and transform)\n\n"
        
        "CLIENT BRIEF:\n"
        f"- Brand Name: '{kiosk_name}'\n"
        f"- Design Instructions & Category: '{prompt}'\n"
        f"- Brand Bio / Tagline: '{bio}'\n"
        f"- Brand Assets: Logo='{logo_url}', Hero='{hero_url}', Background='{bg_url}', MetaImage='{primary_meta_img}', Currency='{currency}'\n\n"
        
        "TECHNICAL REQUIREMENTS:\n"
        "1. Use Tailwind CSS via CDN (<script src='https://cdn.tailwindcss.com'></script>)\n"
        "2. Google Fonts: Import Playfair Display (serif) + Inter or Montserrat (sans-serif)\n"
        "3. Lucide Icons via CDN for all icons\n"
        "4. Semantic HTML5 structure\n"
        "5. Mobile-first responsive design (use sm:, md:, lg: breakpoints)\n"
        "6. Full OpenGraph & Twitter meta tags in <head>\n"
        "7. JSON-LD structured data for SEO\n\n"
        
        "CRITICAL KIOSK ENGINE RULES (NON-NEGOTIABLE):\n"
        "1. HEADER: Include prominent BAG button calling onclick='toggleCart()' with <span id='cartCountBadge'>0</span>\n"
        "2. PRODUCTS LOOP: Use {% for p in regular_products %}...{% endfor %}. Each product card MUST have button calling onclick='openProductModal({{ p.id }})'\n"
        "3. HERO IMAGE: Only render <img> if hero_url is provided. If empty, DO NOT render empty tag!\n"
        "4. BACKGROUND GHOST WORD: Embed oversized brand name with opacity-5 in hero background\n"
        "5. NICHE BADGE: Pre-headline badge MUST match category (e.g., ' FLAME GRILLED' for food, '✨ ARTISANAL' for luxury, ' TECH' for electronics)\n"
        "6. DO NOT write modal or cart drawer - they are auto-injected by backend\n"
        "7. Output ONLY pure HTML. NO markdown code blocks.\n\n"
        
        "FINAL INSTRUCTION:\n"
        "Create a complete, production-ready website that looks like it cost $50,000. Every pixel must be intentional. Even if the client gives minimal info, default to luxury furniture brand aesthetics (like the Aurora/Solstice examples) unless explicitly told otherwise. Make it stunning."
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
                print("Generated luxury showcase via Primary: Gemini!")
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
                print("Generated luxury showcase via Backup: OpenRouter!")
                return inject_bulletproof_chassis(raw_html, kiosk_name, bio, primary_meta_img)

    # 3. Clean Native Fallback
    print("AI generation skipped or unavailable. Falling back to default catalog.html template.")
    return ""
