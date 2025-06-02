import streamlit as st
import requests
import pandas as pd
import re
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import quote_plus, urljoin, urlparse
import time

# Service type taxonomy
SERVICE_TYPES = [
    'modernization', 'cloud', 'migration', 'cybersecurity', 'AI', 'data', 
    'infrastructure', 'application development', 'testing', 'BPO', 
    'managed services', 'consulting', 'network'
]

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
        
        return links
    except Exception as e:
        st.error(f"Google Search API error: {str(e)}")
        return []

def search_google_scraping(query, num_results=10):
    """Search Google by scraping (less reliable, may be blocked)"""
    try:
        # Google search URL
        search_url = f"https://www.google.com/search?q={quote_plus(query)}&num={num_results}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract links from Google results
        links = []
        
        # Google search result selectors (these change frequently)
        selectors = ['h3 a', '.yuRUbf a', '.kCrYT a']
        
        for selector in selectors:
            for link_elem in soup.select(selector):
                href = link_elem.get('href')
                if href and href.startswith('http') and 'google.com' not in href:
                    if href not in links:  # Avoid duplicates
                        links.append(href)
                        if len(links) >= num_results:
                            break
            if links:
                break
        
        return links
    except Exception as e:
        st.error(f"Google scraping error: {str(e)}")
        return []

def search_duckduckgo(query, num_results=10):
    """Search DuckDuckGo and return list of URLs (fallback option)"""
    try:
        # DuckDuckGo HTML search URL
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract links from DuckDuckGo results
        links = []
        for link_elem in soup.find_all('a', {'class': 'result__a'}):
            href = link_elem.get('href')
            if href and href.startswith('http'):
                links.append(href)
                if len(links) >= num_results:
                    break
        
        return links
    except Exception as e:
        st.error(f"DuckDuckGo search error: {str(e)}")
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
    
    # Search configuration
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        search_query = st.text_input(
            "Search Query", 
            value="IT services contract announcement",
            help="Enter search terms to find IT contract announcements"
        )
    
    with col2:
        search_engine = st.selectbox(
            "Search Engine",
            ["DuckDuckGo", "Google (Scraping)", "Google (API)"],
            help="Choose search method"
        )
    
    with col3:
        num_results = st.number_input(
            "Max Results", 
            min_value=5, 
            max_value=20, 
            value=10,
            help="Number of search results to process"
        )
    
    # Google API configuration (only show if Google API is selected)
    if search_engine == "Google (API)":
        st.info("🔑 Google Custom Search API requires free API key setup")
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
        
        if not google_api_key or not search_engine_id:
            st.warning("⚠️ Google API Key and Search Engine ID are required for Google API search")
    
    elif search_engine == "Google (Scraping)":
        st.warning("⚠️ Google scraping may be blocked or rate-limited. Use sparingly.")
    
    else:
        st.info("ℹ️ DuckDuckGo is more reliable for automated searches")
    
    if st.button("🔍 Search & Analyze", type="primary"):
        if search_query:
            with st.spinner("Searching for contract announcements..."):
                # Choose search method
                urls = []
                
                if search_engine == "Google (API)":
                    if google_api_key and search_engine_id:
                        urls = search_google_api(search_query, google_api_key, search_engine_id, num_results)
                    else:
                        st.error("Please provide Google API Key and Search Engine ID")
                        return
                        
                elif search_engine == "Google (Scraping)":
                    urls = search_google_scraping(search_query, num_results)
                    
                else:  # DuckDuckGo
                    urls = search_duckduckgo(search_query, num_results)
                
                if not urls:
                    st.error("No search results found. Please try a different query.")
                    return
                
                st.success(f"Found {len(urls)} URLs to analyze")
                
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
                
                else:
                    st.warning("No qualifying contract announcements found. Try adjusting your search terms.")
        
        else:
            st.error("Please enter a search query.")
    
    # Information sidebar
    with st.sidebar:
        st.header("🔍 Search Options")
        st.markdown("""
        **DuckDuckGo**: Most reliable, no setup required
        
        **Google Scraping**: May be blocked, use sparingly
        
        **Google API**: Best results but requires:
        1. Google Cloud account (free)
        2. Enable Custom Search API
        3. Create search engine ID
        4. Get API key
        """)
        
        st.header("ℹ️ How it Works")
        st.markdown("""
        1. **Search**: Uses DuckDuckGo to find relevant pages
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
