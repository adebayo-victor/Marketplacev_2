import os
import re

def generate_kiosk_template(kiosk_name: str, bio: str, prompt: str, logo_url: str = None, hero_url: str = None, bg_url: str = None, currency: str = '₦') -> str:
    """
    Uses Gemini AI to write a complete, standalone Jinja2 HTML template 
    incorporating the merchant's prompt and Cloudinary image links.
    """
    api_key = os.environ.get('AI_API_KEY')

    # If Gemini API key is configured, query the model
    if api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')

            system_instruction = f"""
You are an expert web designer creating a custom storefront website for a brand named "{kiosk_name}".
Merchant Design Prompt: "{prompt}"
Merchant Bio: "{bio}"

Brand Assets Provided:
- Logo Image URL: "{logo_url or ''}"
- Hero / Showcase Banner URL: "{hero_url or ''}"
- Background Image URL: "{bg_url or ''}"
- Currency Symbol: "{currency}"

Write a COMPLETE, BEAUTIFUL, MOBILE-FIRST HTML5 page using Tailwind CSS via CDN.
IMPORTANT JINJA2 / FUNCTIONAL REQUIREMENTS:
1. Product Loop: You MUST iterate over regular products using:
   {{% for p in regular_products %}}
     Display product name ({{{{ p.name }}}}), price ({{{{ store.currency }}}}{{{{ "{:,.2f}".format(p.current_price) }}}}), image ({{{{ url_for('static', filename='uploads/products/' + p.image) if not p.image.startswith('http') else p.image }}}}), description ({{{{ p.description }}}}).
     Include an order button calling: openProductModal({{{{ p.id }}}}, {{{{ p.name|tojson }}}}, {{{{ p.current_price }}}}, {{{{ p.get_attributes()|tojson }}}})
   {{% endfor %}}

2. Flash Sales: Include:
   {{% if flash_sales %}}
     {{% for p in flash_sales %}} ... {{{{ p.name }}}} ... {{% endfor %}}
   {{% endif %}}

3. Shopping Bag Drawer & Checkout Modal: Include an interactive slide-out cart drawer and a checkout form that submits via fetch to '/{{{{ store.slug }}}}/checkout'.

4. Dynamic Open Graph tags in <head>:
   <meta property="og:title" content="{{{{ store.name }}}}">
   <meta property="og:description" content="{{% if store.show_public_stats %}}Over {{{{ '{:,}'.format(store.views_count) }}}} visits • Verified Merchant{{% else %}}{{{{ store.bio }}}}{{% endif %}}">

Output ONLY the raw HTML code. Do NOT wrap in markdown ```html code blocks.
"""
            response = model.generate_content(system_instruction)
            raw_html = response.text.strip()
            
            # Clean markdown fences if any
            raw_html = re.sub(r'^```html\s*', '', raw_html)
            raw_html = re.sub(r'```$', '', raw_html).strip()
            return raw_html
        except Exception as e:
            print(f"Gemini generation error: {e}, using bespoke fallback.")

    # Fallback Template (Clean & tailored with their Cloudinary assets)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{{{ store.name }}}} // Official Store</title>
    <meta property="og:title" content="{{{{ store.name }}}}">
    <meta property="og:description" content="{{% if store.show_public_stats %}}Over {{{{ '{:,}'.format(store.views_count) }}}} visits • Verified Merchant{{% else %}}{{{{ store.bio }}}}{{% endif %}}">
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ 
            font-family: 'Montserrat', sans-serif; 
            {f"background-image: url('{bg_url}'); background-size: cover; background-attachment: fixed;" if bg_url else "background-color: #fdfcfb;"}
        }}
    </style>
