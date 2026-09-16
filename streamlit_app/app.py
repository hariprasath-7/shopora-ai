import json
import logging

import streamlit as st
from sqlalchemy import select

from src.agent import agent
from src.database import SessionLocal
from src.models import Customer, Product
from src.tools import get_product_image

logger = logging.getLogger("shopora.streamlit")

# Page configuration
st.set_page_config(
    page_title="Shopora — AI Shopping Agent",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🛒 Shopora — AI Shopping Agent")
st.markdown("Your intelligent conversational shopping assistant powered by LangGraph & Groq.")
st.info(
    "This Streamlit view is a lightweight demo console for the agent and doesn't use "
    "the real login flow (see the React app for that). Cart, checkout, and order "
    "tools act on a demo account scoped to the label you pick in the sidebar.",
    icon="ℹ️",
)


def get_or_create_demo_customer(label: str) -> Customer:
    """Look up (or create) a demo Customer row for a given sidebar label.

    The tool layer requires an authenticated user_id for anything touching
    cart/orders/payments. This gives the Streamlit console a stable, isolated
    demo identity per label without needing a full login form.
    """
    email = f"streamlit-demo-{label.strip().lower() or 'default'}@shopora.local"
    with SessionLocal() as db:
        customer = db.scalar(select(Customer).where(Customer.email == email))
        if customer is None:
            customer = Customer(name=f"Streamlit Demo ({label})", email=email, hashed_password=None)
            db.add(customer)
            db.commit()
            db.refresh(customer)
        return customer


# Session state initialization
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hello! I'm Shopora, your AI shopping assistant. How can I help you find products, compare options, or manage your shopping cart today?",
            "products": [],
        }
    ]

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "streamlit-session"

if "demo_user_label" not in st.session_state:
    st.session_state.demo_user_label = "default"

# Sidebar controls
with st.sidebar:
    st.header("⚙️ Workspace Options")
    session_id = st.text_input("Session ID / Thread ID", value=st.session_state.thread_id)
    st.session_state.thread_id = session_id

    demo_user_label = st.text_input(
        "Demo customer label",
        value=st.session_state.demo_user_label,
        help="Cart and orders are scoped to this demo identity. Use different labels to simulate different shoppers.",
    )
    st.session_state.demo_user_label = demo_user_label
    demo_customer = get_or_create_demo_customer(demo_user_label)
    st.caption(f"Acting as: **{demo_customer.name}** (customer id {demo_customer.id})")

    if st.button("Clear Chat History", use_container_width=True):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Chat history cleared. How can I help you today?",
                "products": [],
            }
        ]
        st.rerun()

    st.markdown("---")
    st.header("📦 Quick Catalog Peek")
    db = SessionLocal()
    try:
        total_prods = db.query(Product).count()
        st.write(f"Total Products in DB: **{total_prods}**")
        categories = [c[0] for c in db.query(Product.category).distinct().all()]
        st.write(f"Categories: {', '.join(categories)}")
    finally:
        db.close()

# Render chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Render products if attached
        if msg.get("products"):
            st.markdown("### 🛍️ Recommended Products")
            cols = st.columns(min(len(msg["products"]), 3))
            for idx, prod in enumerate(msg["products"]):
                with cols[idx % 3]:
                    st.image(prod.get("image") or get_product_image(prod.get("category", "")), use_container_width=True)
                    st.subheader(prod.get("name", "Product"))
                    st.write(f"**Price:** ₹{prod.get('price', 0):,.0f}")
                    st.write(f"**Rating:** ⭐ {prod.get('rating', 0)}")
                    if prod.get("match_score"):
                        st.write(f"**Match:** {prod.get('match_score')}%")
                    if prod.get("reason"):
                        st.caption(f"💡 {prod.get('reason')}")

# Chat input
if prompt := st.chat_input("Ask about laptops, monitors, headphones, cart, orders..."):
    # Append user message
    st.session_state.messages.append({"role": "user", "content": prompt, "products": []})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process with agent
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        extracted_products = []
        seen_pids = set()

        config = {
            "configurable": {
                "thread_id": st.session_state.thread_id,
                "user_id": demo_customer.id,
                "user_role": demo_customer.role,
            }
        }

        try:
            with st.spinner("Shopora is thinking..."):
                for chunk, metadata in agent.stream(
                    {"messages": [prompt]},
                    config,
                    stream_mode="messages",
                ):
                    node = metadata.get("langgraph_node")
                    if node == "llm" and chunk.content:
                        full_response += chunk.content
                        message_placeholder.markdown(full_response + "▌")
                    
                    elif node == "tools" and getattr(chunk, "content", None):
                        try:
                            data = json.loads(chunk.content)
                            p_list = []
                            if isinstance(data, dict) and "recommendations" in data:
                                p_list = data["recommendations"]
                            elif isinstance(data, dict) and "products" in data:
                                p_list = data["products"]
                            elif isinstance(data, list):
                                p_list = data
                            
                            for p in p_list:
                                if isinstance(p, dict):
                                    pid = p.get("id") or p.get("product_id")
                                    if pid and pid not in seen_pids:
                                        seen_pids.add(pid)
                                        extracted_products.append(p)
                        except Exception:
                            logger.debug("Skipping non-JSON tool event", exc_info=True)

            message_placeholder.markdown(full_response if full_response else "I have updated your request.")
            st.session_state.messages.append({
                "role": "assistant",
                "content": full_response,
                "products": extracted_products,
            })
            if extracted_products:
                st.rerun()

        except Exception as err:
            error_msg = f"An error occurred while connecting to the agent: {err}"
            message_placeholder.error(error_msg)
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_msg,
                "products": [],
            })
