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
        api_key = 'your_api_key_here'  # Replace with actual key or use config
    
    if not api_key or api_key == 'your_api_key_here':
        return jsonify({"status": "error", "message": "API key not configured."}), 500

    # 2. The System Prompt (FIXED: Extremely strict about double braces)
    system_prompt = (
        "You are an expert frontend developer creating beautiful HTML flyers.\n"
        "You MUST respond with ONLY a valid JSON object containing three keys: \"name\", \"category\", and \"html\".\n"
        "DO NOT include markdown formatting, code blocks, or any text outside the JSON.\n\n"
        f"Product: {product.name}\n"
        f"Category: {category}\n"
        f"Price: ₦{product.current_price:,.2f}\n"
        f"Store: {store.name if store else 'Marketplace'}\n\n"
        "CRITICAL RULES:\n"
        "1. Output MUST be valid JSON only.\n"
        "2. \"name\": A short, catchy name (e.g., \"Newspaper Layout\")\n"
        "3. \"category\": Use the category provided above\n"
        "4. \"html\": Raw HTML/Tailwind CSS flyer code. Make it visually stunning.\n"
        "5. Use EXACTLY TWO curly braces on each side for placeholders, like this: {{PRODUCT_IMAGE}}. DO NOT use three braces.\n"
        "6. Required placeholders: {{PRODUCT_IMAGE}}, {{PRODUCT_NAME}}, {{PRICE}}, {{STORE_NAME}}, {{DESCRIPTION}}\n"
        "7. Use Tailwind CSS classes for styling\n\n"
        f"User request: {prompt}"
    )

    try:
        # 3. Call the AI
        print(f"🤖 Calling OpenRouter API...")
        ai_response = query_openrouter(system_prompt, api_key)
        
        if not ai_response:
            return jsonify({"status": "error", "message": "AI service did not respond."}), 500

        # 4. Clean the response
        clean_response = ai_response.strip()
        if clean_response.startswith("```"):
            first_newline = clean_response.find('\n')
            if first_newline > 0:
                clean_response = clean_response[first_newline:].strip()
        if clean_response.endswith("```"):
            clean_response = clean_response[:-3].strip()
        if clean_response.startswith("```json"):
            clean_response = clean_response[7:].strip()

        # 5. Parse JSON
        try:
            template_data = json.loads(clean_response)
        except json.JSONDecodeError:
            return jsonify({"status": "error", "message": "Invalid JSON from AI. Try a simpler prompt."}), 500

        if 'html' not in template_data:
            return jsonify({"status": "error", "message": "AI response missing HTML code."}), 500

        # 🛡️ SAFETY NET: Force double braces in case the AI used three
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

        # 7. Render the Preview using Jinja
        try:
            image_url = product.image if product.image.startswith('http') else url_for('static', filename='uploads/products/' + product.image)
            
            preview_html = render_template_string(
                new_template.html,
                PRODUCT_IMAGE=image_url,
                PRODUCT_NAME=product.name,
                PRICE=f"₦{product.current_price:,.2f}",
                STORE_NAME=store.name if store else "Marketplace",
                DESCRIPTION=product.description or "Premium quality product."
            )
        except Exception:
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
