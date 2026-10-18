import json
import os
from flask import Blueprint, request, jsonify, render_template_string, url_for
from flask_login import login_required, current_user
from app import db
from app.models import FlyerTemplate, Product
from app.utils.ai_builder import query_openrouter
from datetime import datetime

design_bp = Blueprint('design', __name__, url_prefix='/design')

@design_bp.route('/generate', methods=['POST'])
@login_required
def generate_flyer():
    data = request.get_json()
    prompt = data.get('prompt')
    product_id = data.get('product_id')
    category = data.get('category', 'General')

    if not prompt or not product_id:
        return jsonify({"status": "error", "message": "Missing prompt or product."}), 400

    product = Product.query.get(product_id)
    store = current_user.store if hasattr(current_user, 'store') else None
    
    if not product:
        return jsonify({"status": "error", "message": "Product not found."}), 404

    # 1. Get API Key
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        api_key = 'your_api_key_here' 
    
    if not api_key or api_key == 'your_api_key_here':
        return jsonify({"status": "error", "message": "API key not configured."}), 500

    # =====================================================================
    # 2. EXTRACT ALL RICH PRODUCT DATA
    # =====================================================================
    
    # A. Prices (Original vs Discount)
    original_price = f"₦{product.original_price:,.2f}"
    current_price = f"₦{product.current_price:,.2f}"
    has_discount = product.original_price > product.current_price

    # B. Flash Sale Badge (Pre-formatted HTML)
    # We build the HTML here so the AI just has to place it, rather than writing Jinja logic
    flash_sale_html = ""
    if product.is_flash_sale:
        flash_sale_html = '<div class="inline-flex items-center gap-1 bg-rose-500 text-white text-[10px] font-black uppercase px-2.5 py-1 rounded-full shadow-lg tracking-wider"><span>🔥</span> FLASH SALE</div>'

    # C. Attributes/Sizes (Pre-formatted HTML Pills)
    attributes_html = ""
    if hasattr(product, 'get_attributes'):
        attrs = product.get_attributes()
        if attrs:
            pills = ""
            for attr_name, attr_vals in attrs.items():
                # attr_vals might be a list or a string
                val_str = ", ".join(attr_vals) if isinstance(attr_vals, list) else attr_vals
                pills += f'<span class="inline-block text-[9px] font-mono font-semibold border border-stone-300/30 bg-stone-100/10 px-2 py-1 rounded-md backdrop-blur-sm">{attr_name}: {val_str}</span>'
            attributes_html = f'<div class="flex flex-wrap gap-1.5 mt-2">{pills}</div>'

    # D. WhatsApp Number
    whatsapp_number = getattr(store, 'whatsapp_number', '') if store else ''

    # =====================================================================
    # 3. THE "MEGA" SYSTEM PROMPT
    # =====================================================================
    system_prompt = (
        "You are a world-class graphic designer and frontend expert. Create a highly detailed, visually stunning HTML flyer.\n\n"
        f"Product: {product.name}\n"
        f"Category: {category}\n"
        f"Store: {store.name if store else 'Marketplace'}\n\n"
        
        "--- PRODUCT DATA TO DISPLAY ---\n"
        f"1. Current Price: {current_price}\n"
        f"2. Original Price: {original_price} {'(Show this with a strikethrough if there is a discount)' if has_discount else ''}\n"
        f"3. Flash Sale: {'YES - Make this VERY prominent with a red badge!' if product.is_flash_sale else 'No'}\n"
        f"4. Attributes/Sizes: {'YES - Display these clearly as tags/pills.' if attributes_html else 'None'}\n"
        f"5. WhatsApp Contact: {whatsapp_number if whatsapp_number else 'Not provided'}\n\n"

        "CRITICAL DESIGN RULES:\n"
        "1. Use CSS Grid/Flexbox for advanced layouts (columns, overlapping elements).\n"
        "2. Use beautiful typography (Serif for headlines, Sans-serif for body).\n"
        "3. Add decorative elements: Borders, dividers, shadows, gradients.\n"
        "4. Use Tailwind CSS for all styling.\n\n"

        "MANDATORY PLACEHOLDERS (Use EXACTLY these in your HTML):\n"
        "- {{PRODUCT_IMAGE}}: The main product photo (make it large and central).\n"
        "- {{PRODUCT_NAME}}: The headline/title.\n"
        "- {{DESCRIPTION}}: A short text block.\n"
        "- {{FLASH_SALE_HTML}}: Insert this EXACT string where the flash sale badge should go.\n"
        "- {{ATTRIBUTES_HTML}}: Insert this EXACT string where the size/attribute pills should go.\n"
        "- {{PRICE_BLOCK_HTML}}: Insert this EXACT string where the price should go.\n"
        "- {{WHATSAPP_HTML}}: Insert this EXACT string for the WhatsApp order button.\n\n"

        "OUTPUT FORMAT:\n"
        "Respond ONLY with a valid JSON object: {\"name\": \"Design Name\", \"category\": \"Category\", \"html\": \"<html>...</html>\"}\n"
        "Do not include markdown blocks.\n\n"
        f"User Request: {prompt}"
    )

    try:
        # 4. Call the AI
        print(f"🤖 Calling OpenRouter API...")
        ai_response = query_openrouter(system_prompt, api_key)
        
        if not ai_response:
            return jsonify({"status": "error", "message": "AI service did not respond."}), 500

        # 5. Clean and Parse JSON
        clean_response = ai_response.strip()
        if clean_response.startswith("```"):
            first_newline = clean_response.find('\n')
            if first_newline > 0: clean_response = clean_response[first_newline:].strip()
        if clean_response.endswith("```"):
            clean_response = clean_response[:-3].strip()
        if clean_response.startswith("```json"):
            clean_response = clean_response[7:].strip()

        try:
            template_data = json.loads(clean_response)
        except json.JSONDecodeError:
            return jsonify({"status": "error", "message": "Invalid JSON from AI. Try a simpler prompt."}), 500

        if 'html' not in template_data:
            return jsonify({"status": "error", "message": "AI response missing HTML code."}), 500

        # Safety net for braces
        template_data['html'] = template_data['html'].replace('{{{', '{{').replace('}}}', '}}')

        # 6. Save to Database
        new_template = FlyerTemplate(
            name=template_data.get('name', 'Custom Design'),
            category=template_data.get('category', category),
            creator_name=store.name if store else "Anonymous",
            original_context=prompt,
            html=template_data.get('html', ''),
            is_official=False
        )
        db.session.add(new_template)
        db.session.commit()

        # =====================================================================
        # 7. RENDER PREVIEW WITH ALL NEW DATA
        # =====================================================================
        try:
            image_url = product.image if product.image.startswith('http') else url_for('static', filename='uploads/products/' + product.image)
            
            # Pre-build the Price Block HTML
            if has_discount:
                price_block_html = f'<div class="flex items-baseline gap-2"><span class="text-[10px] line-through opacity-50 font-mono">{original_price}</span><span class="text-xl font-black font-mono text-rose-600">{current_price}</span></div>'
            else:
                price_block_html = f'<div class="text-xl font-black font-mono">{current_price}</div>'

            # Pre-build WhatsApp Button HTML
            whatsapp_html = ""
            if whatsapp_number:
                whatsapp_html = f'<a href="https://wa.me/{whatsapp_number}" class="inline-flex items-center gap-2 bg-[#16a34a] hover:bg-[#15803d] text-white text-xs font-bold px-4 py-2 rounded-lg shadow-md transition"><span>💬</span> Order on WhatsApp</a>'

            preview_html = render_template_string(
                new_template.html,
                PRODUCT_IMAGE=image_url,
                PRODUCT_NAME=product.name,
                DESCRIPTION=product.description or "Premium quality product.",
                FLASH_SALE_HTML=flash_sale_html,
                ATTRIBUTES_HTML=attributes_html,
                PRICE_BLOCK_HTML=price_block_html,
                WHATSAPP_HTML=whatsapp_html
            )
        except Exception as render_err:
            print(f"Render error: {render_err}")
            preview_html = new_template.html

        return jsonify({
            "status": "success",
            "template_id": new_template.id,
            "preview_html": preview_html,
            "name": new_template.name
        })

    except Exception as e:
        db.session.rollback()
        print(f"💥 Error: {str(e)}")
        return jsonify({"status": "error", "message": f"Server error: {str(e)[:100]}"}), 500
