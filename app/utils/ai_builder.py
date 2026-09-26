import os
import re
import json
import urllib.request
import urllib.error

# 🛡️ THE BULLETPROOF INTERACTIVE ENGINE (INJECTED INTO AI-GENERATED PAGES)
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
<div id="productModal" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[99999] flex items-center justify-center p-4 hidden">
    <div class="bg-white p-6 max-w-sm w-full rounded-2xl shadow-2xl relative text-stone-900">
        <button type="button" onclick="closeProductModal()" class="absolute top-3 right-3 text-stone-400 hover:text-black font-bold text-xl cursor-pointer">&times;</button>
        <h3 id="modalProductName" class="font-bold text-base mb-1 text-stone-900"></h3>
        <p id="modalProductDesc" class="text-xs text-stone-500 mb-3 leading-relaxed"></p>
        <p id="modalProductPrice" class="text-emerald-600 font-bold text-base mb-4"></p>
        <div id="modalVariantsContainer" class="space-y-3 mb-5"></div>
        <button type="button" id="modalAddBtn" onclick="confirmAddToCart()" class="w-full bg-stone-900 hover:bg-black text-white font-bold py-3.5 rounded-xl text-xs uppercase tracking-wider cursor-pointer transition">
            ADD TO BAG &rarr;
        </button>
    </div>
</div>

<!-- Slide-Out Shopping Bag Drawer -->
<div id="cartOverlay" onclick="toggleCart()" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-[99998] hidden"></div>
<aside id="cartDrawer" class="fixed top-0 right-0 h-full w-full max-w-md bg-white z-[99999] shadow-2xl p-6 flex flex-col justify-between translate-x-full transition-transform duration-300 text-stone-900">
    <div>
        <div class="flex justify-between items-center pb-4 border-b border-stone-100 mb-4">
            <div>
                <h3 class="font-bold text-sm uppercase tracking-wider text-stone-900 m-0">Your Bag</h3>
                <span class="text-[10px] text-stone-400 font-mono">WhatsApp Checkout</span>
            </div>
            <button type="button" onclick="toggleCart()" class="text-xs font-bold text-stone-400 hover:text-black cursor-pointer">&times; CLOSE</button>
        </div>
        <div id="cartItemsList" class="space-y-3 max-h-[45vh] overflow-y-auto"></div>
    </div>

    <div class="pt-4 border-t border-stone-100">
        <div class="flex justify-between items-center mb-4 font-mono">
            <span class="text-xs uppercase text-stone-400 font-bold">Total:</span>
            <span id="cartTotalPrice" class="font-bold text-xl text-emerald-600">{{ store.currency }}0.00</span>
        </div>
        <form id="checkoutForm" onsubmit="handleCheckout(event)" class="space-y-3">
            <input type="text" id="custName" required placeholder="Your Full Name" class="w-full p-3 border border-stone-200 rounded-xl text-xs outline-none focus:border-stone-900">
            <input type="text" id="custPhone" required placeholder="WhatsApp Number (e.g. 08012345678)" class="w-full p-3 border border-stone-200 rounded-lg text-xs outline-none focus:border-stone-900">
            <textarea id="custAddress" required placeholder="Delivery Address / Notes" rows="2" class="w-full p-3 border border-stone-200 rounded-lg text-xs outline-none focus:border-stone-900"></textarea>
            <button type="submit" id="checkoutBtn" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-4 rounded-xl text-xs uppercase tracking-wider cursor-pointer transition shadow-lg shadow-emerald-600/20">
                CHECKOUT ON WHATSAPP &rarr;
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
                <label class='text-[10px] font-bold text-stone-500 uppercase block mb-1'>${attr}</label>
                <select class='variant-select w-full p-2.5 border border-stone-200 rounded-lg text-xs outline-none bg-stone-50' data-attr='${attr}'>
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
            d.className = 'flex justify-between items-center text-xs pb-3 border-b border-stone-100';
            d.innerHTML = `
                <div>
                    <strong class="text-stone-900 block">${item.name}</strong>
                    ${item.variants ? `<p class="text-[10px] text-stone-400 m-0">${item.variants}</p>` : ''}
                    <span class="text-emerald-600 font-bold">${storeCurrency}${item.price.toLocaleString()}</span>
                </div>
                <button type="button" onclick="cart.splice(${idx}, 1); updateCartUI();" class="text-rose-500 font-bold text-base px-2 cursor-pointer">&times;</button>
            `;
            list.appendChild(d);
        });

        if (totalEl) totalEl.innerText = `${storeCurrency}${total.toLocaleString()}`;
    }

    async function handleCheckout(e) {
        e.preventDefault();
        if (cart.length === 0) {
            alert('Your shopping bag is empty. Please select an item first.');
            return;
        }

        const btn = document.getElementById('checkoutBtn');
        btn.innerText = 'ROUTING TO WHATSAPP...';
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
                alert(data.message || 'Error processing checkout.');
                btn.innerText = 'CHECKOUT ON WHATSAPP →';
                btn.disabled = false;
            }
        } catch (err) {
            alert('Connection error. Please try again.');
            btn.innerText = 'CHECKOUT ON WHATSAPP →';
            btn.disabled = false;
        }
    }
