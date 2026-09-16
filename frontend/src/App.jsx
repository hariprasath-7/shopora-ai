import { useState, useEffect, useRef, useCallback } from "react";
import "./App.css";
import {
  sendMessage,
  fetchProducts,
  searchProducts,
  fetchCart,
  addToCartAPI,
  removeFromCartAPI,
  updateCartQuantityAPI,
  fetchOrders,
  checkoutAPI,
  checkHealth,
  getCurrentThreadId,
  login, register, restoreSession, logout, fetchRecommendations,
} from "./services/api";

// ============================================================
// Helpers
// ============================================================

function formatPrice(price) {
  if (typeof price === "string") return price;
  return `₹${Number(price).toLocaleString("en-IN")}`;
}

function loadSaved() {
  try {
    const data = localStorage.getItem("shopora-saved");
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

function persistSaved(items) {
  localStorage.setItem("shopora-saved", JSON.stringify(items));
}

function loadCompare() {
  try {
    const data = localStorage.getItem("shopora-compare");
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

function persistCompare(items) {
  localStorage.setItem("shopora-compare", JSON.stringify(items));
}

// ============================================================
// App
// ============================================================

function App() {
  const [dark, setDark] = useState(() => {
    return localStorage.getItem("shopora-dark") === "true";
  });
  const [active, setActive] = useState("AI Shopper");
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [saved, setSaved] = useState(loadSaved);
  const [cart, setCart] = useState([]);
  const [cartTotal, setCartTotal] = useState(0);
  const [checkingOut, setCheckingOut] = useState(false);
  const [checkoutError, setCheckoutError] = useState("");
  const [thinking, setThinking] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);

  // Discover
  const [discoverQuery, setDiscoverQuery] = useState("");
  const [discoverProducts, setDiscoverProducts] = useState([]);
  const [discoverLoading, setDiscoverLoading] = useState(false);

  // Recommendations
  const [recProducts, setRecProducts] = useState([]);
  const [recLoading, setRecLoading] = useState(false);

  // Compare
  const [compareItems, setCompareItems] = useState(loadCompare);

  // Orders
  const [orders, setOrders] = useState([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [trackingOrder, setTrackingOrder] = useState(null);

  // Backend status
  const [backendOk, setBackendOk] = useState(true);
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  // Thread ID
  const [threadId] = useState(getCurrentThreadId);

  useEffect(() => {
    restoreSession().then(setUser).finally(() => setAuthLoading(false));
  }, []);

  // Refs
  const conversationRef = useRef(null);

  // ============================================================
  // Effects
  // ============================================================

  // Dark mode persistence
  useEffect(() => {
    localStorage.setItem("shopora-dark", dark);
  }, [dark]);

  // Persist saved
  useEffect(() => {
    persistSaved(saved);
  }, [saved]);

  // Persist compare
  useEffect(() => {
    persistCompare(compareItems);
  }, [compareItems]);

  // Auto-scroll conversation
  useEffect(() => {
    if (conversationRef.current) {
      conversationRef.current.scrollTop = conversationRef.current.scrollHeight;
    }
  }, [messages, thinking]);

  // Check backend health on mount
  useEffect(() => {
    checkHealth()
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false));
  }, []);

  // Load cart from backend
  const refreshCart = useCallback(async () => {
    try {
      const data = await fetchCart(threadId);
      setCart(data.items || []);
      setCartTotal(data.total || 0);
    } catch {
      // Cart might be empty, that's fine
    }
  }, [threadId]);

  useEffect(() => {
    let ignore = false;
    fetchCart(threadId)
      .then((data) => {
        if (!ignore) {
          setCart(data.items || []);
          setCartTotal(data.total || 0);
        }
      })
      .catch(() => {});
    return () => {
      ignore = true;
    };
  }, [threadId]);

  // Load products for discover on first visit
  useEffect(() => {
    if (active === "Discover" && discoverProducts.length === 0) {
      let ignore = false;
      fetchProducts()
        .then((data) => {
          if (!ignore) setDiscoverProducts(data);
        })
        .catch(() => {})
        .finally(() => {
          if (!ignore) setDiscoverLoading(false);
        });
      return () => {
        ignore = true;
      };
    }
  }, [active, discoverProducts.length]);

  // Load recommendations
  useEffect(() => {
    if (active === "Recommendations" && recProducts.length === 0) {
      let ignore = false;
      fetchRecommendations()
        .then((data) => {
          if (!ignore) setRecProducts(data);
        })
        .catch(() => {})
        .finally(() => {
          if (!ignore) setRecLoading(false);
        });
      return () => {
        ignore = true;
      };
    }
  }, [active, recProducts.length]);

  // Load orders
  useEffect(() => {
    if (active === "Orders") {
      let ignore = false;
      fetchOrders(threadId)
        .then((data) => {
          if (!ignore) setOrders(data);
        })
        .catch(() => {})
        .finally(() => {
          if (!ignore) setOrdersLoading(false);
        });
      return () => {
        ignore = true;
      };
    }
  }, [active, threadId]);

  // ============================================================
  // Chat Handler
  // ============================================================

  const handleSendMessage = async () => {
    if (!query.trim() || thinking) return;

    const userMessage = query.trim();

    setMessages((prev) => [
      ...prev,
      { type: "user", text: userMessage },
    ]);

    setQuery("");
    setThinking(true);

    try {
      const data = await sendMessage(userMessage, threadId);

      setMessages((prev) => [
        ...prev,
        {
          type: "assistant",
          text: data.response,
          products: data.products || [],
        },
      ]);

      // Refresh cart in case the agent modified it
      refreshCart();
    } catch (error) {
      console.error("Shopora backend error:", error);

      const errorMessage =
        error.message && !error.message.includes("Failed to fetch")
          ? `Connection issue: ${error.message}. Please check that the FastAPI backend server is running.`
          : "I'm having trouble connecting to Shopora right now. Please make sure the FastAPI backend is running on port 8000 and try again.";

      setMessages((prev) => [
        ...prev,
        {
          type: "assistant",
          text: errorMessage,
          error: true,
          products: [],
        },
      ]);
    } finally {
      setThinking(false);
    }
  };

  // ============================================================
  // Product Actions
  // ============================================================

  const toggleSaved = (product) => {
    setSaved((prev) =>
      prev.some((item) => item.id === product.id)
        ? prev.filter((item) => item.id !== product.id)
        : [...prev, product]
    );
  };

  const addToCart = async (product) => {
    try {
      await addToCartAPI(product.id, threadId);
      await refreshCart();
    } catch {
      // Fallback: add to local state
      if (!cart.some((item) => item.product_id === product.id)) {
        setCart((prev) => [
          ...prev,
          {
            product_id: product.id,
            name: product.name,
            category: product.category,
            price: product.price,
            quantity: 1,
            subtotal: product.price,
            image: product.image,
          },
        ]);
      }
    }
  };

  const removeFromCart = async (productId) => {
    try {
      await removeFromCartAPI(productId, threadId);
      await refreshCart();
    } catch {
      setCart((prev) => prev.filter((item) => item.product_id !== productId));
    }
  };

  const updateQuantity = async (productId, quantity) => {
    if (quantity < 1) return;
    try {
      await updateCartQuantityAPI(productId, quantity, threadId);
      await refreshCart();
    } catch {
      setCart((prev) =>
        prev.map((item) =>
          item.product_id === productId
            ? { ...item, quantity, subtotal: item.price * quantity }
            : item
        )
      );
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      setUser(null);
    }
  };

  const handleCheckout = async () => {
    setCheckingOut(true);
    setCheckoutError("");
    try {
      await checkoutAPI();
      await refreshCart();
      setOrdersLoading(true);
      setActive("Orders");
    } catch (err) {
      setCheckoutError(err.message || "Checkout failed. Please try again.");
    } finally {
      setCheckingOut(false);
    }
  };

  const toggleCompare = (product) => {
    setCompareItems((prev) => {
      if (prev.some((item) => item.id === product.id)) {
        return prev.filter((item) => item.id !== product.id);
      }
      if (prev.length >= 4) return prev;
      return [...prev, product];
    });
  };

  // Discover search
  const handleDiscoverSearch = async () => {
    const q = discoverQuery.trim();
    if (!q) {
      setDiscoverLoading(true);
      fetchProducts()
        .then((data) => setDiscoverProducts(data))
        .catch(() => {})
        .finally(() => setDiscoverLoading(false));
      return;
    }

    setDiscoverLoading(true);
    try {
      const data = await searchProducts(q);
      setDiscoverProducts(data);
    } catch {
      // Keep existing products on error
    } finally {
      setDiscoverLoading(false);
    }
  };

  // Compute local cart total
  const computedCartTotal = cart.reduce(
    (sum, item) => sum + (item.price || 0) * (item.quantity || 1),
    0
  );
  const displayTotal = cartTotal > 0 ? cartTotal : computedCartTotal;

  // ============================================================
  // Render
  // ============================================================


  if (authLoading) {
  return (
    <div className="auth-loading">
      <div className="auth-loading-card">
        <span>AI SHOPPING AGENT</span>
        <h1>Shopora</h1>
        <p>Loading your session...</p>
      </div>
    </div>
  );
}

if (!user) {
  return <AuthScreen onAuthenticated={setUser} />;
}

  return (
    <div className={`app ${dark ? "dark" : ""}`}>
      {/* =========================================================
          SIDEBAR
      ========================================================= */}

      <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
        <div className="logo">
          <div className="logo-mark">
            <span>✦</span>
          </div>

          <div>
            <strong>shopora</strong>
            <small>AI shopping agent</small>
          </div>
        </div>

        <div className="workspace-switcher">
          <div className="workspace-avatar">H</div>

          <div>
            <strong>Personal Space</strong>
            <span>Shopping workspace</span>
          </div>

          <span className="chevron">⌄</span>
        </div>

        <div className="nav-section">
          <span className="nav-label">WORKSPACE</span>

          {[
            ["✦", "AI Shopper"],
            ["⌕", "Discover"],
            ["◇", "Recommendations"],
            ["♡", "Saved"],
            ["⇄", "Compare"],
          ].map(([icon, name]) => (
            <button
              key={name}
              className={`nav-item ${active === name ? "active" : ""}`}
              onClick={() => {
                setActive(name);
                setMobileNav(false);
              }}
            >
              <span className="nav-icon">{icon}</span>
              <span>{name}</span>

              {name === "Saved" && saved.length > 0 && (
                <b>{saved.length}</b>
              )}
              {name === "Compare" && compareItems.length > 0 && (
                <b>{compareItems.length}</b>
              )}
            </button>
          ))}
        </div>

        <div className="nav-section">
          <span className="nav-label">ORDERS</span>

          <button
            className={`nav-item ${active === "Orders" ? "active" : ""}`}
            onClick={() => {
              setActive("Orders");
              setMobileNav(false);
            }}
          >
            <span className="nav-icon">▣</span>
            <span>Orders</span>
          </button>

          <button
            className={`nav-item ${active === "Tracking" ? "active" : ""}`}
            onClick={() => {
              setActive("Tracking");
              setMobileNav(false);
            }}
          >
            <span className="nav-icon">⌁</span>
            <span>Track shipment</span>
          </button>
        </div>

        <div className="sidebar-bottom">
          <button
            className={`nav-item ${active === "Settings" ? "active" : ""}`}
            onClick={() => {
              setActive("Settings");
              setMobileNav(false);
            }}
          >
            <span className="nav-icon">⚙</span>
            <span>Settings</span>
          </button>

          <div className="profile">
            <div className="profile-avatar">H</div>

            <div>
              <strong>Hari Prasath</strong>
              <span>Personal account</span>
            </div>

            <span className="more">•••</span>
          </div>
        </div>
      </aside>

      {/* Mobile nav overlay */}
      {mobileNav && (
        <div
          className="nav-overlay"
          onClick={() => setMobileNav(false)}
        />
      )}

      {/* =========================================================
          MAIN
      ========================================================= */}

      <main className="main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="hamburger"
              onClick={() => setMobileNav((prev) => !prev)}
            >
              ☰
            </button>

            <div className="breadcrumbs">
              <span>Shopora</span>
              <span>/</span>
              <strong>{active}</strong>
            </div>
          </div>

          <div className="top-actions">
            {!backendOk && (
              <span className="backend-status offline">
                <i />
                Offline
              </span>
            )}

            <button
              className="top-button"
              onClick={() => setDark((prev) => !prev)}
              title="Toggle theme"
            >
              {dark ? "☀" : "☾"}
            </button>

            <button
              className="cart-top"
              onClick={() => setActive("Cart")}
            >
              <span>Bag</span>

              {cart.length > 0 && <b>{cart.length}</b>}
            </button>
          </div>
        </header>

        {/* ======================================================
            AI SHOPPER
        ====================================================== */}

        {active === "AI Shopper" && (
          <section className="ai-page">
            <div className="hero-copy">
              <div className="status">
                <span />
                SHOPORA INTELLIGENCE
              </div>

              <h1>
                Shopping decisions,
                <br />
                <em>made intelligent.</em>
              </h1>

              <p>
                Tell Shopora what you're looking for. Our AI understands your
                intent, evaluates the options and helps you make the right
                decision.
              </p>
            </div>

            <div className="ai-console">
              <div className="console-header">
                <div className="console-agent">
                  <div className="agent-symbol">✦</div>

                  <div>
                    <strong>Shopora Agent</strong>
                    <span>
                      {thinking ? "Working..." : "Ready to help"}
                    </span>
                  </div>
                </div>

                <span className="live">
                  <i />
                  LIVE
                </span>
              </div>

              <div className="conversation" ref={conversationRef}>
                {messages.length === 0 && (
                  <div className="welcome">
                    <div className="welcome-icon">✦</div>

                    <h2>What can I help you find?</h2>

                    <p>
                      Describe your needs naturally. You don't need to know
                      exactly what you're looking for.
                    </p>

                    <div className="prompt-examples">
                      {[
                        "Laptop for AI development under ₹80K",
                        "Best gaming mouse under ₹2K",
                        "Monitor for programming",
                      ].map((text) => (
                        <button
                          key={text}
                          onClick={() => setQuery(text)}
                        >
                          <span>↗</span>
                          {text}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {messages.map((message, index) => (
                  <div
                    className={`message ${message.type}`}
                    key={`${message.type}-${index}`}
                  >
                    {message.type === "assistant" && (
                      <div className="message-agent">✦</div>
                    )}

                    <div className="message-body">
                      <span className="message-author">
                        {message.type === "assistant" ? "SHOPORA" : "YOU"}
                      </span>

                      <p
                        className={
                          message.error ? "error-message" : ""
                        }
                      >
                        {message.text}
                      </p>

                      {/* Inline product cards from AI */}
                      {message.products && message.products.length > 0 && (
                        <div className="chat-products">
                          {message.products.map((product) => (
                            <ChatProductCard
                              key={product.id}
                              product={product}
                              saved={saved}
                              cart={cart}
                              toggleSaved={toggleSaved}
                              addToCart={addToCart}
                              setSelectedProduct={setSelectedProduct}
                              toggleCompare={toggleCompare}
                              compareItems={compareItems}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {thinking && (
                  <div className="message assistant">
                    <div className="message-agent thinking">✦</div>

                    <div className="thinking-panel">
                      <div className="thinking-head">
                        <strong>
                          Shopora is analyzing your request
                        </strong>

                        <div className="dots">
                          <i />
                          <i />
                          <i />
                        </div>
                      </div>

                      <div className="agent-activity">
                        <div className="complete">
                          <span>✓</span>
                          Understanding requirements
                        </div>

                        <div className="running">
                          <span />
                          Searching product catalog
                        </div>

                        <div className="running">
                          <span />
                          Evaluating best matches
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="composer">
                <div className="composer-icon">✦</div>

                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  placeholder="Tell Shopora what you're looking for..."
                  disabled={thinking}
                  rows={1}
                />

                <div className="composer-actions">
                  <button
                    className="voice"
                    type="button"
                    title="Voice input coming soon"
                    disabled
                  >
                    ◉
                  </button>

                  <button
                    className="send"
                    onClick={handleSendMessage}
                    disabled={!query.trim() || thinking}
                    title="Send message"
                  >
                    ↑
                  </button>
                </div>
              </div>

              <div className="composer-footer">
                <span>AI shopping agent</span>
                <span>Enter ↵ to send</span>
              </div>
            </div>
          </section>
        )}

        {/* ======================================================
            DISCOVER
        ====================================================== */}

        {active === "Discover" && (
          <section className="content-page">
            <PageHeader
              eyebrow="DISCOVER"
              title="Explore products"
              description="Search through products with natural language."
            />

            <div className="search-bar">
              <span>⌕</span>

              <input
                value={discoverQuery}
                onChange={(e) => setDiscoverQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleDiscoverSearch();
                }}
                placeholder="Search products, categories or describe what you need..."
              />

              <button onClick={handleDiscoverSearch}>
                {discoverLoading ? "..." : "Search"}
              </button>
            </div>

            {discoverLoading ? (
              <div className="loading-grid">
                {[1, 2, 3].map((i) => (
                  <div className="skeleton-card" key={i} />
                ))}
              </div>
            ) : discoverProducts.length === 0 ? (
              <Empty
                icon="⌕"
                title="No products found"
                text="Try a different search term or browse all products."
              />
            ) : (
              <div className="product-grid">
                {discoverProducts.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    saved={saved}
                    cart={cart}
                    toggleSaved={toggleSaved}
                    addToCart={addToCart}
                    setSelectedProduct={setSelectedProduct}
                    toggleCompare={toggleCompare}
                    compareItems={compareItems}
                  />
                ))}
              </div>
            )}
          </section>
        )}

        {/* ======================================================
            RECOMMENDATIONS
        ====================================================== */}

        {active === "Recommendations" && (
          <section className="content-page">
            <PageHeader
              eyebrow="AI CURATED"
              title="Recommendations"
              description="Products selected around your shopping intent."
            />

            {recProducts.length > 0 && (
              <div className="insight">
                <div className="insight-icon">✦</div>

                <div>
                  <strong>Shopora's recommendation</strong>

                  <p>
                    {recProducts[0].name} is currently the strongest overall
                    match with a {recProducts[0].match_score}% AI match score.
                    {recProducts[0].reason && ` ${recProducts[0].reason}`}
                  </p>
                </div>
              </div>
            )}

            {recLoading ? (
              <div className="loading-grid">
                {[1, 2, 3].map((i) => (
                  <div className="skeleton-card" key={i} />
                ))}
              </div>
            ) : (
              <div className="product-grid">
                {recProducts.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    saved={saved}
                    cart={cart}
                    toggleSaved={toggleSaved}
                    addToCart={addToCart}
                    setSelectedProduct={setSelectedProduct}
                    toggleCompare={toggleCompare}
                    compareItems={compareItems}
                  />
                ))}
              </div>
            )}
          </section>
        )}

        {/* ======================================================
            SAVED
        ====================================================== */}

        {active === "Saved" && (
          <section className="content-page">
            <PageHeader
              eyebrow="YOUR COLLECTION"
              title="Saved products"
              description="Keep interesting products here for later."
            />

            {saved.length === 0 ? (
              <Empty
                icon="♡"
                title="Nothing saved yet"
                text="Save products while you explore and they'll appear here."
              />
            ) : (
              <div className="product-grid">
                {saved.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    saved={saved}
                    cart={cart}
                    toggleSaved={toggleSaved}
                    addToCart={addToCart}
                    setSelectedProduct={setSelectedProduct}
                    toggleCompare={toggleCompare}
                    compareItems={compareItems}
                  />
                ))}
              </div>
            )}
          </section>
        )}

        {/* ======================================================
            COMPARE
        ====================================================== */}

        {active === "Compare" && (
          <section className="content-page">
            <PageHeader
              eyebrow="DECISION SUPPORT"
              title="Compare products"
              description="Understand the differences before you buy."
            />

            {compareItems.length < 2 ? (
              <Empty
                icon="⇄"
                title={compareItems.length === 0 ? "No products to compare" : "Add one more product"}
                text="Save products to compare from Discover or Recommendations. You need at least 2 products."
              />
            ) : (
              <div className="compare-box">
                <div className="compare-ai">
                  <div className="insight-icon">✦</div>

                  <div>
                    <strong>AI decision summary</strong>

                    <p>
                      {(() => {
                        const sorted = [...compareItems].sort(
                          (a, b) => (b.match_score || 0) - (a.match_score || 0)
                        );
                        const best = sorted[0];
                        const cheapest = [...compareItems].sort(
                          (a, b) => a.price - b.price
                        )[0];

                        if (best.id === cheapest.id) {
                          return `${best.name} is the best overall choice — highest match score and most affordable.`;
                        }
                        return `${best.name} is the strongest match at ${best.match_score}% score. ${cheapest.name} offers the best value at ${formatPrice(cheapest.price)}.`;
                      })()}
                    </p>
                  </div>
                </div>

                <div
                  className="compare-table"
                  style={{
                    gridTemplateColumns: `130px repeat(${compareItems.length}, 1fr)`,
                  }}
                >
                  <div className="compare-labels">
                    <strong>PRODUCT</strong>
                    <span>Price</span>
                    <span>Rating</span>
                    <span>AI Match</span>
                    <span>Category</span>
                    <span>Stock</span>
                    <span>Action</span>
                  </div>

                  {compareItems.map((product) => (
                    <div
                      className="compare-column"
                      key={product.id}
                    >
                      <div className="compare-product-head">
                        <img
                          src={product.image}
                          alt={product.name}
                        />
                        <strong>{product.name}</strong>
                      </div>

                      <span>{formatPrice(product.price)}</span>
                      <span>★ {product.rating}</span>
                      <span className="match">
                        <span>✦</span>
                        {product.match_score || "—"}%
                      </span>
                      <span>{product.category}</span>
                      <span>{product.stock > 0 ? `${product.stock} in stock` : "Out of stock"}</span>
                      <span>
                        <button
                          className="compare-remove"
                          onClick={() => toggleCompare(product)}
                        >
                          Remove
                        </button>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {/* ======================================================
            ORDERS
        ====================================================== */}

        {active === "Orders" && (
          <section className="content-page">
            <PageHeader
              eyebrow="ORDER HISTORY"
              title="Your orders"
              description="Track everything you've purchased through Shopora."
            />

            {ordersLoading ? (
              <div className="loading-grid">
                <div className="skeleton-card" />
                <div className="skeleton-card" />
              </div>
            ) : orders.length === 0 ? (
              <Empty
                icon="▣"
                title="No orders yet"
                text="Complete a purchase through the AI agent or cart to see your orders here."
              />
            ) : (
              <div className="orders">
                {orders.map((order) => (
                  <OrderCard
                    key={order.order_id}
                    order={order}
                    onTrack={() => {
                      setTrackingOrder(order);
                      setActive("Tracking");
                    }}
                  />
                ))}
              </div>
            )}
          </section>
        )}

        {/* ======================================================
            TRACKING
        ====================================================== */}

        {active === "Tracking" && (
          <section className="content-page tracking-page">
            {trackingOrder ? (
              <>
                <PageHeader
                  eyebrow="SHIPMENT"
                  title={`Order #${trackingOrder.order_id}`}
                  description={
                    trackingOrder.shipment
                      ? "Your package is currently on its way."
                      : `Current status: ${trackingOrder.status}`
                  }
                />

                <div className="tracking-card">
                  <div className="tracking-summary">
                    <div>
                      <span>ESTIMATED DELIVERY</span>
                      <strong>
                        {trackingOrder.shipment?.estimated_delivery
                          ? new Date(
                              trackingOrder.shipment.estimated_delivery
                            ).toLocaleDateString("en-IN", {
                              year: "numeric",
                              month: "long",
                              day: "numeric",
                            })
                          : "Pending"}
                      </strong>
                    </div>

                    <div className="status-pill">
                      <i />
                      {trackingOrder.status}
                    </div>
                  </div>

                  <div className="timeline">
                    {[
                      ["Order placed", true],
                      ["Confirmed", ["confirmed", "processing", "shipped", "delivered"].includes(trackingOrder.status)],
                      ["Processing", ["processing", "shipped", "delivered"].includes(trackingOrder.status)],
                      ["Shipped", ["shipped", "delivered"].includes(trackingOrder.status)],
                      ["Out for delivery", trackingOrder.status === "delivered"],
                      ["Delivered", trackingOrder.status === "delivered"],
                    ].map(([name, complete]) => (
                      <div
                        className={`timeline-item ${
                          complete ? "complete" : ""
                        }`}
                        key={name}
                      >
                        <div className="timeline-dot">
                          {complete ? "✓" : ""}
                        </div>

                        <div>
                          <strong>{name}</strong>
                        </div>
                      </div>
                    ))}
                  </div>

                  {trackingOrder.shipment && (
                    <div className="shipment-info">
                      <div>
                        <span>TRACKING NUMBER</span>
                        <strong>{trackingOrder.shipment.tracking_number}</strong>
                      </div>

                      <div>
                        <span>CARRIER</span>
                        <strong>{trackingOrder.shipment.carrier}</strong>
                      </div>

                      <div>
                        <span>CURRENT LOCATION</span>
                        <strong>{trackingOrder.shipment.current_location}</strong>
                      </div>

                      <div>
                        <span>LAST UPDATED</span>
                        <strong>
                          {new Date(trackingOrder.shipment.updated_at).toLocaleString("en-IN")}
                        </strong>
                      </div>
                    </div>
                  )}

                  {/* Order items */}
                  <div className="tracking-items">
                    <span className="tracking-items-label">ORDER ITEMS</span>
                    {trackingOrder.items.map((item) => (
                      <div className="tracking-item" key={item.product_id}>
                        <img src={item.image} alt={item.name} />
                        <div>
                          <strong>{item.name}</strong>
                          <span>
                            {item.quantity} × {formatPrice(item.price)}
                          </span>
                        </div>
                        <strong>{formatPrice(item.subtotal)}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <>
                <PageHeader
                  eyebrow="SHIPMENT"
                  title="Track shipment"
                  description="Select an order from the Orders page to track it."
                />

                <Empty
                  icon="⌁"
                  title="No order selected"
                  text="Go to Orders and click 'Track order' to see shipment details."
                />
              </>
            )}
          </section>
        )}

        {/* ======================================================
            CART
        ====================================================== */}

        {active === "Cart" && (
          <section className="content-page">
            <PageHeader
              eyebrow="SHOPPING BAG"
              title="Your cart"
              description="Review the products you've selected."
            />

            {cart.length === 0 ? (
              <Empty
                icon="□"
                title="Your cart is empty"
                text="Find something interesting and add it to your cart."
              />
            ) : (
              <div className="cart-layout">
                <div className="cart-list">
                  {cart.map((item) => (
                    <div className="cart-item" key={item.product_id}>
                      <img
                        src={item.image}
                        alt={item.name}
                      />

                      <div>
                        <span>{item.category}</span>
                        <h3>{item.name}</h3>
                        <strong>{formatPrice(item.price)}</strong>
                      </div>

                      <div className="cart-item-actions">
                        <div className="quantity-control">
                          <button
                            onClick={() =>
                              updateQuantity(item.product_id, item.quantity - 1)
                            }
                            disabled={item.quantity <= 1}
                          >
                            −
                          </button>
                          <span>{item.quantity}</span>
                          <button
                            onClick={() =>
                              updateQuantity(item.product_id, item.quantity + 1)
                            }
                          >
                            +
                          </button>
                        </div>

                        <button
                          className="remove-btn"
                          onClick={() => removeFromCart(item.product_id)}
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="cart-summary">
                  <span>ORDER SUMMARY</span>
                  <h2>Ready to checkout?</h2>

                  <div>
                    <span>Items</span>
                    <strong>
                      {cart.reduce((sum, item) => sum + item.quantity, 0)}
                    </strong>
                  </div>

                  <div>
                    <span>Delivery</span>
                    <strong className="green">Free</strong>
                  </div>

                  <hr />

                  <div className="cart-total">
                    <span>Total</span>
                    <strong>{formatPrice(displayTotal)}</strong>
                  </div>

                  {checkoutError && (
                    <p className="checkout-error">{checkoutError}</p>
                  )}

                  <button
                    className="checkout-button"
                    onClick={handleCheckout}
                    disabled={checkingOut}
                  >
                    {checkingOut ? "Placing order…" : "Continue to checkout →"}
                  </button>
                </div>
              </div>
            )}
          </section>
        )}

        {/* ======================================================
            SETTINGS
        ====================================================== */}

        {active === "Settings" && (
          <section className="content-page">
            <PageHeader
              eyebrow="PREFERENCES"
              title="Settings"
              description="Manage your Shopora workspace preferences."
            />

            <div className="settings-card">
              <div className="settings-row">
                <div>
                  <strong>Appearance</strong>
                  <span>Switch between light and dark mode.</span>
                </div>

                <button
                  className="settings-action"
                  onClick={() => setDark((prev) => !prev)}
                >
                  {dark ? "Light mode" : "Dark mode"}
                </button>
              </div>

              <div className="settings-row">
                <div>
                  <strong>AI Shopping Agent</strong>
                  <span>
                    Connected to your FastAPI and LangGraph backend.
                  </span>
                </div>

                <span className={`connection-status ${backendOk ? "" : "offline"}`}>
                  <i />
                  {backendOk ? "Connected" : "Offline"}
                </span>
              </div>

              <div className="settings-row">
                <div>
                  <strong>Session</strong>
                  <span>Current Shopora conversation thread.</span>
                </div>

                <code>{threadId}</code>
              </div>

              <div className="settings-row">
                <div>
                  <strong>Account</strong>
                  <span>{user?.name} · {user?.email}</span>
                </div>

                <button className="settings-action" onClick={handleLogout}>
                  Log out
                </button>
              </div>
            </div>
          </section>
        )}
      </main>

      {/* ========================================================
          PRODUCT DETAILS MODAL
      ======================================================== */}

      {selectedProduct && (
        <div
          className="modal"
          onClick={() => setSelectedProduct(null)}
        >
          <div
            className="product-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="close"
              onClick={() => setSelectedProduct(null)}
            >
              ×
            </button>

            <div className="modal-image">
              <img
                src={selectedProduct.image}
                alt={selectedProduct.name}
              />
            </div>

            <div className="modal-details">
              <span className="modal-category">
                {selectedProduct.category}
              </span>

              <h2>{selectedProduct.name}</h2>

              <div className="modal-rating">
                ★ {selectedProduct.rating}
              </div>

              <div className="modal-price">
                {formatPrice(selectedProduct.price)}
              </div>

              {selectedProduct.match_score && (
                <div className="modal-match">
                  <span>✦</span>
                  {selectedProduct.match_score}% AI Match
                </div>
              )}

              <p>
                {selectedProduct.description ||
                  "A carefully selected product that matches your shopping requirements across performance, value and reliability."}
              </p>

              {selectedProduct.specs && selectedProduct.specs.length > 0 && (
                <div className="specs">
                  {selectedProduct.specs.map((spec) => (
                    <span key={spec}>{spec}</span>
                  ))}
                </div>
              )}

              {selectedProduct.reason && (
                <div className="ai-note">
                  <span>✦</span>

                  <div>
                    <strong>Why Shopora recommends it</strong>
                    <p>{selectedProduct.reason}</p>
                  </div>
                </div>
              )}

              <div className="modal-actions">
                <button
                  className="modal-add"
                  onClick={() => {
                    addToCart(selectedProduct);
                    setSelectedProduct(null);
                  }}
                >
                  Add to cart · {formatPrice(selectedProduct.price)}
                </button>

                <button
                  className={`modal-save ${
                    saved.some((s) => s.id === selectedProduct.id)
                      ? "saved"
                      : ""
                  }`}
                  onClick={() => toggleSaved(selectedProduct)}
                >
                  {saved.some((s) => s.id === selectedProduct.id)
                    ? "♥ Saved"
                    : "♡ Save"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ================================================================
   CHAT PRODUCT CARD (inline in conversation)
================================================================ */

function ChatProductCard({
  product,
  saved,
  cart,
  toggleSaved,
  addToCart,
  setSelectedProduct,
  toggleCompare,
  compareItems,
}) {
  const isSaved = saved.some((item) => item.id === product.id);
  const inCart = cart.some((item) => item.product_id === product.id);
  const inCompare = compareItems.some((item) => item.id === product.id);

  return (
    <article className="chat-product-card">
      <div className="chat-product-image">
        <img src={product.image} alt={product.name} />

        <div className="match">
          <span>✦</span>
          {product.match_score}% match
        </div>
      </div>

      <div className="chat-product-info">
        <span className="category">{product.category}</span>
        <h3>{product.name}</h3>

        <div className="chat-product-meta">
          <strong className="price">{formatPrice(product.price)}</strong>
          <span className="rating">
            <span>★</span>
            {product.rating}
          </span>
        </div>

        {product.reason && (
          <div className="ai-reason">
            <span>✦</span>
            <div>
              <strong>AI recommendation</strong>
              <p>{product.reason}</p>
            </div>
          </div>
        )}

        <div className="chat-product-buttons">
          <button onClick={() => setSelectedProduct(product)}>
            Details
          </button>

          <button
            className={inCart ? "added" : ""}
            onClick={() => addToCart(product)}
          >
            {inCart ? "Added ✓" : "Add to cart"}
          </button>

          <button
            className={`icon-btn ${isSaved ? "saved" : ""}`}
            onClick={() => toggleSaved(product)}
            title={isSaved ? "Unsave" : "Save"}
          >
            {isSaved ? "♥" : "♡"}
          </button>

          <button
            className={`icon-btn ${inCompare ? "active" : ""}`}
            onClick={() => toggleCompare(product)}
            title={inCompare ? "Remove from compare" : "Add to compare"}
          >
            ⇄
          </button>
        </div>
      </div>
    </article>
  );
}

/* ================================================================
   PRODUCT CARD (grid)
================================================================ */

function ProductCard({
  product,
  saved,
  cart,
  toggleSaved,
  addToCart,
  setSelectedProduct,
  toggleCompare,
  compareItems,
}) {
  const isSaved = saved.some(
    (item) => item.id === product.id
  );

  const inCart = cart.some(
    (item) => item.product_id === product.id
  );

  const inCompare = compareItems.some(
    (item) => item.id === product.id
  );

  return (
    <article className="product-card">
      <div className="product-image">
        <img
          src={product.image}
          alt={product.name}
        />

        <button
          className={`save ${isSaved ? "saved" : ""}`}
          onClick={() => toggleSaved(product)}
          title={isSaved ? "Remove from saved" : "Save product"}
        >
          {isSaved ? "♥" : "♡"}
        </button>

        {product.match_score && (
          <div className="match">
            <span>✦</span>
            {product.match_score}% match
          </div>
        )}
      </div>

      <div className="product-info">
        <span className="category">
          {product.category}
        </span>

        <h3>{product.name}</h3>

        <div className="rating">
          <span>★</span>
          {product.rating}
        </div>

        <strong className="price">
          {formatPrice(product.price)}
        </strong>

        {product.reason && (
          <div className="ai-reason">
            <span>✦</span>

            <div>
              <strong>AI recommendation</strong>
              <p>{product.reason}</p>
            </div>
          </div>
        )}

        <div className="product-buttons">
          <button
            onClick={() => setSelectedProduct(product)}
          >
            Details
          </button>

          <button
            className={inCart ? "added" : ""}
            onClick={() => addToCart(product)}
          >
            {inCart ? "Added ✓" : "Add to cart"}
          </button>
        </div>

        <button
          className={`compare-btn ${inCompare ? "active" : ""}`}
          onClick={() => toggleCompare(product)}
        >
          {inCompare ? "✓ Comparing" : "⇄ Compare"}
        </button>
      </div>
    </article>
  );
}

/* ================================================================
   PAGE HEADER
================================================================ */

function PageHeader({
  eyebrow,
  title,
  description,
}) {
  return (
    <div className="page-header">
      <div>
        <span>{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
    </div>
  );
}

/* ================================================================
   EMPTY STATE
================================================================ */

function Empty({
  icon,
  title,
  text,
}) {
  return (
    <div className="empty">
      <div>{icon}</div>
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}

/* ================================================================
   ORDER CARD
================================================================ */

function OrderCard({ order, onTrack }) {
  const mainItem = order.items[0];

  return (
    <div className="order">
      <div className="order-top">
        <div>
          <span>ORDER</span>
          <strong>#{order.order_id}</strong>
        </div>

        <div>
          <span>ITEMS</span>
          <strong>
            {order.items.length === 1
              ? mainItem?.name
              : `${mainItem?.name} + ${order.items.length - 1} more`}
          </strong>
        </div>

        <div>
          <span>TOTAL</span>
          <strong>{formatPrice(order.total_amount)}</strong>
        </div>

        <div
          className={`order-status ${order.status.toLowerCase()}`}
        >
          {order.status}
        </div>
      </div>

      <div className="order-bottom">
        <span>
          {order.items.length} item{order.items.length > 1 ? "s" : ""}
        </span>

        <div>
          <button onClick={onTrack}>
            Track order
          </button>
        </div>
      </div>
    </div>
  );
}


function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault(); setError(""); setLoading(true);
    try {
      const user = mode === "login" ? await login(email, password) : await register(name, email, password);
      onAuthenticated(user);
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  }

  return (
    <div className="auth-screen">
      <form className="auth-card" onSubmit={submit}>
        <span>AI SHOPPING AGENT</span><h1>Welcome to Shopora</h1>
        <p>Your cart, orders and AI shopping history stay tied to your account.</p>
        {mode === "register" && <input placeholder="Full name" value={name} onChange={e => setName(e.target.value)} required minLength={2} />}
        <input
  type="email"
  placeholder="Email"
  value={email}
  onChange={e => setEmail(e.target.value)}
  required
/>

<input
  type="password"
  placeholder="Password"
  value={password}
  onChange={e => setPassword(e.target.value)}
  required
  minLength={8}
/>

        {error && <div className="auth-error">{error}</div>}
        <button type="submit" disabled={loading}>{loading ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
        <button type="button" className="secondary" onClick={() => setMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "Create a new account" : "I already have an account"}</button>
      </form>
    </div>
  );
}

export default App;
