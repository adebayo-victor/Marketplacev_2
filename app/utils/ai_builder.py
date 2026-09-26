import os
import re
import json
import urllib.request
import urllib.error

# 🛡️ THE BULLETPROOF INTERACTIVE ENGINE (INJECTED INTO EVERY GENERATED KIOSK)
GUARANTEED_CART_ENGINE = """
<!-- ========================================== -->
<!-- BULLETPROOF SHOPPING BAG & CHECKOUT ENGINE -->
<!-- ========================================== -->
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
<div id="productModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-[99999] flex items-center justify-center p-4 hidden">
    <div class="bg-[#14161f] border border-blue-500/40 p-8 max-w-sm w-full rounded-3xl shadow-2xl relative text-white">
        <button type="button" onclick="closeProductModal()" class="absolute top-4 right-4 text-stone-400 hover:text-white font-bold text-xl cursor-pointer">&times;</button>
        <span class="text-[10px] font-mono text-amber-400 uppercase tracking-widest block mb-1">Select Options & Specs</span>
        <h3 id="modalProductName" class="font-black text-lg text-white mb-2 uppercase"></h3>
        <p id="modalProductDesc" class="text-xs text-stone-400 mb-4 leading-relaxed"></p>
        <p id="modalProductPrice" class="font-mono text-2xl font-black text-amber-400 mb-6"></p>

        <div id="modalVariantsContainer" class="space-y-4 mb-6"></div>

        <button type="button" onclick="confirmAddToCart()" 
                class="w-full bg-amber-400 hover:bg-amber-300 text-black font-black py-4 rounded-xl text-xs uppercase tracking-wider transition cursor-pointer shadow-lg shadow-amber-400/20">
            ADD TO BAG &rarr;
        </button>
    </div>
</div>

<!-- Slide-Out Shopping Bag Drawer -->
<div id="cartOverlay" onclick="toggleCart()" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[99998] hidden"></div>
<aside id="cartDrawer" class="fixed top-0 right-0 h-full w-full max-w-md bg-[#111218] border-l border-stone-800 z-[99999] p-6 flex flex-col justify-between translate-x-full transition-transform duration-300 text-white">
    <div>
        <div class="flex justify-between items-center pb-4 border-b border-stone-800 mb-6">
            <div>
                <h3 class="font-black text-base uppercase tracking-wider text-white m-0">Your Shopping Bag</h3>
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
                   class="w-full p-3 bg-[#181a24] border border-stone-800 rounded-xl text-xs text-white outline-none focus:border-blue-500">
            <input type="text" id="custPhone" required placeholder="WhatsApp Number (e.g. 08012345678)" 
                   class="w-full p-3 bg-[#181a24] border border-stone-800 rounded-xl text-xs text-white outline-none focus:border-blue-500">
            <textarea id="custAddress" required placeholder="Delivery Address / City / Notes" rows="2" 
                      class="w-full p-3 bg-[#181a24] border border-stone-800 rounded-xl text-xs text-white outline-none focus:border-blue-500"></textarea>

            <button type="submit" id="checkoutBtn" 
                    class="w-full bg-[#16a34a] hover:bg-[#15803d] text-white font-black py-4 rounded-xl text-xs uppercase tracking-wider transition cursor-pointer shadow-lg shadow-green-600/20">
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
        if (drawer) drawer.classList.toggle('translate-x-full');
        if (overlay) overlay.classList.toggle('hidden');
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

        document.getElementById('productModal').classList.remove('hidden');
    }

    function closeProductModal() {
        document.getElementById('productModal').classList.add('hidden');
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
                    <span class="text-blue-400 font-bold mt-1 block">${storeCurrency}${item.price.toLocaleString()}</span>
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
    raw_text = re.sub(r'^```html\s*', '', raw_text.strip())
    raw_text = re.sub(r'```$', '', raw_text.strip())
    return raw_text


def inject_bulletproof_chassis(html_content: str) -> str:
    """Strips AI-attempted broken modals and cleanly injects our tested cart engine."""
    html_content = re.sub(r'<div id="productModal".*?</div>\s*</div>', '', html_content, flags=re.DOTALL)
    html_content = re.sub(r'<aside id="cartDrawer".*?</aside>', '', html_content, flags=re.DOTALL)

    if '</body>' in html_content:
        return html_content.replace('</body>', GUARANTEED_CART_ENGINE + '\n</body>')
    return html_content + '\n' + GUARANTEED_CART_ENGINE


def query_openrouter(prompt_instruction: str, api_key: str) -> str:
    """Queries OpenRouter using high-speed models that respond in ~2-3 seconds."""
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
    MASTER DESIGN AGENCY PROMPT:
    Forces the AI to generate high-end, bespoke boutique storefronts
    with custom typography, ghost backdrops, layered depth, and micro-tags.
    """
    system_instruction = (
        'You are an award-winning creative art director and lead web architect. You design bespoke, $10,000 storefronts for high-end boutique brands.\n'
        'You NEVER build generic, pale, plain, or cookie-cutter templates. Every site you create looks like an editorial showcase from Awwwards or Dribbble.\n\n'
        'CLIENT BRIEF:\n'
        '- Brand Name: "' + kiosk_name + '"\n'
        '- Creative Design Request: "' + prompt + '"\n'
        '- Brand Bio: "' + bio + '"\n'
        '- Brand Assets: Logo="' + logo_url + '", Hero="' + hero_url + '", Background="' + bg_url + '", Currency="' + currency + '"\n\n'
        'EXECUTIVE DESIGN SPECIFICATIONS (FOLLOW EXACTLY):\n\n'
        '1. TYPOGRAPHY PAIRINGS:\n'
        '   - Import TWO contrasting Google Fonts in the <head>:\n'
        '     • Display/Headline Font: One of ["Syne", "Space Grotesk", "Clash Display", "Cinzel", "Outfit", "Playfair Display"].\n'
        '     • Body/UI Font: One of ["Space Grotesk", "Plus Jakarta Sans", "JetBrains Mono", "Inter"].\n\n'
        '2. COLOR HARMONY & DEPTH:\n'
        '   - Use rich layered surfaces with deep contrast (e.g. obsidian #09090b, deep charcoal #12131a, midnight navy, warm espresso, or vibrant boutique tones).\n'
        '   - Add glow shadows to buttons (e.g. shadow-lg shadow-amber-400/20 or shadow-cyan-500/20).\n'
        '   - Add subtle border glows on cards with hover states.\n'
        '   -A dark and light mode toggle button. \n\n
        '3. THE "GHOST WATERMARK" HERO SECTION:\n'
        '   - Build a dramatic hero container with rounded-3xl corners.\n'
        '   - Include a pre-headline badge pill (e.g. "⚡ LIMITED RUN // EXCLUSIVE APPAREL" or "⚡ AUDITED CODE // INSTANT INTAKE").\n'
        '   - Headline: Massive, bold, characterful typography (text-3xl md:text-5xl font-black uppercase tracking-tight).\n'
        '   - In the background of the hero container, embed an OVERSIZED semi-transparent ghost word from the brand name (e.g. class="absolute -right-8 -bottom-12 opacity-5 text-8xl md:text-9xl font-black uppercase select-none pointer-events-none") for depth.\n\n'
        '4. PRODUCT CATALOG CARDS:\n'
        '   - Iterate using: {% for p in regular_products %} ... {% endfor %}\n'
        '   - Image container: Clean aspect ratio with dark/contrast backdrop.\n'
        '   - Above product title: Include an editorial micro-tag (e.g. <span class="text-[10px] font-mono text-cyan-400 uppercase tracking-wider block mb-1">[VERIFIED // DROP]</span>).\n'
        '   - Title ({{ p.name }}), Description ({{ p.description }}), Stock units remaining.\n'
        '   - Price block: If p.has_discount, show strikethrough original and bold colored current price.\n'
        '   - Action Button: Prominent, high-contrast, uppercase button that calls: onclick="openProductModal({{ p.id }})"\n\n'
        '5. FLASH SALES SECTION:\n'
        '   - Include: {% if flash_sales %} ... with 🔥 FLASH DROP badge and urgent action buttons ... {% endif %}\n\n'
        '6. HEADER & FOOTER:\n'
        '   - Sticky glassmorphism header with logo/avatar, brand title with VERIFIED badge, and a BAG button with onclick="toggleCart()" containing <span id="cartCountBadge">0</span>.\n'
        '   - Footer with "Powered by Marketplace • ' + kiosk_name + '".\n\n'
        'IMPORTANT: Do NOT write the modal or cart drawer HTML yourself. It is automatically injected. Just deliver the complete, stunning visual page from <!DOCTYPE html> to </html>!\n'
        'Output ONLY pure HTML. No markdown code blocks.'
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
                print("Generated bespoke showcase via Primary: Gemini!")
                return inject_bulletproof_chassis(raw_html)
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
                return inject_bulletproof_chassis(raw_html)

    # 3. Clean Native Fallback
    print("AI generation skipped or unavailable. Falling back to default catalog.html template.")
    return ""
