// --- Core Cart Operations ---
function addToCart(productId, qty = 1) {
    fetch('/api/cart/add', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ product_id: productId, quantity: qty })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            // Update cart bubble count in navbar if exists
            const bubble = document.getElementById('cart-count-bubble');
            if (bubble && data.cart_count !== undefined) {
                bubble.innerText = data.cart_count;
                bubble.style.display = 'inline-block';
            }
        } else {
            showToast(data.message, 'danger');
        }
    })
    .catch(err => {
        console.error("Cart error:", err);
        showToast("Error adding product to cart", "danger");
    });
}

function updateCartQty(productId, newQty) {
    fetch('/api/cart/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ product_id: productId, quantity: newQty })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            showToast(data.message, 'danger');
        }
    });
}

function removeCartItem(productId) {
    fetch('/api/cart/remove', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ product_id: productId })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            showToast(data.message, 'danger');
        }
    });
}

// --- Dynamic Point Slider logic on Checkout page ---
document.addEventListener('DOMContentLoaded', function() {
    const slider = document.getElementById('points-slider-input');
    if (slider) {
        const pointsValueDisplay = document.getElementById('slider-points-value');
        const discountDisplay = document.getElementById('slider-discount-value');
        const totalPayDisplay = document.getElementById('checkout-final-pay');
        const subtotal = parseFloat(document.getElementById('checkout-subtotal').dataset.subtotal);
        
        function updateCheckoutValues() {
            const pointsToUse = parseInt(slider.value);
            const discountRs = (pointsToUse * 0.1).toFixed(2);
            const finalPay = (subtotal - parseFloat(discountRs)).toFixed(2);
            
            pointsValueDisplay.innerText = pointsToUse;
            discountDisplay.innerText = `₹${discountRs}`;
            totalPayDisplay.innerText = `₹${Math.max(0, finalPay)}`;
        }
        
        slider.addEventListener('input', updateCheckoutValues);
        updateCheckoutValues(); // Initial trigger
    }
});

// --- Referral Code Generation and Copy ---
function generateReferral(productId) {
    const btn = document.getElementById(`ref-btn-${productId}`);
    if (btn) btn.disabled = true;
    
    fetch(`/api/generate_referral/${productId}`, {
        method: 'POST'
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            const container = document.getElementById(`ref-link-container-${productId}`);
            const input = document.getElementById(`ref-link-input-${productId}`);
            if (container && input) {
                input.value = data.ref_url;
                container.style.display = 'flex';
                showToast("Referral code generated! Click copy to share.", "success");
            }
        } else {
            showToast(data.error || "Please log in to generate referral links.", "danger");
            if (btn) btn.disabled = false;
        }
    })
    .catch(err => {
        console.error("Referral creation error:", err);
        showToast("Authentication required to refer products.", "danger");
        if (btn) btn.disabled = false;
    });
}

function copyReferralLink(productId) {
    let input = document.getElementById(`ref-link-input-${productId}`);
    if (!input) {
        input = document.getElementById(`ref-dash-input-${productId}`);
    }
    if (input) {
        input.select();
        input.setSelectionRange(0, 99999); // For mobile devices
        navigator.clipboard.writeText(input.value)
        .then(() => {
            showToast("Referral link copied to clipboard!", "success");
        })
        .catch(err => {
            console.error("Clipboard copy failed:", err);
            showToast("Failed to copy link automatically.", "warning");
        });
    }
}

