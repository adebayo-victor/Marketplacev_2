"""
app/routes/design.py
AI Flyer Design Studio + Community Template Gallery + Async Worker Integration.
"""
import base64
import io
import ipaddress
import json
import os
import random
import re
import socket
import uuid
import requests
from datetime import datetime, timedelta
from html import escape as html_escape
from urllib.parse import quote, urlparse

from flask import Blueprint, current_app, jsonify, render_template_string, request, url_for
from flask_login import current_user, login_required
from jinja2 import TemplateSyntaxError
from markupsafe import Markup
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import FlyerTemplate, Product, TemplateReview

design_bp = Blueprint('design', __name__, url_prefix='/design')

FLYER_W, FLYER_H = 1080, 1350
SCOPE_CLASS = 'ai-flyer-scope'
MAX_GALLERY = 30

ALLOWED_VARS = (
    'PRODUCT_IMAGE', 'PRODUCT_NAME', 'PRICE', 'STORE_NAME', 'DESCRIPTION',
    'IS_FLASH_SALE', 'ATTRIBUTES', 'ORIGINAL_PRICE', 'DISCOUNT_PRICE',
    'WHATSAPP', 'DISCOUNT_PERCENT',
)
REQUIRED_VARS = ('PRODUCT_IMAGE', 'PRODUCT_NAME', 'PRICE')

ART_DIRECTIONS = [
    "Oversized-type poster: the product name set enormous (200px+), cropped by the canvas edge, the photo overlapping the letters, one hot spot colour against a deep neutral.",
    "Luxury editorial: asymmetric two-column grid, hairlines, a tall arch-masked photo, generous negative space, a refined high-contrast serif, a restrained two-colour palette.",
    "Streetwear brutalist: chunky Archivo Black / Anton type, rotated stickers, thick outlines, hard offset shadows, raw flat colour blocks.",
    "Swiss grid: strict 12-column structure, one flat saturated background, small precise type, photo in a clean rectangle, the price as the focal point.",
    "Retro 70s sunburst: concentric warm arcs from CSS gradients, rounded display type (Syne), photo inside a thick ring, orange / plum / mustard palette.",
    "Soft studio: large centred photo on a seamless coloured gradient with a long soft floor shadow, floating pill tags, friendly geometric sans (Poppins).",
    "Sale blast: diagonal colour split, huge price numerals, a starburst built with clip-path, high energy but a tidy hierarchy.",
    "Magazine cover: masthead-style store name across the top, full-bleed photo with a gradient scrim, cover-line tagline and price in the lower third.",
]

# ============================================================================
# Helpers: user / store / product
# ============================================================================
def _current_store():
    # Check the plural 'stores' relationship (which is what we use in models.py)
    user_stores = getattr(current_user, 'stores', None)
    if user_stores is not None:
        first_store = user_stores.first()  # .first() works on SQLAlchemy query objects
        if first_store is not None:
            return first_store
            
    # Fallback to singular 'store' or 'kiosk' just in case
    for attr in ('store', 'kiosk'):
        obj = getattr(current_user, attr, None)
        if obj is not None and not isinstance(obj, (list, tuple)):
            return obj
            
    return None

def _product_store(product):
    store = _current_store()
    if store is not None:
        return store
    for attr in ('store', 'kiosk'):
        obj = getattr(product, attr, None)
        if obj is not None and not isinstance(obj, (list, tuple)):
            return obj
    return None

def _user_owns_product(product, store):
    if store is None:
        return True
    for fk in ('store_id', 'kiosk_id'):
        if hasattr(product, fk):
            return getattr(product, fk) == store.id
    return True

def _money(currency, amount):
    amount = float(amount or 0)
    return f"{currency}{amount:,.0f}" if amount.is_integer() else f"{currency}{amount:,.2f}"

