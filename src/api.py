"""Production Shopora API."""
from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .agent import get_agent, shutdown_agent
from .auth import router as auth_router
from .cache import cache_delete_prefix, cache_get, cache_set, redis_ping
from .config import settings
from .database import check_database, get_db
from .models import Cart, Customer, Order, OrderItem, Product
from .recommendations import recommend_for_user
from .search_service import hybrid_search
from .security import get_current_user
from .tools import compute_match_score, get_product_image, product_to_dict

logger = logging.getLogger("shopora.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.environment != "test":
        check_database()
    yield
    shutdown_agent()


app = FastAPI(title=settings.app_name, description="AI shopping assistant API", version=settings.app_version, docs_url="/docs" if settings.environment != "production" else None, redoc_url="/redoc" if settings.environment != "production" else None, lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request error", extra={"request_id": request_id})
        raise
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    logger.info("%s %s -> %s %.1fms", request.method, request.url.path, response.status_code, (time.perf_counter() - started) * 1000)
    return response


app.include_router(auth_router)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str = Field(default="", max_length=100)


class ProductRecommendation(BaseModel):
    id: int; name: str; description: str; category: str; price: float; rating: float; stock: int; match_score: int; reason: str; specs: list[str]; image: str


class ChatResponse(BaseModel):
    response: str; products: list[ProductRecommendation]; thread_id: str


class CartAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: int = Field(gt=0); quantity: int = Field(default=1, ge=1, le=100)


class CartUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: int = Field(ge=0, le=100)


def normalize_thread_id(thread_id: str) -> str:
    if not thread_id: return str(uuid4())
    try: return str(UUID(thread_id))
    except ValueError as exc: raise HTTPException(400, "thread_id must be a valid UUID") from exc


def extract_products(events: list) -> list[dict]:
    out=[]; seen=set()
    for event in events:
        content=getattr(event,"content",None)
        if not isinstance(content,str): continue
        try: data=json.loads(content)
        except Exception: logger.debug("Skipping non-JSON tool event"); continue
        if isinstance(data,dict): products=data.get("recommendations") or data.get("products") or ([data] if "id" in data and "name" in data else [])
        elif isinstance(data,list): products=data
        else: products=[]
        for p in products:
            if not isinstance(p,dict): continue
            pid=p.get("id") or p.get("product_id")
            if not pid or pid in seen: continue
            seen.add(pid); p["id"]=int(pid); p.setdefault("match_score", int(float(p.get("rating") or 4)*20)); p.setdefault("reason","Matches your requirements."); p.setdefault("specs",[]); p.setdefault("image",get_product_image(p.get("category",""))); p.setdefault("description",""); out.append(p)
    return out


@app.get("/")
def root(): return {"service":"shopora-api","version":settings.app_version,"status":"running"}

@app.get("/health")
def health(): return {"status":"healthy"}

@app.get("/ready")
def ready():
    database_ok=redis_ok=False
    try: check_database(); database_ok=True
    except Exception: logger.exception("Database readiness failed")
    redis_ok=redis_ping()
    ready_state=database_ok and (redis_ok or settings.environment != "production")
    return {"status":"ready" if ready_state else "not_ready","database":database_ok,"redis":redis_ok}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, user: Customer = Depends(get_current_user)):
    thread_id=normalize_thread_id(request.thread_id)
    config={"configurable":{"thread_id":thread_id,"user_id":user.id,"user_role":user.role}}
    try:
        response_text=""; tool_messages=[]
        for chunk, metadata in get_agent().stream({"messages":[request.message]}, config, stream_mode="messages"):
            node=metadata.get("langgraph_node")
            if node=="llm" and chunk.content: response_text += chunk.content
            elif node=="tools": tool_messages.append(chunk)
        products=[]
        for p in extract_products(tool_messages):
            try: products.append(ProductRecommendation.model_validate(p))
            except Exception: logger.warning("Skipping malformed product")
        return ChatResponse(response=response_text,products=products,thread_id=thread_id)
    except Exception:
        logger.exception("Agent request failed")
        raise HTTPException(503,"Shopora is temporarily unable to process the request")


@app.get("/products")
def get_all_products(db: Session = Depends(get_db)):
    cached=cache_get("products:all")
    if cached is not None: return cached
    products=db.scalars(select(Product).order_by(Product.id)).all()
    result=[]
    for p in products:
        d=product_to_dict(p); score,reason=compute_match_score(p); d.update(match_score=score,reason=reason); result.append(d)
    cache_set("products:all",result,60); return result


@app.get("/products/search")
def search_products_endpoint(q: str = Query(default="",max_length=200), db: Session = Depends(get_db)):
    if not q.strip(): return get_all_products(db)
    key=f"products:hybrid:{q.strip().lower()}"; cached=cache_get(key)
    if cached is not None: return cached
    result=[]
    for p,score,source in hybrid_search(db,q,12):
        d=product_to_dict(p); m_score,reason=compute_match_score(p,search_term=q); d.update(match_score=m_score,reason=f"{reason}; {source} search"); result.append(d)
    cache_set(key,result,60); return result


@app.get("/products/{product_id}")
def get_product_endpoint(product_id: int, db: Session = Depends(get_db)):
    p=db.get(Product,product_id)
    if not p: raise HTTPException(404,"Product not found")
    d=product_to_dict(p); score,reason=compute_match_score(p); d.update(match_score=score,reason=reason); return d


def cart_payload(db: Session, user_id: int):
    items=db.scalars(select(Cart).options(selectinload(Cart.product)).where(Cart.customer_id==user_id).order_by(Cart.id)).all()
    result=[]; total=0.0
    for item in items:
        subtotal=float(item.product.price)*item.quantity; total+=subtotal
        result.append({"id":item.id,"product_id":item.product.id,"name":item.product.name,"category":item.product.category,"price":float(item.product.price),"quantity":item.quantity,"subtotal":subtotal,"image":get_product_image(item.product.category)})
    return {"items":result,"total":total,"count":len(result)}


@app.get("/cart")
def get_cart(user: Customer = Depends(get_current_user), db: Session = Depends(get_db)): return cart_payload(db,user.id)

@app.post("/cart/add")
def add_to_cart(payload: CartAddRequest, user: Customer = Depends(get_current_user), db: Session = Depends(get_db)):
    p=db.get(Product,payload.product_id)
    if not p: raise HTTPException(404,"Product not found")
    item=db.scalar(select(Cart).where(Cart.customer_id==user.id,Cart.product_id==p.id)); new_qty=(item.quantity if item else 0)+payload.quantity
    if new_qty>p.stock: raise HTTPException(409,f"Only {p.stock} units are available")
    if item: item.quantity=new_qty
    else: db.add(Cart(customer_id=user.id,product_id=p.id,quantity=payload.quantity))
    db.commit(); cache_delete_prefix(f"cart:{user.id}"); return {"message":"Added to cart",**cart_payload(db,user.id)}

@app.patch("/cart/{product_id}")
def update_cart(product_id:int,payload:CartUpdateRequest,user:Customer=Depends(get_current_user),db:Session=Depends(get_db)):
    item=db.scalar(select(Cart).options(selectinload(Cart.product)).where(Cart.customer_id==user.id,Cart.product_id==product_id))
    if not item: raise HTTPException(404,"Item not in cart")
    if payload.quantity>item.product.stock: raise HTTPException(409,"Insufficient stock")
    if payload.quantity==0: db.delete(item)
    else: item.quantity=payload.quantity
    db.commit(); return {"message":"Cart updated",**cart_payload(db,user.id)}

@app.delete("/cart/{product_id}")
def remove_cart(product_id:int,user:Customer=Depends(get_current_user),db:Session=Depends(get_db)):
    item=db.scalar(select(Cart).where(Cart.customer_id==user.id,Cart.product_id==product_id))
    if not item: raise HTTPException(404,"Item not in cart")
    db.delete(item); db.commit(); return {"message":"Removed",**cart_payload(db,user.id)}

@app.post("/checkout")
def checkout(user: Customer = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Cart).options(selectinload(Cart.product)).where(Cart.customer_id == user.id).with_for_update()).all()
    if not items: raise HTTPException(409, "Your cart is empty")
    total = 0.0
    for item in items:
        if item.quantity > item.product.stock: raise HTTPException(409, f"Insufficient stock for {item.product.name}")
        total += float(item.product.price) * item.quantity
    order = Order(customer_id=user.id, total_amount=total, status="pending")
    db.add(order); db.flush()
    for item in items:
        db.add(OrderItem(order_id=order.id, product_id=item.product_id, quantity=item.quantity, price=item.product.price))
        item.product.stock -= item.quantity
        db.delete(item)
    db.commit(); cache_delete_prefix(f"cart:{user.id}")
    return {"message": "Order placed successfully", "order_id": order.id, "status": order.status, "total_amount": total}