// --- Dynamic Plotly Charts Rendering ---
document.addEventListener('DOMContentLoaded', function() {
    const salesChartDiv = document.getElementById('owner-sales-chart');
    const categoryChartDiv = document.getElementById('owner-category-chart');
    
    if (salesChartDiv && categoryChartDiv) {
        if (typeof Plotly === 'undefined') {
            const fallbackHTML = `
                <div style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:100%; padding:2rem; text-align:center; color:var(--text-muted);">
                    <i class="fa-solid fa-chart-pie" style="font-size:2.5rem; color:var(--accent); margin-bottom:0.75rem;"></i>
                    <h4 style="color:var(--text-main); font-family:var(--font-heading); margin-bottom:0.25rem;">Interactive Charts Unavailable</h4>
                    <p style="font-size:0.8rem; line-height:1.4;">Interactive visualizations require an active internet connection to load Plotly.js from the CDN. Standard data tables remain fully readable below.</p>
                </div>
            `;
            salesChartDiv.innerHTML = fallbackHTML;
            categoryChartDiv.innerHTML = fallbackHTML;
            return;
        }
        
        fetch('/api/owner/analytics-data')
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                salesChartDiv.innerHTML = `<div style="display:flex; justify-content:center; align-items:center; height:100%; color:var(--danger);">${data.error}</div>`;
                return;
            }
            try {
                // Plot 1: Revenue vs Profit per Product (Bar Chart)
                const trace1 = {
                    x: data.products.names,
                    y: data.products.revenues,
                    name: 'Gross Revenue (Rs)',
                    type: 'bar',
                    marker: { color: '#3b82f6', opacity: 0.8 }
                };
                const trace2 = {
                    x: data.products.names,
                    y: data.products.profits,
                    name: 'Net Profit (Rs)',
                    type: 'bar',
                    marker: { color: '#10b981', opacity: 0.85 }
                };
                const layout1 = {
                    title: { text: 'Sales Performance by Product', font: { color: '#f8fafc', family: 'Outfit' } },
                    barmode: 'group',
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    xaxis: { tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' },
                    yaxis: { title: 'Amount in Rs', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' },
                    legend: { font: { color: '#f8fafc' } },
                    margin: { t: 50, b: 50, l: 50, r: 20 }
                };
                salesChartDiv.innerHTML = ''; // Clear the spinner!
                Plotly.newPlot(salesChartDiv, [trace1, trace2], layout1, { responsive: true });
                
                // Plot 2: Category distribution (Pie Chart)
                const tracePie = {
                    labels: data.categories.names,
                    values: data.categories.revenues,
                    type: 'pie',
                    hole: 0.4,
                    marker: { colors: ['#10b981', '#3b82f6', '#f59e0b', '#8b5cf6', '#ec4899'] }
                };
                const layoutPie = {
                    title: { text: 'Sales by Product Category', font: { color: '#f8fafc', family: 'Outfit' } },
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    legend: { font: { color: '#f8fafc' } },
                    margin: { t: 50, b: 20, l: 20, r: 20 }
                };
                categoryChartDiv.innerHTML = ''; // Clear the spinner!
                Plotly.newPlot(categoryChartDiv, [tracePie], layoutPie, { responsive: true });
            } catch (err) {
                console.error("Plotly render error:", err);
                salesChartDiv.innerHTML = `<div style="display:flex; justify-content:center; align-items:center; height:100%; color:var(--danger); padding:2rem; text-align:center;">Error rendering chart.</div>`;
            }
        });
    }
    
    // 2. Check if Sysadmin Chart container is available
    const adminChartDiv = document.getElementById('admin-platform-chart');
    if (adminChartDiv) {
        if (typeof Plotly === 'undefined') {
            adminChartDiv.innerHTML = `
                <div style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:100%; padding:2rem; text-align:center; color:var(--text-muted);">
                    <i class="fa-solid fa-chart-pie" style="font-size:2.5rem; color:var(--accent); margin-bottom:0.75rem;"></i>
                    <h4 style="color:var(--text-main); font-family:var(--font-heading); margin-bottom:0.25rem;">Analytics Unavailable</h4>
                    <p style="font-size:0.8rem;">An active internet connection is required to load interactive graphs from Plotly CDN.</p>
                </div>
            `;
            return;
        }
        
        fetch('/api/admin/analytics-data')
        .then(res => res.json())
        .then(data => {
            if (data.error) return;
            try {
                // Platform Merchant Performance (Bar Chart)
                const trace = {
                    x: data.owners.names,
                    y: data.owners.sales,
                    type: 'bar',
                    marker: {
                        color: ['#8b5cf6', '#3b82f6', '#10b981', '#f59e0b', '#ec4899', '#f43f5e'], // Beautiful array of distinct colors!
                        opacity: 0.8,
                        line: { color: 'rgba(255,255,255,0.15)', width: 1 }
                    }
                };
                const layout = {
                    title: { text: 'Merchant Revenue Distribution', font: { color: '#f8fafc', family: 'Outfit' } },
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    xaxis: { tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' },
                    yaxis: { title: 'Total Sales (Rs)', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' },
                    margin: { t: 50, b: 50, l: 65, r: 20 }
                };
                adminChartDiv.innerHTML = ''; // Clear the spinner!
                Plotly.newPlot(adminChartDiv, [trace], layout, { responsive: true });
            } catch (err) {
                console.error("Plotly admin render error:", err);
                adminChartDiv.innerHTML = `<div style="display:flex; justify-content:center; align-items:center; height:100%; color:var(--danger);">Error rendering analytics.</div>`;
            }
        });
    }
});

// --- Dynamic Glass Toast Alert Utilities ---
function showToast(message, type = 'success') {
    // Check if alerts wrapper exists
    let wrapper = document.getElementById('dynamic-toast-wrapper');
    if (!wrapper) {
        wrapper = document.createElement('div');
        wrapper.id = 'dynamic-toast-wrapper';
        wrapper.style.position = 'fixed';
        wrapper.style.bottom = '2rem';
        wrapper.style.right = '2rem';
        wrapper.style.zIndex = '9999';
        wrapper.style.display = 'flex';
        wrapper.style.flexDirection = 'column';
        wrapper.style.gap = '0.75rem';
        document.body.appendChild(wrapper);
    }
    
    const toast = document.createElement('div');
    toast.className = `alert alert-${type}`;
    toast.style.boxShadow = '0 10px 30px rgba(0,0,0,0.5)';
    toast.style.backdropFilter = 'blur(10px)';
    toast.style.width = '320px';
    toast.style.margin = '0';
    
    // Icon
    let icon = '🔔';
    if (type === 'success') icon = '✅';
    if (type === 'danger') icon = '❌';
    if (type === 'warning') icon = '⚠️';
    
    toast.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.75rem;">
            <span>${icon}</span>
            <span>${message}</span>
        </div>
        <button onclick="this.parentElement.remove()" style="background:none; border:none; color:inherit; cursor:pointer; font-weight:700;">×</button>
    `;
    
    wrapper.appendChild(toast);
    
    // Auto-remove after 4 seconds
    setTimeout(() => {
        toast.style.transition = 'all 0.3s ease';
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(15px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// --- Modal Helper Functions ---
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
    }
}

// --- Custom Modal Delete Confirmation ---
function confirmDelete(deleteUrl) {
    const form = document.getElementById('delete-confirm-form');
    if (form) {
        form.action = deleteUrl;
        openModal('delete-confirm-modal');
    }
}
