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

def search_duckduckgo(query, num_results=10):
    """Search DuckDuckGo and return list of URLs"""
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
        st.error(f"Search error: {str(e)}")
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
    
    # Search input
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_query = st.text_input(
            "Search Query", 
            value="IT services contract announcement",
            help="Enter search terms to find IT contract announcements"
        )
    
    with col2:
        num_results = st.number_input(
            "Max Results", 
            min_value=5, 
            max_value=20, 
            value=10,
            help="Number of search results to process"
        )
    
    if st.button("🔍 Search & Analyze", type="primary"):
        if search_query:
            with st.spinner("Searching for contract announcements..."):
                # Search for URLs
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
