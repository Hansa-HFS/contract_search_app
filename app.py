import streamlit as st
import requests
import pandas as pd
import re
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import quote_plus, urljoin, urlparse
import time
import json

# Service type taxonomy
SERVICE_TYPES = [
    'modernization', 'cloud', 'migration', 'cybersecurity', 'AI', 'data', 
    'infrastructure', 'application development', 'testing', 'BPO', 
    'managed services', 'consulting', 'network'
]

# Predefined IT contract sources (more reliable than search scraping)
CONTRACT_SOURCES = [
    "https://www.fbo.gov",
    "https://sam.gov",
    "https://www.contractsforaccess.com",
    "https://govtribe.com",
    "https://www.fedconnect.net",
    "https://www.govwin.com",
    "https://www.usaspending.gov",
    "https://www.fpds.gov"
]

def search_searx_instance(query, num_results=10):
    """Search using SearX metasearch engine"""
    searx_instances = [
        "https://searx.be",
        "https://searx.info",
        "https://searx.tiekoetter.com",
        "https://search.mdosch.de",
        "https://searx.org"
    ]
    
    for instance in searx_instances:
        try:
            search_url = f"{instance}/search"
            params = {
                'q': query,
                'format': 'json',
                'engines': 'google,bing,duckduckgo',
                'safesearch': '0'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(search_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                links = []
                
                if 'results' in data:
                    for result in data['results'][:num_results]:
                        if 'url' in result:
                            links.append(result['url'])
                
                if links:
                    return links
                    
        except Exception as e:
            continue
    
    return []

def search_direct_sources(query_terms):
    """Search directly from known contract announcement sources"""
    # For demo purposes, return some realistic test URLs
    # In production, you'd implement specific scrapers for each source
    test_urls = [
        "https://www.defense.gov/News/Contracts/",
        "https://www.gsa.gov/about-us/newsroom/news-releases",
        "https://www.nasa.gov/news/contracts-news/",
        "https://www.dhs.gov/news-releases/press-releases",
        "https://www.energy.gov/articles/department-energy-announces",
        "https://www.treasury.gov/press-center/press-releases/",
        "https://www.commerce.gov/news/press-releases",
        "https://www.hhs.gov/about/news/",
        "https://www.dot.gov/briefing-room/dot-announces",
        "https://www.va.gov/opa/pressrel/"
    ]
    
    return test_urls

def manual_url_input():
    """Allow users to manually input URLs"""
    st.subheader("📝 Manual URL Input (Recommended)")
    st.info("Since search engines block automated access, you can paste URLs directly from contract announcement sites.")
    
    urls_text = st.text_area(
        "Paste URLs (one per line):",
        placeholder="""https://www.defense.gov/News/Contracts/Contract/Article/3234567/
https://www.gsa.gov/about-us/newsroom/news-releases/2024/01/15/
https://sam.gov/opp/12345/view""",
        height=150
    )
    
    if urls_text:
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        return urls
    
    return []

def search_with_fallbacks(query, num_results=10):
    """Try multiple search methods with fallbacks"""
    st.write("🔍 Trying search methods...")
    
    # Method 1: Try SearX metasearch
    with st.spinner("Trying SearX metasearch engines..."):
        urls = search_searx_instance(query, num_results)
        if urls:
            st.success(f"✅ SearX found {len(urls)} results")
            return urls
        else:
            st.warning("❌ SearX instances unavailable")
    
    # Method 2: Direct sources
    with st.spinner("Checking direct contract sources..."):
        urls = search_direct_sources(query)
        if urls:
            st.info(f"📋 Using {len(urls)} known contract sources")
            return urls[:num_results]
    
    # Method 3: Return empty for manual input
    st.error("🚫 Automated search unavailable. Please use manual URL input below.")
    return []

def fetch_page_content(url):
    """Fetch and parse page content"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text content
        text = soup.get_text()
        
        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text.lower()
    except Exception as e:
        return None

def extract_contract_value(text):
    """Extract contract value in USD using regex"""
    # Patterns for currency values
    patterns = [
        r'\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*million',
        r'\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*m\b',
        r'\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*billion',
        r'\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*b\b',
        r'\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*thousand',
        r'\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*k\b',
        r'worth\s+\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)',
        r'value\s+of\s+\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)',
        r'contract\s+for\s+\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            value_str = matches[0].replace(',', '')
            value = float(value_str)
            
            if 'million' in pattern or ' m\\b' in pattern:
                return value
            elif 'billion' in pattern or ' b\\b' in pattern:
                return value * 1000
            elif 'thousand' in pattern or ' k\\b' in pattern:
                return value / 1000
            else:
                # Assume raw dollar amount, convert to millions
                return value / 1000000
    
    return None

def extract_duration(text):
    """Extract contract duration in months"""
    patterns = [
        r'(\d+)\s*year[s]?',
        r'(\d+)\s*month[s]?',
        r'duration\s+of\s+(\d+)\s*year[s]?',
        r'duration\s+of\s+(\d+)\s*month[s]?',
        r'term\s+of\s+(\d+)\s*year[s]?',
        r'term\s+of\s+(\d+)\s*month[s]?',
        r'(\d+)-year',
        r'(\d+)-month'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            duration = int(matches[0])
            if 'year' in pattern:
                return duration * 12
            else:
                return duration
    
    return None

def extract_organizations(text):
    """Extract organization names using regex patterns"""
    patterns = [
        r'\b([A-Z][a-zA-Z\s&]+(?:Inc\.?|Corp\.?|Corporation|Company|Co\.?|Ltd\.?|Limited|LLC|Group|Solutions|Systems|Technologies|Services))\b',
        r'\b([A-Z][a-zA-Z\s&]+ (?:Inc|Corp|Corporation|Company|Co|Ltd|Limited|LLC|Group|Solutions|Systems|Technologies|Services))\b'
    ]
    
    organizations = []
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            org = match.strip()
            if len(org) > 5 and org not in organizations:  # Filter out very short matches
                organizations.append(org)
    
    return organizations[:5]  # Return first 5 matches

def extract_service_type(text):
    """Extract service type from predefined taxonomy"""
    text_lower = text.lower()
    
    for service_type in SERVICE_TYPES:
        if service_type in text_lower:
            return service_type
    
    return None

def process_contract_page(url):
    """Process a single page and extract contract information"""
    content = fetch_page_content(url)
    
    if not content:
        return None
    
    # Filter for pages mentioning "contract"
    if 'contract' not in content:
        return None
    
    # Extract information
    contract_value = extract_contract_value(content)
    duration = extract_duration(content)
    organizations = extract_organizations(content)
    service_type = extract_service_type(content)
    
    # Assign vendor and client
    vendor = organizations[0] if len(organizations) > 0 else None
    client = organizations[1] if len(organizations) > 1 else None
    
    return {
        'URL': url,
        'Estimated Value (USD Millions)': contract_value,
        'Announcement Date': datetime.now().strftime('%Y-%m-%d'),
        'Vendor': vendor,
        'Client': client,
        'Contract Duration (Months)': duration,
        'Service Type': service_type
    }

def main():
    st.set_page_config(page_title="IT Contract Search", page_icon="🔍", layout="wide")
    
    st.title("🔍 IT Contract Search & Analysis")
    st.markdown("Search for publicly announced IT contracts and extract structured information.")
    
    # Show current limitations
    st.warning("⚠️ **Important**: Most search engines now block automated scraping. Choose from these options:")
    
    # Create tabs for different approaches
    tab1, tab2, tab3 = st.tabs(["🔗 Manual URLs", "🔍 Auto Search", "🔑 Google API"])
    
    with tab1:
        st.header("Manual URL Input (Most Reliable)")
        st.info("💡 **Recommended**: Copy URLs from government contract sites for best results")
        
        urls = manual_url_input()
        
        if urls:
            if st.button("🔍 Analyze Manual URLs", type="primary"):
                process_urls(urls)
        
        # Show helpful contract sources
        st.subheader("📋 Suggested Contract Sources")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **Government Sources:**
            - [SAM.gov](https://sam.gov) - Federal contracts
            - [FBO.gov](https://fbo.gov) - Business opportunities
            - [USASpending.gov](https://usaspending.gov) - Federal spending
            - [FPDS.gov](https://fpds.gov) - Procurement data
            """)
        
        with col2:
            st.markdown("""
            **Agency Sources:**
            - [Defense.gov Contracts](https://defense.gov/News/Contracts/)
            - [GSA News](https://gsa.gov/about-us/newsroom/)
            - [NASA Contracts](https://nasa.gov/news/contracts-news/)
            - [DHS Press Releases](https://dhs.gov/news-releases/)
            """)
    
    with tab2:
        st.header("Automated Search (Limited)")
        st.warning("🚨 May not work due to anti-bot measures")
        
        search_query = st.text_input(
            "Search Query", 
            value="IT services contract announcement",
            help="Enter search terms to find IT contract announcements"
        )
        
        num_results = st.number_input(
            "Max Results", 
            min_value=5, 
            max_value=20, 
            value=10,
            help="Number of search results to process"
        )
        
        if st.button("🔍 Try Auto Search", type="secondary"):
            if search_query:
                urls = search_with_fallbacks(search_query, num_results)
                if urls:
                    process_urls(urls)
    
    with tab3:
        st.header("Google Custom Search API")
        st.info("🔑 Requires free Google API setup but most reliable for automated search")
        
        col1, col2 = st.columns(2)
        with col1:
            google_api_key = st.text_input(
                "Google API Key", 
                type="password",
                help="Get free API key from Google Cloud Console"
            )
        with col2:
            search_engine_id = st.text_input(
                "Search Engine ID",
                help="Create custom search engine at programmablesearchengine.google.com"
            )
        
        search_query_api = st.text_input(
            "Search Query", 
            value="IT services contract announcement",
            key="api_query"
        )
        
        if st.button("🔍 Search with Google API", type="primary"):
            if google_api_key and search_engine_id and search_query_api:
                urls = search_google_api(search_query_api, google_api_key, search_engine_id, 10)
                if urls:
                    process_urls(urls)
            else:
                st.error("Please provide Google API Key and Search Engine ID")

def search_google_api(query, api_key, search_engine_id, num_results=10):
    """Search Google using Custom Search API"""
    try:
        base_url = "https://www.googleapis.com/customsearch/v1"
        
        params = {
            'key': api_key,
            'cx': search_engine_id,
            'q': query,
            'num': min(num_results, 10)  # Google API max is 10 per request
        }
        
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        links = []
        if 'items' in data:
            for item in data['items']:
                links.append(item['link'])
        
        st.success(f"✅ Google API found {len(links)} results")
        return links
    except Exception as e:
        st.error(f"Google Search API error: {str(e)}")
        return []

def process_urls(urls):
    """Process the URLs and extract contract information"""
    with st.spinner("Analyzing contract pages..."):
        # Process each URL
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, url in enumerate(urls):
            status_text.text(f"Processing {i+1}/{len(urls)}: {url[:60]}...")
            
            try:
                result = process_contract_page(url)
                if result:
                    results.append(result)
            except Exception as e:
                st.warning(f"Error processing {url}: {str(e)}")
            
            progress_bar.progress((i + 1) / len(urls))
            time.sleep(0.5)  # Rate limiting
        
        status_text.empty()
        progress_bar.empty()
        
        if results:
            display_results(results)
        else:
            st.warning("No qualifying contract announcements found. Try different URLs or check if they contain contract information.")

def display_results(results):
    """Display the contract analysis results"""
def display_results(results):
    """Display the contract analysis results"""
    # Display results
    df = pd.DataFrame(results)
    
    st.success(f"Found {len(results)} qualifying contract announcements!")
    
    # Summary statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_value = df['Estimated Value (USD Millions)'].sum()
        st.metric("Total Contract Value", f"${total_value:.1f}M" if total_value > 0 else "N/A")
    
    with col2:
        avg_duration = df['Contract Duration (Months)'].mean()
        st.metric("Avg Duration", f"{avg_duration:.0f} months" if pd.notna(avg_duration) else "N/A")
    
    with col3:
        service_types = df['Service Type'].dropna().nunique()
        st.metric("Service Types", service_types)
    
    with col4:
        vendors = df['Vendor'].dropna().nunique()
        st.metric("Unique Vendors", vendors)
    
    # Display data table
    st.subheader("📊 Contract Details")
    
    # Format display
    display_df = df.copy()
    display_df['Estimated Value (USD Millions)'] = display_df['Estimated Value (USD Millions)'].apply(
        lambda x: f"${x:.2f}M" if pd.notna(x) else "N/A"
    )
    display_df['Contract Duration (Months)'] = display_df['Contract Duration (Months)'].apply(
        lambda x: f"{int(x)} months" if pd.notna(x) else "N/A"
    )
    
    st.dataframe(display_df, use_container_width=True)
    
    # Download option
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name=f"it_contracts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
    
    # Service type breakdown
    if df['Service Type'].dropna().shape[0] > 0:
        st.subheader("🏷️ Service Type Breakdown")
        service_counts = df['Service Type'].value_counts()
        st.bar_chart(service_counts)
    
    # Information sidebar
    with st.sidebar:
        st.header("💡 Quick Start Guide")
        st.markdown("""
        **Best Approach:**
        1. Visit government contract sites
        2. Copy URLs of contract announcements
        3. Paste into "Manual URLs" tab
        4. Click "Analyze Manual URLs"
        
        **Good Sources:**
        - SAM.gov (search "IT services")
        - Defense.gov contracts section
        - Agency press release pages
        """)
        
        st.header("🔍 Search Issues?")
        st.markdown("""
        **Why search doesn't work:**
        - Search engines block bots
        - CAPTCHAs and rate limits
        - IP blocking for automation
        
        **Solutions:**
        1. Manual URL input (recommended)
        2. Google Custom Search API
        3. Use specific contract databases
        """)
        
        st.header("ℹ️ How Analysis Works")
        st.markdown("""
        1. **Fetch**: Downloads webpage content
        2. **Filter**: Only processes pages mentioning "contract"
        3. **Extract**: Uses regex patterns to find:
           - Contract values ($X million, $Y thousand)
           - Duration (X months, Y years)
           - Organizations (Corp, Inc, Ltd, etc.)
           - Service types from taxonomy
        4. **Structure**: Organizes data into standardized format
        5. **Export**: Download results as CSV
        """)
        
        st.header("🏷️ Service Types")
        st.markdown("Detected service types:")
        for service in SERVICE_TYPES:
            st.text(f"• {service}")

if __name__ == "__main__":
    main()