def _price_info(product, currency):
    original = float(getattr(product, 'original_price', 0) or 0)
    current = 0.0
    for attr in ('discount_price', 'current_price'):
        value = getattr(product, attr, None)
        if value:
            current = float(value)
            break
    if current <= 0:
        current = original
    has_discount = original > 0 and 0 < current < original
    return {
        'original': _money(currency, original),
        'current': _money(currency, current),
        'has_discount': has_discount,
        'percent': round((1 - current / original) * 100) if has_discount else 0,
    }

# ============================================================================
# Product image -> data URI
# ============================================================================
def _bytes_to_data_uri(raw, mime):
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw))
        im.thumbnail((1600, 1600))
        buf = io.BytesIO()
        if im.mode in ('RGBA', 'LA', 'P'):
            im.convert('RGBA').save(buf, 'PNG', optimize=True)
            mime = 'image/png'
        else:
            im.convert('RGB').save(buf, 'JPEG', quality=88)
            mime = 'image/jpeg'
        raw = buf.getvalue()
    except Exception:
        pass
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"

def _is_public_host(hostname):
    try:
        for info in socket.getaddrinfo(hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True
    except Exception:
        return False

def _fetch_remote_image(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not _is_public_host(parsed.hostname or ''):
        return None
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 FlyerStudio'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            mime = resp.headers.get_content_type()
            if not mime.startswith('image/'):
                return None
            raw = resp.read(8 * 1024 * 1024)
        return _bytes_to_data_uri(raw, mime)
    except Exception:
        return None

def _product_image_src(product):
    image = (getattr(product, 'image', '') or '').strip()
    if not image:
        return ''
    if image.startswith(('http://', 'https://')):
        return _fetch_remote_image(image) or quote(image, safe=":/?&=%#@+,;~")
    path = os.path.join(current_app.static_folder, 'uploads', 'products', os.path.basename(image))
    if os.path.isfile(path):
        with open(path, 'rb') as fh:
            return _bytes_to_data_uri(fh.read(), 'image/png' if path.lower().endswith('.png') else 'image/jpeg')
    return url_for('static', filename='uploads/products/' + image, _external=True)

# ============================================================================
# Template context
# ============================================================================
def _build_context(product, store):
    currency = getattr(store, 'currency', None) or '₦'
    price = _price_info(product, currency)

    attributes = ''
    attrs = product.get_attributes() if hasattr(product, 'get_attributes') else None
    if attrs:
        pills = ''.join(
            '<span style="display:inline-block;border:2px solid currentColor;'
            "font-family:'Montserrat',sans-serif;font-weight:700;font-size:22px;"
            f'padding:8px 20px;border-radius:999px">{html_escape(str(name))}: '
            f'{html_escape(", ".join(map(str, vals)) if isinstance(vals, (list, tuple)) else str(vals))}</span>'
            for name, vals in attrs.items()
        )
        attributes = f'<div style="display:flex;flex-wrap:wrap;gap:12px">{pills}</div>'

    whatsapp = ''
    number = str(getattr(store, 'whatsapp_number', '') or '').strip()
    if number:
        whatsapp = (
            '<span style="display:inline-flex;align-items:center;gap:16px;background:#16a34a;color:#fff;'
            "font-family:'Montserrat',sans-serif;padding:16px 32px;border-radius:999px;"
            'box-shadow:0 12px 30px rgba(22,163,74,.45)"><span style="font-size:34px">💬</span>'
            '<span style="display:flex;flex-direction:column;line-height:1.15">'
            '<span style="font-size:15px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;opacity:.85">'
            'Order on WhatsApp</span>'
            f'<span style="font-size:32px;font-weight:800">{html_escape(number)}</span></span></span>'
        )

    description = (getattr(product, 'description', '') or 'Premium quality product.').strip()
    if len(description) > 180:
        description = description[:177].rstrip() + '…'

    def safe(text):
        return Markup(html_escape(str(text or '')))

    return {
        'PRODUCT_IMAGE': Markup(_product_image_src(product)),
        'PRODUCT_NAME': safe(product.name),
        'PRICE': price['current'],
        'ORIGINAL_PRICE': price['original'],
        'DISCOUNT_PRICE': price['current'] if price['has_discount'] else '',
        'DISCOUNT_PERCENT': f"{price['percent']}%" if price['has_discount'] else '',
        'STORE_NAME': safe(getattr(store, 'name', None) or 'Marketplace'),
        'DESCRIPTION': safe(description),
        'IS_FLASH_SALE': 'FLASH SALE' if getattr(product, 'is_flash_sale', False) else '',
        'ATTRIBUTES': Markup(attributes),
        'WHATSAPP': Markup(whatsapp),
    }

# ============================================================================
# AI prompt
# ============================================================================
PROMPT_TEMPLATE = """You are a cutting-edge graphic designer and front-end developer who specializes in replicating REAL-WORLD print designs using ONLY HTML and CSS. You create magazine covers, newspaper layouts, posters, flyers, brochures, and promotional materials that look like they were designed in professional design software—but you build them entirely with HTML structure and CSS styling.

YOUR EXPERTISE:
- You replicate authentic print design aesthetics: newspapers with mastheads and columns, magazines with covers and spreads, brutalist posters, luxury editorial spreads, retro advertisements, modern minimalist flyers, etc.
- You use ONLY HTML elements and CSS properties—no external libraries, no JavaScript, no images except the provided product image placeholder.
- You create depth and visual interest through: CSS gradients, box-shadows, text-shadows, clip-path, mix-blend-mode, transforms, filters, and creative typography.
- You understand real design principles: hierarchy, contrast, alignment, proximity, whitespace, and visual balance.

PRODUCT FACTS (use the placeholders, NEVER hard-code these values):
- Name: [[NAME]]
- Category: [[CATEGORY]]
- Store: [[STORE]]
- is_flash_sale: [[FLASH]]
- Has a discount: [[DISCOUNT]]
- Has attributes/sizes: [[ATTRS]]
- Has a WhatsApp number: [[WA]]

CANVAS SPECIFICATIONS (NON-NEGOTIABLE):
- Dimensions: Exactly [[W]] x [[H]] pixels. Use px units ONLY (no vh/vw/rem/%).
- Root element structure:
  <div style="width:[[W]]px;height:[[H]]px;position:relative;overflow:hidden;background:#fff">
    <style>...your CSS here...</style>
    ...your HTML structure...
  </div>
- Nothing may scroll or overflow. All content must fit within the canvas.

TECHNICAL RULES:
1. Use a SINGLE <style> block at the top for all CSS.
2. Use semantic HTML structure with divs, spans, headings, paragraphs, and images.
3. Prefix ALL custom CSS classes with 'fl-' (e.g., .fl-headline, .fl-price-tag, .fl-badge).
4. Use CSS variables for your color palette at the top of the <style> block:
   :root { --fl-primary: #1a1a1a; --fl-accent: #d96c3b; --fl-bg: #fdfbf7; }
5. NO external resources: no <link> tags, no @import, no external fonts (use the loaded fonts below), no external images.
6. CRITICAL JSON RULE: Your HTML will be placed inside a JSON string. You MUST use single quotes (') for ALL HTML attributes (e.g., <div class='fl-root'>). NEVER use double quotes inside the HTML, or the JSON will break.
7. NO JavaScript, no event handlers, no interactivity.

AVAILABLE FONTS (use these ONLY):
- Display/Serif: 'Playfair Display', 'DM Serif Display', 'Bebas Neue'
- Bold/Impact: 'Anton', 'Archivo Black', 'Oswald'
- Modern/Sans: 'Syne', 'Space Grotesk', 'Poppins', 'Montserrat', 'Inter'
- Mono: 'JetBrains Mono'
The Naira sign (₦) renders correctly only in: Montserrat, Poppins, Inter, Space Grotesk.

DESIGN APPROACH:
- Study the user's request and replicate a REAL design style (e.g., "newspaper" = masthead, columns, serif fonts, grayscale image; "magazine cover" = large headline, cover image, taglines, date bar; "luxury editorial" = asymmetric grid, generous whitespace, elegant serif fonts).
- Create a strong visual hierarchy: one dominant focal point (usually the product name or image), secondary elements (price, store name), and supporting details (description, attributes).
- Use dramatic scale contrast: make important elements MUCH larger than secondary ones.
- Choose a cohesive color palette (2-3 colors max) and stick to it.
- The product image MUST be large (minimum 40% of canvas), use object-fit: cover, and be presented beautifully (mask it, frame it, add overlays, use mix-blend-mode).
- Keep all text within a 60px safe margin from edges.

REQUIRED PLACEHOLDERS (use EXACTLY these with double curly braces, NO spaces, NO filters):
- {{PRODUCT_IMAGE}} - The product image URL. Use as: <img src='{{PRODUCT_IMAGE}}' style="..."> or background-image: url('{{PRODUCT_IMAGE}}')
- {{PRODUCT_NAME}} - The product name (may be long, max 3 lines)
- {{PRICE}} - The current price (always show this)
- {{ORIGINAL_PRICE}} - The original price (show with strikethrough if there's a discount)
- {{DISCOUNT_PRICE}} - The discounted price (show if discount exists, otherwise empty)
- {{DISCOUNT_PERCENT}} - The discount percentage like "25%" (empty if no discount)
- {{STORE_NAME}} - The store/kiosk name
- {{DESCRIPTION}} - Product description (max 180 chars)
- {{IS_FLASH_SALE}} - Text "FLASH SALE" if active, otherwise empty
- {{ATTRIBUTES}} - Pre-formatted HTML pills for sizes/options (empty if none)
- {{WHATSAPP}} - Pre-formatted green WhatsApp CTA button (empty if no number)

CONDITIONAL LOGIC (the ONLY Jinja syntax allowed):
{% if IS_FLASH_SALE %}...design flash sale badge...{% endif %}
{% if DISCOUNT_PRICE %}...show original price struck through + discount price...{% else %}...show regular price...{% endif %}
{% if ATTRIBUTES %}...show attributes pills...{% endif %}

Design intelligently for BOTH states (when placeholder is empty AND when it has content). Never leave ugly gaps.

OUTPUT FORMAT:
Respond with ONE valid JSON object ONLY (no markdown, no commentary, no explanation):
{"name": "Evocative design name (e.g., 'The Daily Gazette - Breaking News')", "category": "[[CATEGORY]]", "html": "<style>...CSS...</style><div style='width:[[W]]px;height:[[H]]px;...'>...HTML...</div>"}

USER'S DESIGN REQUEST (interpret this and replicate the appropriate real-world design style):
\"\"\"[[REQUEST]]\"\"\"
"""

def _build_prompt(product, store, category, user_prompt):
    price = _price_info(product, getattr(store, 'currency', None) or '₦')
    attrs = product.get_attributes() if hasattr(product, 'get_attributes') else None
    values = {
        '[[NAME]]': str(product.name)[:120],
        '[[CATEGORY]]': category,
        '[[STORE]]': str(getattr(store, 'name', None) or 'Marketplace')[:80],
        '[[FLASH]]': 'True' if getattr(product, 'is_flash_sale', False) else 'False',
        '[[DISCOUNT]]': f"yes ({price['percent']}% off)" if price['has_discount'] else 'no',
        '[[ATTRS]]': 'yes' if attrs else 'no',
        '[[WA]]': 'yes' if getattr(store, 'whatsapp_number', None) else 'no',
        '[[W]]': str(FLYER_W),
        '[[H]]': str(FLYER_H),
        '[[DIRECTION]]': random.choice(ART_DIRECTIONS),
        '[[REQUEST]]': user_prompt.replace('"""', "'''"),
    }
    prompt = PROMPT_TEMPLATE
    for key, val in values.items():
        prompt = prompt.replace(key, val)
    return prompt

# ============================================================================
# Parsing, sanitising, scoping, rendering AI output
# ============================================================================
_VARS = '|'.join(ALLOWED_VARS)
_KEEP_RE = re.compile(
    r'\{\{\s*(?:' + _VARS + r')\s*\}\}'
    r'|\{%\s*(?:(?:if|elif)\s+(?:not\s+)?(?:' + _VARS + r')|else|endif)\s*%\}'
)

def _neutralize_jinja(html):
    html = re.sub(r'\{{2,3}\s*([A-Z_]+)\s*\}{2,3}', r'{{\1}}', html)
    kept = []
    def stash(match):
        kept.append(match.group(0))
        return f'\x00{len(kept) - 1}\x00'
    html = _KEEP_RE.sub(stash, html)
    html = re.sub(r'\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}', '', html, flags=re.S)
    html = html.replace('{{', '{ {').replace('{%', '{ %').replace('{#', '{ #')
    return re.sub(r'\x00(\d+)\x00', lambda m: kept[int(m.group(1))], html)

def _sanitize(raw):
    fenced = re.search(r'```(?:html)?\s*(.*?)```', raw, re.S | re.I)
    if fenced:
        raw = fenced.group(1)
    styles = re.findall(r'<style[^>]*>(.*?)</style>', raw, re.S | re.I)
    body = re.search(r'<body[^>]*>(.*)</body>', raw, re.S | re.I)
    markup = body.group(1) if body else raw
    markup = re.sub(r'<style[^>]*>.*?</style>', '', markup, flags=re.S | re.I)
    markup = re.sub(r'<head[^>]*>.*?</head>', '', markup, flags=re.S | re.I)
    markup = re.sub(r'<(script|iframe|object|embed|form)\b[^>]*>.*?</\1\s*>', '', markup, flags=re.S | re.I)
    markup = re.sub(r'<(script|link|meta|base|iframe|object|embed)\b[^>]*/?>', '', markup, flags=re.I)
    markup = re.sub(r'<!DOCTYPE[^>]*>|</?html[^>]*>|</?body[^>]*>|<title>.*?</title>', '', markup, flags=re.S | re.I)
    markup = re.sub(r'\son\w+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', '', markup, flags=re.I)
    markup = re.sub(r'(href|src|xlink:href)\s*=\s*(["\']?)\s*javascript:[^"\'>\s]*\2', r'\1=\2#\2', markup, flags=re.I)
    css = '\n'.join(styles)
    css = re.sub(r'@import[^;]+;', '', css, flags=re.I)
    css = re.sub(r'expression\s*\(|javascript:', '', css, flags=re.I)
    return (f'<style>{css}</style>' if css.strip() else '') + markup.strip()

def _scope_css(css, scope):
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    out, i, n = [], 0, len(css)
    while i < n:
        j = css.find('{', i)
        if j == -1:
            break
        prelude = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            depth += (css[k] == '{') - (css[k] == '}')
            k += 1
        block, i = css[j + 1:k - 1], k
        if re.match(r'@(media|supports)', prelude, re.I):
            out.append(f'{prelude}{{{_scope_css(block, scope)}}}')
        elif prelude.startswith('@'):
            out.append(f'{prelude}{{{block}}}')
        else:
            selectors = []
            for sel in prelude.split(','):
                sel = sel.strip()
                if not sel:
                    continue
                if sel == '*':
                    selectors += [scope, f'{scope} *']
                    continue
                rest = re.sub(r'^(?:html|body|:root)\s*', '', sel).strip()
                selectors.append(f'{scope} {rest}' if rest else scope)
            if selectors:
                out.append(f'{",".join(selectors)}{{{block}}}')
    return '\n'.join(out)

def _wrap_and_scope(clean_html):
    scoped = re.sub(
        r'<style>(.*?)</style>',
        lambda m: f'<style>{_scope_css(m.group(1), "." + SCOPE_CLASS)}</style>',
        clean_html, flags=re.S,
    )
    return (
        f'<div class="{SCOPE_CLASS}" style="width:{FLYER_W}px;height:{FLYER_H}px;position:relative;'
        f'overflow:hidden;isolation:isolate">'
        f'<div id="flyer" style="width:{FLYER_W}px;height:{FLYER_H}px;position:relative;overflow:hidden">'
        f'{scoped}</div></div>'
    )

def _has_required(html):
    return all(re.search(r'\{\{\s*' + name + r'\s*\}\}', html) for name in REQUIRED_VARS)

def _render_preview(template_html, product, store):
    prepared = _wrap_and_scope(_neutralize_jinja(_sanitize(template_html)))
    ctx = _build_context(product, store)
    try:
        return render_template_string(prepared, **ctx)
    except TemplateSyntaxError:
        return render_template_string(re.sub(r'\{%.*?%\}', '', prepared, flags=re.S), **ctx)

def _template_dict(t, my_store_id=None):
    return {
        'id': t.id,
        'name': t.name,
        'category': t.category or 'General',
        'creator_name': t.creator_name or 'Anonymous',
        'usage_count': t.usage_count or 0,
        'likes_count': t.likes_count or 0,
        'avg_star_rating': round(t.avg_star_rating or 0, 1),
        'total_ratings': t.total_ratings or 0,
        'is_mine': bool(my_store_id and t.creator_store_id == my_store_id),
    }

# ============================================================================
# 1. DISPATCH: Send task to external worker
# ============================================================================
@design_bp.route('/generate', methods=['POST'])
@login_required
def generate_flyer():
    data = request.get_json(silent=True) or {}
    user_prompt = (data.get('prompt') or '').strip()[:800]
    category = (data.get('category') or 'General').strip()[:60]
    
    try:
        product_id = int(data.get('product_id'))
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid product ID.'}), 400

    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'status': 'error', 'message': 'Product not found.'}), 404

    store = _current_store()
    if not _user_owns_product(product, store):
        return jsonify({'status': 'error', 'message': 'Unauthorized.'}), 403

    task_id = str(uuid.uuid4())
    system_prompt = _build_prompt(product, store, category, user_prompt)

    base_url = os.environ.get('APP_BASE_URL') or request.host_url.rstrip('/')
    callback_url = f"{base_url}/design/worker-callback"
    secret_key = os.environ.get('BUILDER_SECRET_KEY', 'your-secure-secret-key')

    pending_template = FlyerTemplate(
        task_id=task_id,
        name="Generating Design...",
        category=category,
        creator_name=getattr(store, 'name', None) or 'Anonymous',
        creator_store_id=getattr(store, 'id', None),
        original_context=user_prompt,
        html="", 
        is_official=False,
    )
    db.session.add(pending_template)
    db.session.commit()

    # --- UPDATED URL LOGIC ---
    worker_base_url = os.environ.get('WORKER_URL', 'http://localhost:5001').rstrip('/')
    worker_execute_url = f"{worker_base_url}/execute"
    
    try:
        worker_response = requests.post(worker_execute_url, json={
            "task_id": task_id,
            "task_type": "flyer",
            "callback_url": callback_url,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "secret": secret_key
        }, timeout=10)
        
        if worker_response.status_code != 202:
            return jsonify({'status': 'error', 'message': 'Worker failed to accept task.'}), 502
            
        return jsonify({
            'status': 'accepted',
            'message': 'Design is being generated. Please wait...',
            'task_id': task_id,
            'template_id': pending_template.id
        }), 202

    except requests.exceptions.RequestException as e:
        db.session.rollback()
        current_app.logger.error(f"Worker dispatch failed: {e}")
        return jsonify({'status': 'error', 'message': 'AI Worker is currently unreachable.'}), 503

