import streamlit as st
import requests
import pandas as pd
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urljoin, urlparse
import time
import json
from typing import List, Dict, Optional

# Service type taxonomy
SERVICE_TYPES = [
    'modernization', 'cloud', 'migration', 'cybersecurity', 'AI', 'data', 
    'infrastructure', 'application development', 'testing', 'BPO', 
    'managed services', 'consulting', 'network'
]

# Initialize session state for saved URLs
if 'saved_urls' not in st.session_state:
    st.session_state.saved_urls = []

def load_saved_urls():
    """Load saved URLs from session state"""
    return st.session_state.saved_urls

def save_url(url: str, description: str = ""):
    """Save a URL to session state"""
    if url and url not in [item['url'] for item in st.session_state.saved_urls]:
        st.session_state.saved_urls.append({
            'url': url,
            'description': description,
            'added_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

def remove_saved_url(index: int):
    """Remove a saved URL by index"""
    if 0 <= index < len(st.session_state.saved_urls):
        st.session_state.saved_urls.pop(index)

def search_duckduckgo(query: str, num_results: int = 10, date_range: Optional[tuple] = None):
    """Search DuckDuckGo and return list of URLs with date filtering"""
    try:
        # Add date range to query if specified
        search_query = query
        if date_range:
            start_date, end_date = date_range
            # Add date range operators for DuckDuckGo (limited support)
            search_query += f" after:{start_date.strftime('%Y-%m-%d')} before:{end_date.strftime('%Y-%m-%d')}"
        
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(search_query)}"
        
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

def fetch_page_content(url: str):
    """Fetch and parse page content, return both raw text and structured data"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title = soup.find('title')
        title_text = title.get_text().strip() if title else "No title found"
        
        # Try to extract publication date from meta tags
        pub_date = extract_publication_date(soup)
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text content
        text = soup.get_text()
        
        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = ' '.join(chunk for chunk in chunks if chunk)
        
        return {
            'text': clean_text.lower(),
            'original_text': clean_text,
            'title': title_text,
            'publication_date': pub_date
        }
    except Exception as e:
        return None

def extract_publication_date(soup):
    """Extract publication date from HTML meta tags and content"""
    # Try various meta tag patterns
    date_selectors = [
        ('meta', {'property': 'article:published_time'}),
        ('meta', {'name': 'publishdate'}),
        ('meta', {'name': 'publication-date'}),
        ('meta', {'name': 'date'}),
        ('meta', {'property': 'og:published_time'}),
        ('time', {'datetime': True}),
    ]
    
    for tag_name, attrs in date_selectors:
        element = soup.find(tag_name, attrs)
        if element:
            date_str = element.get('content') or element.get('datetime') or element.get_text()
            if date_str:
                try:
                    # Try to parse various date formats
                    for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%fZ', '%B %d, %Y']:
                        try:
                            return datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').strftime('%Y-%m-%d')
                        except:
                            continue
                except:
                    continue
    
    # Fallback: look for date patterns in text
    text = soup.get_text()
    date_patterns = [
        r'(\w+ \d{1,2}, \d{4})',  # January 15, 2024
        r'(\d{1,2}/\d{1,2}/\d{4})',  # 01/15/2024
        r'(\d{4}-\d{2}-\d{2})',  # 2024-01-15
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, text)
        if matches:
            return matches[0]
    
    return datetime.now().strftime('%Y-%m-%d')  # Default to today

def generate_summary(text: str, max_sentences: int = 3) -> str:
    """Generate a simple extractive summary from text"""
    if not text:
        return "No summary available"
    
    # Split into sentences
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    
    if not sentences:
        return "No summary available"
    
    # Simple scoring: prefer sentences with contract-related keywords
    keywords = ['contract', 'agreement', 'award', 'million', 'services', 'company', 'announced']
    scored_sentences = []
    
    for sentence in sentences[:10]:  # Only look at first 10 sentences
        score = sum(1 for keyword in keywords if keyword.lower() in sentence.lower())
        scored_sentences.append((score, sentence))
    
    # Sort by score and take top sentences
    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    top_sentences = [s[1] for s in scored_sentences[:max_sentences]]
    
    summary = '. '.join(top_sentences)
    if len(summary) > 500:
        summary = summary[:500] + "..."
    
    return summary

def extract_contract_value(text: str):
    """Extract contract value in USD using regex"""
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
                return value / 1000000
    
    return None

def extract_duration(text: str):
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

def extract_organizations(text: str):
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
            if len(org) > 5 and org not in organizations:
                organizations.append(org)
    
    return organizations[:5]

def extract_service_type(text: str):
    """Extract service type from predefined taxonomy"""
    text_lower = text.lower()
    
    for service_type in SERVICE_TYPES:
        if service_type in text_lower:
            return service_type
    
    return None

def process_contract_page(url: str):
    """Process a single page and extract contract information"""
    content_data = fetch_page_content(url)
    
    if not content_data:
        return None
    
    content = content_data['text']
    original_text = content_data['original_text']
    
    # Filter for pages mentioning "contract"
    if 'contract' not in content:
        return None
    
    # Extract information
    contract_value = extract_contract_value(content)
    duration = extract_duration(content)
    organizations = extract_organizations(original_text)
    service_type = extract_service_type(content)
    summary = generate_summary(original_text)
    
    # Assign vendor and client
    vendor = organizations[0] if len(organizations) > 0 else None
    client = organizations[1] if len(organizations) > 1 else None
    
    return {
        'URL': url,
        'Title': content_data['title'],
        'Announcement Date': content_data['publication_date'],
        'Summary': summary,
        'Estimated Value (USD Millions)': contract_value,
        'Vendor': vendor,
        'Client': client,
        'Contract Duration (Months)': duration,
        'Service Type': service_type
    }

def main():
    st.set_page_config(page_title="IT Contract Search", page_icon="🔍", layout="wide")
    
    st.title("🔍 Enhanced IT Contract Search & Analysis")
    st.markdown("Search for publicly announced IT contracts and extract structured information with date filtering and manual URL management.")
    
    # Sidebar for saved URLs management
    with st.sidebar:
        st.header("📎 Saved URLs")
        
        # Add new URL
        with st.expander("Add New URL"):
            new_url = st.text_input("URL", key="new_url")
            new_description = st.text_input("Description (optional)", key="new_desc")
            if st.button("Save URL"):
                if new_url:
                    save_url(new_url, new_description)
                    st.success("URL saved!")
                    st.rerun()
        
        # Display saved URLs
        saved_urls = load_saved_urls()
        if saved_urls:
            st.subheader("Saved URLs")
            for i, url_data in enumerate(saved_urls):
                with st.container():
                    st.write(f"**{url_data['description'] or 'No description'}**")
                    st.write(f"URL: {url_data['url'][:50]}...")
                    st.write(f"Added: {url_data['added_date']}")
                    if st.button(f"Remove", key=f"remove_{i}"):
                        remove_saved_url(i)
                        st.rerun()
                    st.divider()
        
        # Export/Import saved URLs
        if saved_urls:
            urls_json = json.dumps(saved_urls, indent=2)
            st.download_button(
                "📥 Export Saved URLs",
                data=urls_json,
                file_name=f"saved_urls_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )
    
    # Main search interface
    tab1, tab2 = st.tabs(["🔍 Web Search", "📎 Process Saved URLs"])
    
    with tab1:
        # Search inputs
        col1, col2 = st.columns([2, 1])
        
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
        
        # Date range filter
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=datetime.now() - timedelta(days=30),
                help="Filter results from this date onwards"
            )
        
        with col2:
            end_date = st.date_input(
                "End Date",
                value=datetime.now(),
                help="Filter results up to this date"
            )
        
        if st.button("🔍 Search & Analyze", type="primary"):
            if search_query:
                date_range = (start_date, end_date) if start_date and end_date else None
                
                with st.spinner("Searching for contract announcements..."):
                    urls = search_duckduckgo(search_query, num_results, date_range)
                    
                    if not urls:
                        st.error("No search results found. Please try a different query.")
                        return
                    
                    st.success(f"Found {len(urls)} URLs to analyze")
                    process_urls(urls)
            else:
                st.error("Please enter a search query.")
    
    with tab2:
        st.subheader("Process Saved URLs")
        saved_urls = load_saved_urls()
        
        if saved_urls:
            selected_urls = st.multiselect(
                "Select URLs to process:",
                options=range(len(saved_urls)),
                format_func=lambda x: f"{saved_urls[x]['description'] or 'No description'} - {saved_urls[x]['url'][:50]}...",
                default=list(range(len(saved_urls)))
            )
            
            if st.button("📊 Process Selected URLs", type="primary"):
                if selected_urls:
                    urls_to_process = [saved_urls[i]['url'] for i in selected_urls]
                    process_urls(urls_to_process)
                else:
                    st.warning("Please select at least one URL to process.")
        else:
            st.info("No saved URLs found. Add some URLs in the sidebar to get started.")

def process_urls(urls: List[str]):
    """Process a list of URLs and display results"""
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
        st.warning("No qualifying contract announcements found. Try adjusting your search terms or check your saved URLs.")

def display_results(results: List[Dict]):
    """Display processed results with enhanced formatting"""
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
    
    # Display detailed results
    st.subheader("📊 Contract Details")
    
    for idx, row in df.iterrows():
        with st.expander(f"📄 {row['Title'][:100]}..." if len(row['Title']) > 100 else row['Title']):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write("**Summary:**")
                st.write(row['Summary'])
                
                st.write(f"**URL:** [{row['URL']}]({row['URL']})")
                st.write(f"**Announcement Date:** {row['Announcement Date']}")
                
                if row['Vendor']:
                    st.write(f"**Vendor:** {row['Vendor']}")
                if row['Client']:
                    st.write(f"**Client:** {row['Client']}")
            
            with col2:
                if row['Estimated Value (USD Millions)']:
                    st.metric("Contract Value", f"${row['Estimated Value (USD Millions)']:.2f}M")
                
                if row['Contract Duration (Months)']:
                    st.metric("Duration", f"{int(row['Contract Duration (Months)'])} months")
                
                if row['Service Type']:
                    st.write(f"**Service Type:** {row['Service Type']}")
    
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

if __name__ == "__main__":
    main()