</script>
"""

def clean_html_fences(raw_text: str) -> str:
    raw_text = re.sub(r'^```html\s*', '', raw_text.strip())
    raw_text = re.sub(r'```$', '', raw_text).strip()
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
        print(f"OpenRouter HTTP {e.code} Error Details: {error_msg}")
        return None
    except Exception as e:
        print(f"OpenRouter Connection Error: {e}")
        return None


def generate_kiosk_template(kiosk_name: str, bio: str, prompt: str, logo_url: str = '', hero_url: str = '', bg_url: str = '', currency: str = '₦') -> str:
    """
    AI Visual Generator:
    - Queries Gemini / OpenRouter to design unique storefronts.
    - If AI succeeds, injects the bulletproof interactive cart engine.
    - If AI fails or times out, returns "" so Flask automatically renders templates/store/catalog.html!
    """
    system_instruction = (
        'You are an elite web designer creating a custom storefront website for a brand named "' + kiosk_name + '".\n'
        'Merchant Design Instructions: "' + prompt + '"\n'
        'Merchant Bio: "' + bio + '"\n\n'
        'Brand Assets: Logo="' + logo_url + '", Hero="' + hero_url + '", Background="' + bg_url + '", Currency="' + currency + '".\n'
        'Write a COMPLETE, BEAUTIFUL, MOBILE-FIRST HTML5 page using Tailwind CSS via CDN and Google Fonts.\n'
        'CRITICAL CONTRACT:\n'
        '1. In the header, include a BAG button that calls: onclick="toggleCart()"\n'
        '   with an element <span id="cartCountBadge">0</span>.\n'
        '2. Products Loop: Iterate using:\n'
        '   {% for p in regular_products %} ... display image {{ p.image if p.image.startswith("http") else url_for("static", filename="uploads/products/" + p.image) }}, title {{ p.name }}, price {{ store.currency }}{{ p.current_price }} ...\n'
        '   Every product card MUST have an order button calling: onclick="openProductModal({{ p.id }})"\n'
        '   {% endfor %}\n'
        '3. Flash Sales: Include {% if flash_sales %} ... {% for p in flash_sales %} ... {% endfor %} {% endif %}\n'
        'Do NOT write the modal or cart drawer HTML yourself—it will be automatically injected. Just build the storefront, header, and product cards!\n'
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
                print("Generated custom kiosk via Primary: Gemini! Injecting bulletproof engine...")
                return inject_bulletproof_chassis(raw_html)
        except Exception as e:
            print(f"Gemini API error: {e}")

    # 2. Fast Backup: OpenRouter
    openrouter_key = (os.environ.get('OPENROUTER_API_KEY') or '').strip()
    if openrouter_key:
        raw_response = query_openrouter(system_instruction, openrouter_key)
        if raw_response:
            raw_html = clean_html_fences(raw_response)
            if raw_html:
                print("Generated custom kiosk via Backup: OpenRouter! Injecting bulletproof engine...")
                return inject_bulletproof_chassis(raw_html)

    # 3. Clean Native Fallback: Returns empty string so Flask seamlessly renders app/templates/store/catalog.html!
    print("AI generation skipped or failed. Falling back to default catalog.html template.")
    return ""