# ============================================================================
# 2. WEBHOOK: Receive completed HTML from the external worker
# ============================================================================
@design_bp.route('/worker-callback', methods=['POST'])
def worker_callback():
    auth_header = request.headers.get('Authorization', '')
    secret_key = os.environ.get('BUILDER_SECRET_KEY', 'your-secure-secret-key')
    
    if auth_header != f"Bearer {secret_key}":
        current_app.logger.warning("Unauthorized worker callback attempt")
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    task_id = data.get('task_id')
    task_type = data.get('task_type')
    status = data.get('status')
    raw_html = data.get('html', '')

    if task_type != 'flyer':
        current_app.logger.warning(f"Received {task_type} task at the flyer callback route!")
        return jsonify({'status': 'error', 'message': 'Invalid task type for this route'}), 400

    if status != 'success' or not raw_html:
        current_app.logger.error(f"Worker callback failed for task {task_id}: {data.get('message')}")
        return jsonify({'status': 'error', 'message': 'Worker reported failure'}), 400

    template = FlyerTemplate.query.filter_by(task_id=task_id).first()
    if not template:
        current_app.logger.error(f"Pending template not found for task_id: {task_id}")
        return jsonify({'status': 'error', 'message': 'Template not found'}), 404

    try:
        # 1. CLEANUP: Aggressively strip markdown artifacts and the literal word "json"
        if isinstance(raw_html, str):
            clean_str = raw_html.strip()
            # Remove markdown code blocks
            if clean_str.lower().startswith('```json'):
                clean_str = clean_str[7:].strip()
            elif clean_str.lower().startswith('```'):
                clean_str = clean_str[3:].strip()
            # Remove the literal word "json" at the start
            if clean_str.lower().startswith('json'):
                clean_str = clean_str[4:].strip()
            # Remove trailing backticks
            if clean_str.endswith('```'):
                clean_str = clean_str[:-3].strip()
        else:
            clean_str = str(raw_html)

        final_html = clean_str
        
        # 2. PARSE: Try to extract the actual HTML from the JSON
        try:
            parsed_data = json.loads(clean_str)
            if isinstance(parsed_data, dict):
                if 'html' in parsed_data:
                    final_html = parsed_data['html']
                # Update the template name if the AI provided a good one!
                if 'name' in parsed_data and parsed_data['name']:
                    template.name = parsed_data['name']
                if 'category' in parsed_data and parsed_data['category']:
                    template.category = parsed_data['category']
        except (json.JSONDecodeError, TypeError) as e:
            current_app.logger.warning(f"JSON parse failed for task {task_id}: {e}. Using cleaned raw string.")

        # 3. SANITIZE & SAVE
        clean_html = _neutralize_jinja(_sanitize(final_html))
        template.html = clean_html
        
        db.session.commit()
        current_app.logger.info(f"✅ Successfully saved and parsed generated flyer for task {task_id}")
        
        return jsonify({'status': 'success', 'template_id': template.id}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Failed to process callback for task {task_id}")
        return jsonify({'status': 'error', 'message': 'Server error processing HTML'}), 500

# ============================================================================
# 3. COMMUNITY GALLERY
# ============================================================================
@design_bp.route('/get-templates', methods=['GET'])
@login_required
def get_templates():
    try:
        store = _current_store()
        my_id = getattr(store, 'id', None)
        rows = (
            FlyerTemplate.query
            .filter(FlyerTemplate.is_official.is_(False))
            .order_by(FlyerTemplate.usage_count.desc(),
                      FlyerTemplate.avg_star_rating.desc(),
                      FlyerTemplate.id.desc())
            .limit(MAX_GALLERY)
            .all()
        )
        return jsonify({'status': 'success', 'templates': [_template_dict(t, my_id) for t in rows]})
    except Exception:
        current_app.logger.exception('Loading community templates failed')
        return jsonify({'status': 'error', 'message': 'Could not load community designs.'}), 500

# ============================================================================
# 4. RENDER TEMPLATE (Used by frontend polling & gallery clicks)
# ============================================================================
@design_bp.route('/render-template/<int:template_id>', methods=['GET'])
@login_required
def render_template_route(template_id):
    try:
        product_id = int(request.args.get('product_id', ''))
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Missing product.'}), 400

    template = db.session.get(FlyerTemplate, template_id)
    product = db.session.get(Product, product_id)
    
    if not template or not product:
        return jsonify({'status': 'error', 'message': 'Design or product not found.'}), 404

    if not template.html:
        return jsonify({'status': 'pending', 'message': 'Still generating...'}), 202

    store = _product_store(product)
    if not _user_owns_product(product, store):
        return jsonify({'status': 'error', 'message': 'Not allowed.'}), 403

    try:
        return jsonify({
            'status': 'success',
            'template_id': template.id,
            'name': template.name,
            'creator_name': template.creator_name or 'Anonymous',
            'preview_html': _render_preview(template.html, product, store),
        })
    except Exception:
        current_app.logger.exception('Rendering template %s failed', template_id)
        return jsonify({'status': 'error', 'message': 'This design could not be rendered.'}), 500

# ============================================================================
# 5. RATE-AND-DOWNLOAD GATE
# ============================================================================
@design_bp.route('/rate-and-download', methods=['POST'])
@login_required
def rate_and_download():
    data = request.get_json(silent=True) or {}
    try:
        template_id = int(data.get('template_id'))
        star = int(data.get('star_rating'))
        scale = int(data.get('scale_rating'))
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid rating data.'}), 400

    if not (1 <= star <= 5) or not (1 <= scale <= 10):
        return jsonify({'status': 'error', 'message': 'Ratings are out of range.'}), 400

    store = _current_store()
    if store is None:
        return jsonify({'status': 'error', 'message': 'You need a store to rate designs.'}), 403

    template = db.session.get(FlyerTemplate, template_id)
    if not template or template.is_official:
        return jsonify({'status': 'error', 'message': 'Design not found.'}), 404

    if template.creator_store_id and template.creator_store_id == store.id:
        return jsonify({'status': 'success', 'counted': False})

    try:
        existing = TemplateReview.query.filter_by(template_id=template.id, store_id=store.id).first()
        if existing is None:
            db.session.add(TemplateReview(
                template_id=template.id, store_id=store.id, star_rating=star, scale_rating=scale))
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()

        avg_star, avg_scale, total = (
            db.session.query(
                func.avg(TemplateReview.star_rating),
                func.avg(TemplateReview.scale_rating),
                func.count(TemplateReview.id),
            )
            .filter(TemplateReview.template_id == template.id)
            .one()
        )

        (FlyerTemplate.query.filter_by(id=template.id).update({
            FlyerTemplate.avg_star_rating: round(float(avg_star or 0), 2),
            FlyerTemplate.avg_scale_rating: round(float(avg_scale or 0), 2),
            FlyerTemplate.total_ratings: int(total or 0),
            FlyerTemplate.usage_count: FlyerTemplate.usage_count + 1,
            FlyerTemplate.last_used_at: datetime.utcnow(),
        }, synchronize_session=False))
        db.session.commit()

        db.session.refresh(template)
        return jsonify({
            'status': 'success',
            'counted': True,
            'avg_star_rating': round(template.avg_star_rating or 0, 1),
            'total_ratings': template.total_ratings,
            'usage_count': template.usage_count,
        })
    except Exception:
        db.session.rollback()
        current_app.logger.exception('rate-and-download failed for template %s', template_id)
        return jsonify({'status': 'error', 'message': 'Could not save your rating. Please try again.'}), 500
