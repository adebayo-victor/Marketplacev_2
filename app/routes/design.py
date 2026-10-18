import json
import os
from flask import Blueprint, request, jsonify, render_template_string
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
        # Try fallback from your config
        api_key = 'your_api_key_here'  # Replace with actual key or use config
    
    if not api_key or api_key == 'your_api_key_here':
        return jsonify({"status": "error", "message": "API key not configured. Please set OPENROUTER_API_KEY environment variable."}), 500

    # 2. The System Prompt - More strict about JSON output
    system_prompt = (
        "You are an expert frontend developer creating HTML flyers.\n"
        "You MUST respond with ONLY a valid JSON object containing three keys: \"name\", \"category\", and \"html\".\n"
        "DO NOT include markdown formatting, code blocks, or any text outside the JSON.\n\n"
        f"Product: {product.name}\n"
        f"Category: {category}\n"
        f"Price: ₦{product.price:,.2f}\n"
        f"Store: {store.name if store else 'Marketplace'}\n\n"
        "CRITICAL RULES:\n"
        "1. Output MUST be valid JSON only - no markdown, no ```json blocks\n"
        "2. \"name\": A short, catchy name (e.g., \"Newspaper Layout\")\n"
        "3. \"category\": Use the category provided above\n"
        "4. \"html\": Raw HTML/Tailwind CSS flyer code\n"
        "5. Use EXACTLY these Jinja placeholders: {{{{PRODUCT_IMAGE}}}}, {{{{PRODUCT_NAME}}}}, {{{{PRICE}}}}, {{{{STORE_NAME}}}}, {{{{DESCRIPTION}}}}\n"
        "6. Make the design modern, professional, and mobile-responsive\n"
        "7. Use Tailwind CSS classes for styling\n"
        "8. Include the product image placeholder prominently\n\n"
        f"User request: {prompt}"
    )

    try:
        # 3. Call the AI
        print(f"🤖 Calling OpenRouter API for user: {current_user.id if current_user else 'anonymous'}")
        ai_response = query_openrouter(system_prompt, api_key)
        
        if not ai_response:
            print("❌ AI returned None/empty response")
            return jsonify({"status": "error", "message": "AI service did not respond. Please try again."}), 500

        print(f"📥 Raw AI response (first 200 chars): {ai_response[:200]}...")

        # 4. Clean the response - remove markdown code blocks
        clean_response = ai_response.strip()
        
        # Remove ```json or ``` at start and end
        if clean_response.startswith("```"):
            # Find the first newline after ```
            first_newline = clean_response.find('\n')
            if first_newline > 0:
                clean_response = clean_response[first_newline:].strip()
        
        if clean_response.endswith("```"):
            clean_response = clean_response[:-3].strip()
        
        # Also try to extract JSON if it's wrapped
        if clean_response.startswith("```json"):
            clean_response = clean_response[7:].strip()
        
        print(f"🧹 Cleaned response (first 200 chars): {clean_response[:200]}...")

        # 5. Parse JSON
        try:
            template_data = json.loads(clean_response)
        except json.JSONDecodeError as json_err:
            print(f" JSON Decode Error: {str(json_err)}")
            print(f"Response was: {clean_response[:500]}")
            return jsonify({
                "status": "error", 
                "message": f"Invalid JSON from AI: {str(json_err)[:100]}. Try a simpler prompt."
            }), 500

        # 6. Validate the data
        if 'html' not in template_data:
            print("❌ AI response missing 'html' key")
            return jsonify({
                "status": "error", 
                "message": "AI response missing HTML code. Try again."
            }), 500

        # 7. Save to Database
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
        print(f"✅ Template saved with ID: {new_template.id}")

        # 8. Render the Preview using Jinja
        try:
            preview_html = render_template_string(
                new_template.html,
                PRODUCT_IMAGE=product.image_url if hasattr(product, 'image_url') else (product.image if hasattr(product, 'image') else '/static/images/placeholder.jpg'),
                PRODUCT_NAME=product.name,
                PRICE=f"₦{product.price:,.2f}",
                STORE_NAME=store.name if store else "Marketplace",
                DESCRIPTION=product.description or "Premium quality product."
            )
            print("✅ Jinja rendering successful")
        except Exception as render_err:
            print(f"❌ Jinja render error: {str(render_err)}")
            # Fallback: just use the HTML as-is
            preview_html = new_template.html

        return jsonify({
            "status": "success",
            "template_id": new_template.id,
            "preview_html": preview_html,
            "name": new_template.name
        })

    except Exception as e:
        db.session.rollback()
        print(f"💥 Unexpected error in generate_flyer: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error", 
            "message": f"Server error: {str(e)[:100]}"
        }), 500