@app.get("/orders")
def get_orders(user:Customer=Depends(get_current_user),db:Session=Depends(get_db)):
    orders=db.scalars(select(Order).options(selectinload(Order.items).selectinload(OrderItem.product),selectinload(Order.shipment)).where(Order.customer_id==user.id).order_by(Order.id.desc())).all()
    return [{"order_id":o.id,"status":o.status,"total_amount":float(o.total_amount),"items":[{"product_id":i.product_id,"name":i.product.name,"price":float(i.price),"quantity":i.quantity,"subtotal":float(i.price)*i.quantity,"image":get_product_image(i.product.category)} for i in o.items],"shipment":({"tracking_number":o.shipment.tracking_number,"carrier":o.shipment.carrier,"current_location":o.shipment.current_location,"shipment_status":o.shipment.shipment_status,"estimated_delivery":o.shipment.estimated_delivery.isoformat() if o.shipment.estimated_delivery else None} if o.shipment else None)} for o in orders]

@app.get("/recommendations")
def recommendations(user:Customer=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=recommend_for_user(db,user,8)
    return [{**product_to_dict(r["product"]),"match_score":r["score"],"reason":r["reason"]} for r in rows]

@app.post("/admin/embeddings")
def rebuild_embeddings(user:Customer=Depends(get_current_user),db:Session=Depends(get_db)):
    if user.role!="admin": raise HTTPException(403,"Admin access required")
    from .search_service import index_products
    return {"indexed":index_products(db)}
