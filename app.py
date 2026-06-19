"""
NurtureAI — Lead Magnet & Email Nurture Dashboard
Streamlit UI · Connected to n8n on Railway
Run:  streamlit run app.py
"""

import streamlit as st
import groq
import json
import random
import requests
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================================
# CONSTANTS
# ============================================================================

N8N_WEBHOOK_URL = "https://n8n-production-bd24.up.railway.app/webhook/lead-capture"
GROQ_API_KEY = "..."
DATABASE_PATH = "leads.db"

# =================================================================.==========
# DATABASE SETUP
# ============================================================================

def init_database():
    """Initialize SQLite database for leads"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT,
            email TEXT NOT NULL UNIQUE,
            company TEXT,
            source TEXT,
            lead_magnet TEXT,
            lead_score INTEGER DEFAULT 10,
            status TEXT DEFAULT 'New',
            segment TEXT DEFAULT 'new_subscriber',
            open_rate REAL DEFAULT 0,
            email_count INTEGER DEFAULT 0,
            created_at TIMESTAMP,
            last_activity TIMESTAMP,
            n8n_response TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def save_lead_to_db(lead_data: dict) -> bool:
    """Save lead to database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO leads 
            (id, first_name, last_name, email, company, source, lead_magnet, 
             lead_score, status, segment, open_rate, email_count, created_at, last_activity, n8n_response)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lead_data.get('id'),
            lead_data.get('first_name'),
            lead_data.get('last_name'),
            lead_data.get('email'),
            lead_data.get('company'),
            lead_data.get('source'),
            lead_data.get('lead_magnet'),
            lead_data.get('lead_score', 10),
            lead_data.get('status', 'New'),
            lead_data.get('segment', 'new_subscriber'),
            lead_data.get('open_rate', 0),
            lead_data.get('email_count', 0),
            lead_data.get('created_at'),
            lead_data.get('last_activity'),
            lead_data.get('n8n_response', '')
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving lead: {e}")
        return False
    finally:
        conn.close()