</head>
<body class="min-h-screen text-stone-900 flex flex-col justify-between">
    <header class="bg-white/95 backdrop-blur border-b border-stone-200 py-4 px-6 sticky top-0 z-40">
        <div class="max-w-6xl mx-auto flex items-center justify-between">
            <div class="flex items-center gap-3">
                {f"<img src='{logo_url}' class='h-10 w-10 object-contain rounded-full'>" if logo_url else ""}
                <div>
                    <h1 class="text-lg font-bold tracking-tight text-stone-900 m-0">{{{{ store.name }}}}</h1>
                    <p class="text-xs text-stone-500 m-0">{{{{ store.bio }}}}</p>
                </div>
            </div>
            <button onclick="toggleCart()" class="bg-stone-900 hover:bg-black text-white text-xs font-bold px-4 py-2.5 rounded-xl uppercase tracking-wider flex items-center gap-2">
                <span>BAG</span>
                <span id="cartCountBadge" class="bg-amber-500 text-stone-900 px-1.5 py-0.5 rounded-full text-[10px]">0</span>
            </button>
        </div>
    </header>

    {f"<div class='max-w-6xl mx-auto px-6 mt-6 w-full'><img src='{hero_url}' class='w-full h-48 md:h-64 object-cover rounded-2xl shadow-sm'></div>" if hero_url else ""}

    <main class="max-w-6xl mx-auto px-6 py-10 w-full flex-grow">
        {{% if flash_sales %}}
        <div class="mb-10">
            <h2 class="text-sm font-bold uppercase tracking-wider text-rose-600 mb-4">🔥 Flash Deals</h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                {{% for p in flash_sales %}}
                <div class="bg-white p-5 rounded-2xl shadow-sm border border-stone-100 flex flex-col justify-between">
                    <div>
                        <img src="{{{{ p.image if p.image.startswith('http') else url_for('static', filename='uploads/products/' + p.image) }}}}" class="h-40 w-full object-cover rounded-xl mb-3">
                        <h3 class="font-bold text-sm">{{{{ p.name }}}}</h3>
                        <p class="text-xs text-stone-400 mb-2">{{{{ p.description }}}}</p>
                    </div>
                    <div>
                        <div class="mb-3">
                            <span class="line-through text-stone-400 text-xs">{{{{ store.currency }}}}{{{{ "{:,.2f}".format(p.original_price) }}}}</span>
                            <span class="font-bold text-rose-600 text-base ml-1">{{{{ store.currency }}}}{{{{ "{:,.2f}".format(p.current_price) }}}}</span>
                        </div>
                        <button onclick='openProductModal({{{{ p.id }}}}, {{{{ p.name|tojson }}}}, {{{{ p.current_price }}}}, {{{{ p.get_attributes()|tojson }}}})' class="w-full bg-rose-600 hover:bg-rose-700 text-white font-bold py-2 rounded-xl text-xs uppercase">
                            ORDER ON SALE
                        </button>
                    </div>
                </div>
                {{% endfor %}}
            </div>
        </div>
        {{% endif %}}

        <h2 class="text-lg font-bold text-stone-800 mb-6">Catalog</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
            {{% for p in regular_products %}}
            <div class="bg-white p-5 rounded-2xl shadow-sm border border-stone-100 flex flex-col justify-between">
                <div>
                    <img src="{{{{ p.image if p.image.startswith('http') else url_for('static', filename='uploads/products/' + p.image) }}}}" class="h-44 w-full object-cover rounded-xl mb-3">
                    <h3 class="font-bold text-sm text-stone-900">{{{{ p.name }}}}</h3>
                    <p class="text-xs text-stone-400 mb-3">{{{{ p.description }}}}</p>
                </div>
                <div>
                    <div class="font-bold text-stone-900 text-sm mb-3">{{{{ store.currency }}}}{{{{ "{:,.2f}".format(p.current_price) }}}}</div>
                    {{% if p.stock > 0 %}}
                    <button onclick='openProductModal({{{{ p.id }}}}, {{{{ p.name|tojson }}}}, {{{{ p.current_price }}}}, {{{{ p.get_attributes()|tojson }}}})' class="w-full bg-stone-900 hover:bg-black text-white font-bold py-2.5 rounded-xl text-xs uppercase tracking-wider">
                        SELECT & ORDER
                    </button>
                    {{% else %}}
                    <button disabled class="w-full bg-stone-100 text-stone-400 py-2.5 rounded-xl text-xs uppercase">Sold Out</button>
                    {{% endif %}}
                </div>
            </div>
            {{% else %}}
            <p class="text-xs italic text-stone-400 col-span-3">No products available in this kiosk yet.</p>
            {{% endfor %}}
        </div>
    </main>

    <!-- Modal & Cart Drawer -->
    <div id="productModal" class="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4 hidden">
        <div class="bg-white p-6 max-w-sm w-full rounded-2xl shadow-xl relative">
            <button onclick="closeProductModal()" class="absolute top-3 right-3 text-stone-400 font-bold">&times;</button>
            <h3 id="modalProductName" class="font-bold text-base mb-1"></h3>
            <p id="modalProductPrice" class="text-emerald-600 font-bold text-sm mb-4"></p>
            <div id="modalVariantsContainer" class="space-y-3 mb-5"></div>
            <button onclick="confirmAddToCart()" class="w-full bg-stone-900 text-white font-bold py-3 rounded-xl text-xs uppercase">Add to Bag &rarr;</button>
        </div>
    </div>

    <aside id="cartDrawer" class="fixed top-0 right-0 h-full w-full max-w-md bg-white z-50 shadow-2xl p-6 flex flex-col justify-between translate-x-full transition-transform duration-300">
        <div>
            <div class="flex justify-between items-center pb-4 border-b border-stone-100 mb-4">
                <h3 class="font-bold text-sm uppercase tracking-wider text-stone-900">Your Bag</h3>
                <button onclick="toggleCart()" class="text-xs font-bold text-stone-400">&times; CLOSE</button>
            </div>
            <div id="cartItemsList" class="space-y-3 max-h-[45vh] overflow-y-auto"></div>
        </div>
        <div class="pt-4 border-t border-stone-100">
            <div class="flex justify-between items-center mb-4">
                <span class="text-xs uppercase text-stone-400 font-bold">Total</span>
                <span id="cartTotalPrice" class="font-bold text-lg text-stone-900">{{{{ store.currency }}}}0.00</span>
            </div>
            <form onsubmit="handleCheckout(event)" class="space-y-2">
                <input type="text" id="custName" required placeholder="Full Name" class="w-full p-2.5 border border-stone-200 rounded-lg text-xs outline-none">
                <input type="text" id="custPhone" required placeholder="WhatsApp Number" class="w-full p-2.5 border border-stone-200 rounded-lg text-xs outline-none">
                <textarea id="custAddress" required placeholder="Delivery Address" rows="2" class="w-full p-2.5 border border-stone-200 rounded-lg text-xs outline-none"></textarea>
                <button type="submit" id="checkoutBtn" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 rounded-xl text-xs uppercase tracking-wider">
                    CHECKOUT ON WHATSAPP &rarr;
                </button>
            </form>
        </div>
    </aside>

    <footer class="bg-white border-t border-stone-100 py-6 text-center text-xs text-stone-400">
        Powered by <a href="/" class="font-bold text-stone-800">Marketplace</a>
    </footer>

    <script>
        const storeSlug = {{{{ store.slug|tojson }}}};
        const storeCurrency = {{{{ store.currency|tojson }}}};
        let cart = [], currentModalProduct = null;
        function toggleCart() {{ document.getElementById('cartDrawer').classList.toggle('translate-x-full'); }}
        function openProductModal(id, name, price, attributes) {{
            currentModalProduct = {{ id, name, price, attributes }};
            document.getElementById('modalProductName').innerText = name;
            document.getElementById('modalProductPrice').innerText = `${{storeCurrency}}${{price.toLocaleString()}}`;
            const container = document.getElementById('modalVariantsContainer');
            container.innerHTML = '';
            for (const [attr, opts] of Object.entries(attributes)) {{
                const group = document.createElement('div');
                group.innerHTML = `<label class='text-[10px] font-bold text-stone-500 uppercase block mb-1'>${{attr}}</label><select class='variant-select w-full p-2 border border-stone-200 rounded text-xs' data-attr='${{attr}}'>${{opts.map(o => `<option value='${{o}}'>${{o}}</option>`).join('')}}</select>`;
                container.appendChild(group);
            }}
            document.getElementById('productModal').classList.remove('hidden');
        }}
        function closeProductModal() {{ document.getElementById('productModal').classList.add('hidden'); }}
        function confirmAddToCart() {{
            const selected = [];
            document.querySelectorAll('.variant-select').forEach(s => selected.push(`${{s.getAttribute('data-attr')}}: ${{s.value}}`));
            cart.push({{ product_id: currentModalProduct.id, name: currentModalProduct.name, price: currentModalProduct.price, variants: selected.join(' | '), quantity: 1 }});
            updateCartUI(); closeProductModal(); toggleCart();
        }}
        function updateCartUI() {{
            const list = document.getElementById('cartItemsList');
            document.getElementById('cartCountBadge').innerText = cart.length;
            list.innerHTML = ''; let total = 0;
            cart.forEach((i, idx) => {{
                total += i.price * i.quantity;
                const d = document.createElement('div');
                d.className = 'flex justify-between items-center text-xs pb-2 border-b border-stone-50';
                d.innerHTML = `<div><strong>${{i.name}}</strong><p class='text-[10px] text-stone-400'>${{i.variants}}</p><span class='text-stone-900 font-bold'>${{storeCurrency}}${{i.price.toLocaleString()}}</span></div><button onclick='cart.splice(${{idx}}, 1); updateCartUI();' class='text-rose-500 font-bold'>&times;</button>`;
                list.appendChild(d);
            }});
            document.getElementById('cartTotalPrice').innerText = `${{storeCurrency}}${{total.toLocaleString()}}`;
        }}
        async function handleCheckout(e) {{
            e.preventDefault();
            const btn = document.getElementById('checkoutBtn');
            btn.innerText = 'ROUTING TO WHATSAPP...'; btn.disabled = true;
            try {{
                const res = await fetch(`/${{storeSlug}}/checkout`, {{
                    method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ customer_name: document.getElementById('custName').value, customer_phone: document.getElementById('custPhone').value, delivery_address: document.getElementById('custAddress').value, cart: cart }})
                }});
                const data = await res.json();
                if (data.status === 'success') {{ window.location.href = data.whatsapp_url; }}
                else {{ alert(data.message); btn.innerText = 'CHECKOUT ON WHATSAPP →'; btn.disabled = false; }}
            }} catch(err) {{ alert('Connection error.'); btn.disabled = false; }}
        }}
    </script>
</body>
</html>"""
