import json
from flask import Blueprint, render_template_string, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import FlyerTemplate, Product
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

    # 2. The "Magic" System Prompt
    # Notice the quadruple braces {{{{...}}}}. Python f-strings turn {{ into {, 
    # so {{{{ becomes {{, which is exactly what we want the AI to see for Jinja!
    system_prompt = (
        "You are an expert UI/UX designer specializing in high-converting digital flyers.\n"
        f"The user wants a flyer for a product named \"{product.name}\" in the \"{category}\" category.\n\n"
        "CRITICAL RULES:\n"
        "1. You MUST output a valid JSON object with exactly these three keys: \"name\", \"category\", and \"html\".\n"
        "2. \"name\": A short, catchy name for this design style (e.g., \"Neon Streetwear\").\n"
        "3. \"category\": The category provided by the user.\n"
        "4. \"html\": The raw HTML/Tailwind CSS code for the flyer.\n"
        "5. DO NOT use real image URLs or text in the HTML. You MUST use exactly these Jinja placeholders:\n"
        "   {{{{PRODUCT_IMAGE}}}}, {{{{PRODUCT_NAME}}}}, {{{{PRICE}}}}, {{{{STORE_NAME}}}}, {{{{DESCRIPTION}}}}.\n"
        "6. Output ONLY the raw JSON. Do not wrap it in markdown blocks like ```json.\n"
    )

    user_prompt = f"Design request: {prompt}"

    try:
        # 3. Call your AI API (Replace 'call_ai_api' with your actual function!)
        ai_response = call_ai_api(system_prompt, user_prompt) 
        
        # Clean up the response
        clean_response = ai_response.strip().replace("```json", "").replace("```", "")
        template_data = json.loads(clean_response)

        # 4. Save to Database
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

        # 5. Render the Preview using Jinja!
        # This is much safer than .replace(). Jinja will inject the variables directly.
        preview_html = render_template_string(
            new_template.html,
            PRODUCT_IMAGE=product.image_url,
            PRODUCT_NAME=product.name,
            PRICE=f"₦{product.price:,.2f}",
            STORE_NAME=store.name if store else "Marketplace",
            DESCRIPTION=product.description or "Premium quality."
        )

        return jsonify({
            "status": "success",
            "template_id": new_template.id,
            "preview_html": preview_html,
            "name": new_template.name
        })

    except json.JSONDecodeError:
        return jsonify({"status": "error", "message": "AI returned invalid JSON. Please try again."}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