def get_all_leads() -> pd.DataFrame:
    """Get all leads from database"""
    conn = sqlite3.connect(DATABASE_PATH)
    query = "SELECT * FROM leads ORDER BY created_at DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_lead_stats() -> dict:
    """Get lead statistics"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM leads")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(lead_score) FROM leads WHERE lead_score > 0")
    avg_score = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'Hot'")
    hot = cursor.fetchone()[0]
    
    cursor.execute("SELECT source, COUNT(*) FROM leads GROUP BY source")
    sources = dict(cursor.fetchall())
    
    conn.close()
    
    return {
        'total': total,
        'avg_score': avg_score,
        'hot': hot,
        'sources': sources
    }

# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="NurtureAI — Lead Nurture Platform",
    page_icon="📬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database
init_database()

# ============================================================================
# CUSTOM CSS (same as before)
# ============================================================================

st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
    .block-container { padding: 1.5rem 2rem; }
    [data-testid="metric-container"] {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 1rem;
    }
    [data-testid="stSidebar"] { background: #0d1117; }
    [data-testid="stSidebar"] * { color: #e6edf3 !important; }
    .email-preview {
        background: white;
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 1.25rem 1.5rem;
        font-family: Georgia, serif;
        line-height: 1.8;
        font-size: 14px;
        color: #1a1a1a;
    }
    .email-preview .subject { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
    .email-preview .preview-text { color: #666; font-size: 13px; margin-bottom: 16px;
        border-bottom: 1px solid #eee; padding-bottom: 12px; }
    .email-preview .body { white-space: pre-wrap; }
    .email-preview .cta-btn {
        display: block; background: #1a1a1a; color: white !important;
        text-align: center; padding: 12px 24px; border-radius: 6px;
        margin: 20px auto; max-width: 280px; font-size: 14px; font-weight: 600;
        text-decoration: none;
    }
    .tag {
        display: inline-block; background: #e8f4fd; color: #0d6efd;
        font-size: 11px; padding: 3px 10px; border-radius: 20px; margin: 2px; font-weight: 500;
    }
    .tip-box {
        background: #f0f9ff; border-left: 3px solid #0d6efd;
        border-radius: 0 8px 8px 0; padding: 10px 14px; margin-top: 12px;
        font-size: 13px; color: #1a1a1a;
    }
    .seg-card {
        background: white; border: 1px solid #dee2e6;
        border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 10px;
    }
    .progress-bar-bg { background: #e9ecef; border-radius: 4px; height: 6px; margin-top: 8px; }
    .progress-bar-fill { height: 6px; border-radius: 4px; }
    .wf-step {
        background: white; border: 1px solid #dee2e6; border-radius: 8px;
        padding: 10px 16px; margin: 4px 0; font-size: 13px;
        display: flex; align-items: center; gap: 10px;
    }
    .wf-trigger { border-color: #198754; background: #f0fdf4; }
    .wf-condition { border-color: #fd7e14; background: #fff8f0; }
    .wf-arrow { text-align: center; color: #adb5bd; font-size: 18px; line-height: 1; margin: 2px 0; }
    .n8n-badge {
        display: inline-block; background: #ea4b71; color: white;
        font-size: 11px; padding: 2px 10px; border-radius: 20px; font-weight: 700;
    }
    h1, h2, h3 { font-weight: 600 !important; }
    .stTabs [data-baseweb="tab"] { font-size: 14px; font-weight: 500; }
    .lead-row { cursor: pointer; }
    .lead-row:hover { background: #f0f0f0; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SEGMENT DATA (for display only)
# ============================================================================

SEGMENTS = [
    {"name": "High Intent", "icon": "🔥", "open_rate": 61.4, "click_rate": 24.8,
     "trigger": "Viewed pricing 2×", "status": "Active", "color": "#198754", "score": 61},
    {"name": "Content Engagers", "icon": "📖", "open_rate": 48.2, "click_rate": 15.3,
     "trigger": "Opened 3+ emails", "status": "Active", "color": "#0d6efd", "score": 48},
    {"name": "New Subscribers", "icon": "👋", "open_rate": 55.8, "click_rate": 18.9,
     "trigger": "Joined last 7 days", "status": "Active", "color": "#198754", "score": 56},
    {"name": "Cold Leads", "icon": "❄️", "open_rate": 12.1, "click_rate": 2.4,
     "trigger": "No open in 30 days", "status": "At Risk", "color": "#fd7e14", "score": 12},
    {"name": "Cart Abandoners", "icon": "🛒", "open_rate": 39.5, "click_rate": 11.2,
     "trigger": "Abandoned checkout", "status": "Critical", "color": "#dc3545", "score": 40},
    {"name": "VIP Customers", "icon": "⭐", "open_rate": 73.2, "click_rate": 31.6,
     "trigger": "Purchased 2+ times", "status": "Active", "color": "#198754", "score": 73},
]

EMAIL_TYPES = {
    "welcome": "Welcome Email (Day 0) — deliver the lead magnet",
    "value1": "Value Email #1 (Day 2) — actionable tip",
    "value2": "Value Email #2 (Day 5) — pain point deep dive",
    "casestudy": "Case Study Email (Day 8) — success story",
    "offer": "Soft Offer (Day 12) — introduce product",
    "hardoffer": "Hard Offer (Day 15) — direct CTA",
    "reeng": "Re-engagement (Day 30) — win back subscribers",
}

TONES = {
    "professional": "Professional — authoritative, data-driven",
    "friendly": "Friendly — warm, conversational",
    "urgent": "Urgent — scarcity, immediate action",
    "story": "Story-driven — narrative, relatable",
    "edu": "Educational — teach first, sell second",
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def test_n8n_connection() -> dict:
    """Test if n8n webhook is reachable"""
    test_payload = {
        "fname": "Test",
        "lname": "User",
        "email": f"test_{int(datetime.now().timestamp())}@example.com",
        "lead_source": "test",
        "Lead_magnet": "test",
        "company": "Test Company"
    }
    
    try:
        resp = requests.post(N8N_WEBHOOK_URL, json=test_payload, timeout=10, 
                            headers={"Content-Type": "application/json"})
        return {"ok": resp.status_code in (200, 201), "status": resp.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def submit_lead_to_n8n(first_name: str, last_name: str, email: str, 
                       lead_source: str, lead_magnet: str, company: str = "") -> dict:
    """Submit lead data to n8n webhook and save to database"""
    
    # Create lead ID
    lead_id = hashlib.md5(f"{email}_{datetime.now().isoformat()}".encode()).hexdigest()[:12]
    
    payload = {
        "fname": first_name.strip(),
        "lname": last_name.strip(),
        "email": email.strip().lower(),
        "lead_source": lead_source.lower(),
        "Lead_magnet": lead_magnet,
        "company": company.strip() if company else ""
    }
    
    try:
        resp = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=15,
                            headers={"Content-Type": "application/json"})
        
        try:
            response_body = resp.json()
        except:
            response_body = resp.text
        
        # Save to database
        lead_data = {
            'id': lead_id,
            'first_name': first_name.strip(),
            'last_name': last_name.strip(),
            'email': email.strip().lower(),
            'company': company.strip() if company else '',
            'source': lead_source.lower(),
            'lead_magnet': lead_magnet,
            'lead_score': 10,
            'status': 'New',
            'segment': 'new_subscriber',
            'open_rate': 0,
            'email_count': 0,
            'created_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat(),
            'n8n_response': json.dumps(response_body) if isinstance(response_body, dict) else str(response_body)
        }
        save_lead_to_db(lead_data)
        
        return {
            "ok": resp.status_code in (200, 201), 
            "status": resp.status_code, 
            "body": response_body,
            "lead_id": lead_id
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def generate_email_with_groq(topic: str, audience: str, email_type: str, tone: str, 
                              personalization: str, include_ps: bool, include_cta: bool) -> dict:
    """Generate email content using Groq API"""
    
    client = groq.Groq(api_key=GROQ_API_KEY)
    
    prompt = f"""Write a nurture email for:
- Lead Magnet: {topic}
- Audience: {audience}
- Email Type: {email_type}
- Tone: {tone}
- Personalization: {personalization}
- Include P.S.: {include_ps}
- Include CTA: {include_cta}

Return ONLY valid JSON (no markdown, no backticks):
{{
  "subject_line": "under 50 chars",
  "preview_text": "under 85 chars",
  "email_body": "200-280 words, use {personalization} in greeting, \\n\\n for paragraphs",
  "cta_text": "4-7 word action CTA",
  "behavioral_tags": ["tag1", "tag2", "tag3", "tag4"],
  "best_send_time": "e.g. Tuesday 10AM",
  "personalization_tip": "one specific suggestion",
  "estimated_open_rate": "e.g. 45-55%"
}}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert email marketing copywriter. Respond ONLY with valid JSON — no markdown, no explanation."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500,
        )
        
        raw_response = response.choices[0].message.content.strip()
        
        if raw_response.startswith("```json"):
            raw_response = raw_response[7:]
        if raw_response.startswith("```"):
            raw_response = raw_response[3:]
        if raw_response.endswith("```"):
            raw_response = raw_response[:-3]
        
        result = json.loads(raw_response.strip())
        return {"success": True, "data": result}
        
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parsing error: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================================================
# SIDEBAR
# ============================================================================

with st.sidebar:
    st.markdown("# 📬 NurtureAI")
    st.markdown("*Lead Magnet & Email Nurture Platform*")
    st.markdown("---")
    
    page = st.radio(
        "Navigation",
        ["📊 Dashboard", "✉️ AI Email Writer", "👥 Audience Segments", 
         "⚙️ Workflow Builder", "🎯 Lead Capture", "📋 Leads Table"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    
    st.markdown("### 🔗 n8n Workflow")
    st.markdown('<span class="n8n-badge">● LIVE on Railway</span>', unsafe_allow_html=True)
    st.code(N8N_WEBHOOK_URL, language="text")
    
    if st.button("🔌 Test Connection", use_container_width=True):
        with st.spinner("Testing..."):
            result = test_n8n_connection()
        if result.get("ok"):
            st.success(f"✅ Connected (HTTP {result['status']})")
        else:
            st.error(f"❌ {result.get('error', 'Connection failed')}")
    
    st.markdown("---")
    st.markdown("### 🤖 AI Model")
    st.info("✅ Groq Llama 3.3 70B\n*Ready to generate emails*")
    
    # Show lead count
    stats = get_lead_stats()
    st.markdown("---")
    st.markdown("### 📊 Database Stats")
    st.metric("Total Leads", stats['total'])
    
    st.markdown("---")
    st.caption("Semester Project · NurtureAI v1.0")
    st.caption("Streamlit + n8n + Groq AI")

# ============================================================================
# PAGE: DASHBOARD (with real data)
# ============================================================================

if page == "📊 Dashboard":
    st.title("📊 Analytics Dashboard")
    st.caption("Real-time conversion, engagement & revenue metrics")
    
    stats = get_lead_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Leads", stats['total'], help="All-time leads")
    col2.metric("Avg Lead Score", f"{stats['avg_score']:.0f}", help="Average engagement score")
    col3.metric("Conversion Rate", "8.7%", "-0.9%", delta_color="inverse")
    col4.metric("Hot Leads", stats['hot'], help="High-intent leads")
    
    st.markdown("---")
    
    # Lead acquisition chart (from real data)
    st.subheader("Lead Acquisition")
    
    df = get_all_leads()
    if not df.empty:
        df['created_date'] = pd.to_datetime(df['created_at']).dt.date
        daily_leads = df.groupby('created_date').size().reset_index(name='count')
        daily_leads = daily_leads.sort_values('created_date').tail(30)
        
        if not daily_leads.empty:
            st.line_chart(daily_leads.set_index('created_date'), color="#198754", height=250)
        else:
            st.info("No lead data yet. Submit some leads to see charts!")
    else:
        st.info("No leads yet. Go to Lead Capture tab to add some!")
    
    # Source distribution
    st.subheader("Lead Sources")
    if stats['sources']:
        source_df = pd.DataFrame(list(stats['sources'].items()), columns=['Source', 'Leads'])
        st.bar_chart(source_df.set_index('Source'), height=250, color="#0d6efd")
    else:
        st.info("No source data yet")
    
    # Recent activity from real leads
    st.markdown("---")
    st.subheader("Recent Activity")
    
    if not df.empty:
        recent = df.head(10)
        for _, lead in recent.iterrows():
            time_ago = datetime.now() - datetime.fromisoformat(lead['created_at'])
            if time_ago.days > 0:
                time_str = f"{time_ago.days}d ago"
            elif time_ago.seconds > 3600:
                time_str = f"{time_ago.seconds // 3600}h ago"
            else:
                time_str = f"{time_ago.seconds // 60}m ago"
            
            st.markdown(f"- {time_str}: New lead **{lead['first_name']} {lead['last_name']}** from {lead['source']} (Score: {lead['lead_score']})")
    else:
        st.info("No activity yet")

# ============================================================================
# PAGE: AI EMAIL WRITER (same as before, with updated model)
# ============================================================================

elif page == "✉️ AI Email Writer":
    st.title("✉️ AI Email Writer")
    st.caption("Generate professional nurture emails using Groq AI (Llama 3.3 70B)")
    
    if "email_generated" not in st.session_state:
        st.session_state.email_generated = False
    
    col_form, col_preview = st.columns([1, 1], gap="large")
    
    with col_form:
        st.markdown("### Campaign Setup")
        
        topic = st.text_input("Lead Magnet Topic *", 
                              placeholder="e.g., Free SEO Checklist, 30-Day Fitness Plan")
        audience = st.text_input("Target Audience *", 
                                 placeholder="e.g., SaaS founders, small business owners")
        
        email_type = st.selectbox("Email Type", list(EMAIL_TYPES.keys()),
                                  format_func=lambda x: EMAIL_TYPES[x].split(" — ")[0])
        
        tone = st.selectbox("Tone & Voice", list(TONES.keys()),
                            format_func=lambda x: x.title())
        
        personalization = st.selectbox("Personalization Variable",
                                       ["first_name", "company_name", "industry", "city"])
        
        col_ps, col_cta = st.columns(2)
        with col_ps:
            include_ps = st.checkbox("Include P.S. line", value=True)
        with col_cta:
            include_cta = st.checkbox("Include CTA button", value=True)
        
        st.markdown("---")
        
        if st.button("🚀 Generate Email", type="primary", use_container_width=True):
            if not topic or not audience:
                st.error("Please fill in both Topic and Audience")
            else:
                with st.spinner("✨ Writing your email with Groq AI..."):
                    result = generate_email_with_groq(
                        topic=topic,
                        audience=audience,
                        email_type=EMAIL_TYPES[email_type],
                        tone=TONES[tone],
                        personalization=personalization,
                        include_ps=include_ps,
                        include_cta=include_cta
                    )
                    
                    if result["success"]:
                        st.session_state.last_email = result["data"]
                        st.session_state.email_generated = True
                        st.success("✅ Email generated successfully!")
                    else:
                        st.error(f"❌ {result.get('error', 'Generation failed')}")
    
    with col_preview:
        st.markdown("### Preview")
        
        if st.session_state.email_generated and "last_email" in st.session_state:
            email = st.session_state.last_email
            
            cta_html = f'<a href="#" class="cta-btn">{email.get("cta_text", "Learn More")} →</a>' if include_cta else ""
            
            st.markdown(f"""
            <div class="email-preview">
                <div class="subject">📧 {email.get('subject_line', 'No subject')}</div>
                <div class="preview-text">👁 {email.get('preview_text', 'No preview')}</div>
                <div class="body">{email.get('email_body', '').replace(chr(10), '<br>')}</div>
                {cta_html}
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("**Behavioral Tags**")
            tags = email.get("behavioral_tags", [])
            tags_html = " ".join(f'<span class="tag">{tag}</span>' for tag in tags)
            st.markdown(tags_html, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            col1.info(f"🕐 Best send: **{email.get('best_send_time', '—')}**")
            col2.success(f"📈 Est. open rate: **{email.get('estimated_open_rate', '—')}**")
            
            st.markdown(f"""
            <div class="tip-box">
                💡 <strong>Personalization tip:</strong> {email.get('personalization_tip', '—')}
            </div>
            """, unsafe_allow_html=True)
            
            st.download_button(
                "💾 Download Email JSON",
                data=json.dumps(email, indent=2),
                file_name=f"email_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
            )
        else:
            st.info("👈 Fill out the form and click 'Generate Email'")

# ============================================================================
# PAGE: AUDIENCE SEGMENTS (with real counts)
# ============================================================================

# ============================================================================
# PAGE: AUDIENCE SEGMENTS (WITH REAL DATA)
# ============================================================================

elif page == "👥 Audience Segments":
    st.title("👥 Audience Segments")
    st.caption("Behavioral segmentation based on REAL lead data from your database")
    
    # Get real data from database
    df = get_all_leads()
    stats = get_lead_stats()
    
    if df.empty:
        st.warning("📭 No leads in database yet. Submit some leads to see real segment data!")
        
        with st.expander("ℹ️ How to get real data"):
            st.markdown("""
            1. Go to **Lead Capture** tab
            2. Submit 5-10 test leads
            3. Return here to see real segmentation!
            """)
    else:
        # Calculate REAL segment data from database
        total_leads = len(df)
        
        # High Intent Leads (score >= 70)
        high_intent_df = df[df['lead_score'] >= 70]
        high_intent_count = len(high_intent_df)
        high_intent_open_rate = high_intent_df['open_rate'].mean() if not high_intent_df.empty else 0
        high_intent_click_rate = high_intent_df['click_rate'].mean() if not high_intent_df.empty else 0
        
        # Content Engagers (opened 3+ emails)
        content_engagers_df = df[df['email_count'] >= 3]
        content_engagers_count = len(content_engagers_df)
        content_engagers_open_rate = content_engagers_df['open_rate'].mean() if not content_engagers_df.empty else 0
        content_engagers_click_rate = content_engagers_df['click_rate'].mean() if not content_engagers_df.empty else 0
        
        # New Subscribers (last 7 days)
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        new_subscribers_df = df[df['created_at'] > week_ago]
        new_subscribers_count = len(new_subscribers_df)
        new_subscribers_open_rate = new_subscribers_df['open_rate'].mean() if not new_subscribers_df.empty else 0
        
        # Cold Leads (no opens, low score)
        cold_leads_df = df[(df['open_rate'] == 0) | (df['lead_score'] < 20)]
        cold_leads_count = len(cold_leads_df)
        
        # VIP Customers (high score + high opens)
        vip_df = df[(df['lead_score'] >= 80) & (df['open_rate'] >= 50)]
        vip_count = len(vip_df)
        vip_open_rate = vip_df['open_rate'].mean() if not vip_df.empty else 0
        vip_click_rate = vip_df['click_rate'].mean() if not vip_df.empty else 0
        
        # Cart Abandoners (based on source or behavior - estimate from data)
        cart_abandoners_df = df[df['source'] == 'paid']  # Example logic
        cart_abandoners_count = len(cart_abandoners_df)
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Leads in DB", total_leads)
        col2.metric("Active Segments", "6")
        col3.metric("Segmented Leads", total_leads)
        
        # Find best performing segment
        segment_scores = {
            'VIP': vip_open_rate,
            'High Intent': high_intent_open_rate,
            'Content Engagers': content_engagers_open_rate,
            'New Subscribers': new_subscribers_open_rate
        }
        best_segment = max(segment_scores, key=segment_scores.get) if any(segment_scores.values()) else "None"
        col4.metric("Best Performing", f"{best_segment} ({max(segment_scores.values()):.1f}% open)" if segment_scores.values() else "No data")
        
        st.markdown("---")
        
        # Display REAL segments in cards
        segments_real = [
            {
                "name": "High Intent",
                "icon": "🔥",
                "count": high_intent_count,
                "open_rate": high_intent_open_rate,
                "click_rate": high_intent_click_rate,
                "trigger": f"Score ≥ 70 ({high_intent_count} leads)",
                "status": "Active" if high_intent_count > 0 else "No Data",
                "color": "#198754",
                "score": int(high_intent_open_rate) if high_intent_open_rate > 0 else 61
            },
            {
                "name": "Content Engagers",
                "icon": "📖",
                "count": content_engagers_count,
                "open_rate": content_engagers_open_rate,
                "click_rate": content_engagers_click_rate,
                "trigger": f"Opened 3+ emails ({content_engagers_count} leads)",
                "status": "Active" if content_engagers_count > 0 else "No Data",
                "color": "#0d6efd",
                "score": int(content_engagers_open_rate) if content_engagers_open_rate > 0 else 48
            },
            {
                "name": "New Subscribers",
                "icon": "👋",
                "count": new_subscribers_count,
                "open_rate": new_subscribers_open_rate,
                "click_rate": 0,  # New subscribers haven't clicked yet
                "trigger": f"Joined last 7 days ({new_subscribers_count} leads)",
                "status": "Active" if new_subscribers_count > 0 else "No Data",
                "color": "#198754",
                "score": int(new_subscribers_open_rate) if new_subscribers_open_rate > 0 else 56
            },
            {
                "name": "Cold Leads",
                "icon": "❄️",
                "count": cold_leads_count,
                "open_rate": 0,
                "click_rate": 0,
                "trigger": f"No engagement ({cold_leads_count} leads)",
                "status": "At Risk" if cold_leads_count > 0 else "No Data",
                "color": "#fd7e14",
                "score": 12
            },
            {
                "name": "Cart Abandoners",
                "icon": "🛒",
                "count": cart_abandoners_count,
                "open_rate": 0,
                "click_rate": 0,
                "trigger": "Abandoned checkout",
                "status": "Critical" if cart_abandoners_count > 0 else "No Data",
                "color": "#dc3545",
                "score": 40
            },
            {
                "name": "VIP Customers",
                "icon": "⭐",
                "count": vip_count,
                "open_rate": vip_open_rate,
                "click_rate": vip_click_rate,
                "trigger": f"Score ≥ 80 & 50%+ open ({vip_count} leads)",
                "status": "Active" if vip_count > 0 else "No Data",
                "color": "#198754",
                "score": int(vip_open_rate) if vip_open_rate > 0 else 73
            },
        ]
        
        # Display segments in 2-column grid
        for i in range(0, len(segments_real), 2):
            cols = st.columns(2, gap="medium")
            for j, col in enumerate(cols):
                if i + j < len(segments_real):
                    seg = segments_real[i + j]
                    status_color = {"Active": "#198754", "At Risk": "#fd7e14", "Critical": "#dc3545", "No Data": "#6c757d"}.get(seg["status"], "#6c757d")
                    
                    with col:
                        st.markdown(f"""
                        <div class="seg-card">
                            <div style="display:flex;justify-content:space-between;margin-bottom:10px">
                                <span style="font-size:15px;font-weight:600">{seg['icon']} {seg['name']}</span>
                                <span style="font-size:11px;background:{status_color}22;color:{status_color};padding:2px 10px;border-radius:20px">{seg['status']}</span>
                            </div>
                            <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:13px;margin-bottom:10px">
                                <div>📊 Leads: <strong>{seg['count']}</strong></div>
                                <div>📧 Open: <strong>{seg['open_rate']:.1f}%</strong></div>
                                <div>👆 Click: <strong>{seg['click_rate']:.1f}%</strong></div>
                                <div>🎯 Score: <strong>{seg['score']}</strong></div>
                            </div>
                            <div class="progress-bar-bg">
                                <div class="progress-bar-fill" style="width:{seg['score']}%;background:{seg['color']}"></div>
                            </div>
                            <div style="font-size:11px;color:#6c757d;margin-top:8px">⚡ {seg['trigger']}</div>
                        </div>
                        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Show real lead distribution chart
        st.subheader("📊 Real Lead Distribution")
        
        dist_data = pd.DataFrame({
            'Segment': ['High Intent', 'Content Engagers', 'New Subscribers', 'Cold Leads', 'VIP'],
            'Leads': [high_intent_count, content_engagers_count, new_subscribers_count, cold_leads_count, vip_count]
        })
        
        st.bar_chart(dist_data.set_index('Segment'), height=300, color="#0d6efd")
        
        # Show recent leads in each segment
        with st.expander("🔍 View leads by segment"):
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔥 High Intent", "📖 Content Engagers", "👋 New Subscribers", "❄️ Cold Leads", "⭐ VIP"])
            
            with tab1:
                if not high_intent_df.empty:
                    st.dataframe(high_intent_df[['first_name', 'last_name', 'email', 'lead_score', 'open_rate']].head(10))
                else:
                    st.info("No leads in this segment yet")
            
            with tab2:
                if not content_engagers_df.empty:
                    st.dataframe(content_engagers_df[['first_name', 'last_name', 'email', 'email_count', 'open_rate']].head(10))
                else:
                    st.info("No leads in this segment yet")
            
            with tab3:
                if not new_subscribers_df.empty:
                    st.dataframe(new_subscribers_df[['first_name', 'last_name', 'email', 'created_at']].head(10))
                else:
                    st.info("No leads in this segment yet")
            
            with tab4:
                if not cold_leads_df.empty:
                    st.dataframe(cold_leads_df[['first_name', 'last_name', 'email', 'lead_score', 'open_rate']].head(10))
                else:
                    st.info("No leads in this segment yet")
            
            with tab5:
                if not vip_df.empty:
                    st.dataframe(vip_df[['first_name', 'last_name', 'email', 'lead_score', 'open_rate', 'click_rate']].head(10))
                else:
                    st.info("No leads in this segment yet")

# ============================================================================
# PAGE: WORKFLOW BUILDER
# ============================================================================

elif page == "⚙️ Workflow Builder":
    st.title("⚙️ Automation Workflow")
    st.caption("15-day behavioral nurture sequence running on n8n")
    
    col_info, col_badge = st.columns([3, 1])
    with col_info:
        st.markdown("**Lead Nurture Sequence — Behavioral Flow**")
        st.caption(f"Webhook: `{N8N_WEBHOOK_URL}`")
    with col_badge:
        st.markdown('<span class="n8n-badge">● Active</span>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    steps = [
        ("trigger", "🟢 TRIGGER", "Lead Magnet Downloaded", "Webhook receives opt-in data → Save to DB"),
        ("step", "📧 DAY 0", "Welcome Email", "Deliver lead magnet + warm intro"),
        ("condition", "⚡ DAY 2", "Email Open Check", "Opened? → Value email | Not opened? → Re-send"),
        ("step", "📧 DAY 3", "Value Email #1", "Actionable tip + engagement tracking"),
        ("step", "📧 DAY 5", "Value Email #2", "Pain point deep dive"),
        ("step", "📧 DAY 8", "Case Study", "Social proof + specific results"),
        ("step", "📧 DAY 12", "Soft Offer", "Introduce paid solution naturally"),
        ("condition", "⚡ DAY 15", "Lead Score Check", "Score ≥ 60? → Hot offer | < 60 → Nurture"),
        ("step", "📧 DAY 15", "Hard Offer / Nurture", "Conversion or relationship email"),
        ("step", "📧 DAY 30", "Re-engagement", "Win back cold subscribers"),
    ]
    
    for kind, icon, title, subtitle in steps:
        css_class = "wf-step"
        if kind == "trigger":
            css_class += " wf-trigger"
        elif kind == "condition":
            css_class += " wf-condition"
        
        st.markdown(f"""
        <div class="{css_class}">
            <div style="min-width:100px;font-size:11px;font-weight:700;color:#6c757d">{icon}</div>
            <div>
                <div style="font-weight:600">{title}</div>
                <div style="font-size:12px;color:#6c757d">{subtitle}</div>
            </div>
        </div>
        <div class="wf-arrow">↓</div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("Lead Scoring Logic")
    
    score_df = pd.DataFrame({
        "Action": ["Opened email", "Clicked link", "Read 4+ emails", "Visited pricing", "Downloaded bonus"],
        "Points": [10, 25, 15, 20, 10],
        "Description": ["Per email opened", "Per link clicked", "Loyalty bonus", "High intent signal", "Content engagement"],
    })
    st.dataframe(score_df, use_container_width=True, hide_index=True)

# ============================================================================
# PAGE: LEAD CAPTURE
# ============================================================================

elif page == "🎯 Lead Capture":
    st.title("🎯 Lead Capture")
    st.caption("Collect leads and trigger the n8n workflow")
    
    tab1, tab2 = st.tabs(["📝 Submit Lead", "🎨 Page Builder"])
    
    with tab1:
        st.markdown(f"""
        <div style="background:#0d1117;color:#e6edf3;border-radius:8px;padding:12px;margin-bottom:16px">
            <span class="n8n-badge">● n8n Active</span>
            <code style="margin-left:10px;background:#ffffff15;padding:4px 8px;border-radius:4px">{N8N_WEBHOOK_URL}</code>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("lead_submit_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            fname = col1.text_input("First Name *", placeholder="John")
            lname = col2.text_input("Last Name", placeholder="Doe")
            
            email = st.text_input("Email Address *", placeholder="john@example.com")
            company = st.text_input("Company (optional)", placeholder="Acme Inc")
            
            col3, col4 = st.columns(2)
            source = col3.selectbox("Lead Source", ["Organic", "Social", "Paid", "Referral", "Event"])
            magnet = col4.selectbox("Lead Magnet", ["SEO Checklist", "Email Templates", "30-Day Plan", "Free Ebook", "Video Course"])
            
            submitted = st.form_submit_button("🚀 Submit Lead", type="primary", use_container_width=True)
        
        if submitted:
            if not fname or not email:
                st.error("⚠️ First Name and Email are required")
            else:
                with st.spinner("Sending to n8n..."):
                    result = submit_lead_to_n8n(fname, lname, email, source, magnet, company)
                
                if result.get("ok"):
                    st.success(f"✅ Lead **{fname} {lname}** submitted successfully!")
                    st.balloons()
                    
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Lead ID", result.get('lead_id', '—')[:8])
                    col2.metric("Source", source)
                    col3.metric("Status", f"HTTP {result['status']}")
                    
                    st.info("📧 n8n will: Validate → Enrich → HubSpot → Send Welcome Email")
                    st.caption("💾 Lead has been saved to local database")
                else:
                    st.error(f"❌ Failed: {result.get('error', 'Unknown error')}")
    
    with tab2:
        col_build, col_preview = st.columns(2)
        
        with col_build:
            st.markdown("### Form Configuration")
            headline = st.text_input("Headline", value="Get Your Free SEO Masterclass")
            subheadline = st.text_input("Subheadline", value="Rank #1 on Google in 90 days")
            button_text = st.text_input("Button Text", value="Download Free Guide →")
            
            st.markdown("### Fields to Collect")
            show_name = st.checkbox("First Name", value=True)
            show_email = st.checkbox("Email Address", value=True)
            show_company = st.checkbox("Company", value=False)
        
        with col_preview:
            st.markdown("### Live Preview")
            
            fields = ""
            if show_name:
                fields += '<input type="text" placeholder="First Name" style="width:100%;padding:10px;margin-bottom:8px;border:1px solid #ddd;border-radius:6px"><br>'
            if show_email:
                fields += '<input type="email" placeholder="Email Address" style="width:100%;padding:10px;margin-bottom:8px;border:1px solid #ddd;border-radius:6px"><br>'
            if show_company:
                fields += '<input type="text" placeholder="Company" style="width:100%;padding:10px;margin-bottom:8px;border:1px solid #ddd;border-radius:6px"><br>'
            
            st.markdown(f"""
            <div style="border:1px solid #dee2e6;border-radius:10px;overflow:hidden">
                <div style="background:#0d1117;padding:10px 15px">
                    <span style="color:white">FREE RESOURCE</span>
                </div>
                <div style="padding:24px;text-align:center">
                    <h3>{headline}</h3>
                    <p style="color:#666">{subheadline}</p>
                    <div style="background:#f8f9fa;padding:16px;border-radius:8px;text-align:left">
                        {fields}
                        <div style="background:#1a1a1a;color:white;text-align:center;padding:12px;border-radius:6px;cursor:pointer">
                            {button_text}
                        </div>
                    </div>
                    <p style="font-size:11px;color:#aaa;margin-top:12px">🔒 No spam. Unsubscribe anytime.</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ============================================================================
# PAGE: LEADS TABLE (NOW WITH REAL DATA!)
# ============================================================================

elif page == "📋 Leads Table":
    st.title("📋 Leads Database")
    st.caption("View, filter, and export lead data from your n8n workflow")
    
    # Refresh button
    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # Load real leads from database
    df = get_all_leads()
    
    if df.empty:
        st.info("📭 No leads yet. Go to the **Lead Capture** tab to submit your first lead!")
        
        # Show example
        with st.expander("ℹ️ How to add leads"):
            st.markdown("""
            1. Go to the **Lead Capture** tab
            2. Fill in the form with:
               - First Name
               - Email Address
               - Lead Source
               - Lead Magnet
            3. Click **Submit Lead**
            4. The lead will appear here automatically!
            """)
    else:
        # Filters
        st.markdown("### Filters")
        col1, col2, col3, col4 = st.columns(4)
        
        # Get unique values for filters
        sources = ['All'] + sorted(df['source'].dropna().unique().tolist())
        segments = ['All'] + sorted(df['segment'].dropna().unique().tolist())
        statuses = ['All'] + sorted(df['status'].dropna().unique().tolist())
        
        source_filter = col1.selectbox("Source", sources)
        segment_filter = col2.selectbox("Segment", segments)
        status_filter = col3.selectbox("Status", statuses)
        
        # Search
        search = col4.text_input("🔍 Search", placeholder="Name or email")
        
        # Apply filters
        filtered_df = df.copy()
        
        if source_filter != 'All':
            filtered_df = filtered_df[filtered_df['source'] == source_filter]
        if segment_filter != 'All':
            filtered_df = filtered_df[filtered_df['segment'] == segment_filter]
        if status_filter != 'All':
            filtered_df = filtered_df[filtered_df['status'] == status_filter]
        if search:
            filtered_df = filtered_df[
                filtered_df['first_name'].str.contains(search, case=False, na=False) |
                filtered_df['last_name'].str.contains(search, case=False, na=False) |
                filtered_df['email'].str.contains(search, case=False, na=False)
            ]
        
        # Metrics
        st.markdown("### Statistics")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Leads", len(filtered_df))
        col2.metric("Avg Score", f"{filtered_df['lead_score'].mean():.0f}" if not filtered_df.empty else "0")
        col3.metric("Total Sources", filtered_df['source'].nunique() if not filtered_df.empty else "0")
        col4.metric("Last 7 Days", len(filtered_df[filtered_df['created_at'] > (datetime.now() - timedelta(days=7)).isoformat()]) if not filtered_df.empty else "0")
        
        # Display table
        st.markdown("### Lead List")
        
        if not filtered_df.empty:
            # Prepare display dataframe
            display_df = filtered_df[[
                'first_name', 'last_name', 'email', 'source', 
                'lead_magnet', 'lead_score', 'status', 'created_at'
            ]].copy()
            
            display_df.columns = ['First Name', 'Last Name', 'Email', 'Source', 'Lead Magnet', 'Score', 'Status', 'Created']
            display_df['Created'] = pd.to_datetime(display_df['Created']).dt.strftime('%Y-%m-%d %H:%M')
            
            # Color code status
            def color_status(val):
                if val == 'Hot':
                    return 'color: #dc3545; font-weight: bold'
                elif val == 'Warm':
                    return 'color: #fd7e14'
                elif val == 'New':
                    return 'color: #198754'
                return ''
            
            st.dataframe(
                display_df,
                use_container_width=True,
                height=500,
                column_config={
                    "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
                    "Status": st.column_config.Column("Status", width="small"),
                }
            )
            
            # Export button
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Export to CSV",
                data=csv,
                file_name=f"leads_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.info("No leads match the selected filters")

# ============================================================================
# RUN THE APP
# ============================================================================

if __name__ == "__main__":
    pass