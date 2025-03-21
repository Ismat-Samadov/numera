# scrapers/emlak.py
import requests 
from bs4 import BeautifulSoup
from datetime import datetime
import json
import time
import random
import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from urllib.parse import urljoin

@dataclass
class ScraperStats:
    total_pages: int = 0
    total_listings: int = 0
    valid_numbers: int = 0
    invalid_numbers: int = 0
    multi_phone_items: int = 0
    invalid_phone_list: List[str] = None

    def __post_init__(self):
        self.invalid_phone_list = []

    def print_summary(self):
        """Print scraping statistics summary"""
        print("\nScraping Statistics:")
        print(f"Total pages processed: {self.total_pages}")
        print(f"Total listings found: {self.total_listings}")
        print(f"Valid numbers found: {self.valid_numbers}")
        print(f"Invalid numbers found: {self.invalid_numbers}")
        print(f"Listings with multiple phones: {self.multi_phone_items}")
        if self.invalid_numbers > 0:
            print("\nInvalid phone numbers:")
            for phone in self.invalid_phone_list:
                print(f"  {phone}")

def format_phone(phone: str, stats: Optional[ScraperStats] = None, original: str = None) -> Optional[str]:
    """Format and validate phone number according to rules"""
    if not phone:
        return None
        
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # Remove country code if present
    if digits.startswith('994'): 
        digits = digits[3:]
    if digits.startswith('0'): 
        digits = digits[1:]
    
    # Validate length
    if len(digits) != 9:
        if stats:
            stats.invalid_phone_list.append(f"Length error - Original: {original}, Cleaned: {digits}")
        return None
    
    # Validate prefix
    valid_prefixes = ('10', '12', '50', '51', '55', '60', '70', '77', '99')
    if not digits.startswith(valid_prefixes):
        if stats:
            stats.invalid_phone_list.append(f"Prefix error - Original: {original}, Cleaned: {digits}")
        return None
    
    # Validate fourth digit
    if digits[3] in ('0', '1'):
        if stats:
            stats.invalid_phone_list.append(f"Fourth digit error - Original: {original}, Cleaned: {digits}")
        return None
        
    return digits

def get_headers() -> Dict[str, str]:
    """Get randomized headers"""
    user_agents = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    
    return {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'User-Agent': random.choice(user_agents)
    }

def make_request(session: requests.Session, url: str, max_retries: int = 3) -> Optional[BeautifulSoup]:
    """Make HTTP request with retries and random delays"""
    for attempt in range(max_retries):
        try:
            time.sleep(random.uniform(1, 2))  # Random delay between requests
            response = session.get(url, headers=get_headers(), timeout=10)
            
            if response.status_code == 200:
                return BeautifulSoup(response.text, 'html.parser')
            
            print(f"Got status code {response.status_code} for {url}")
            
        except Exception as e:
            print(f"Request error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt == max_retries - 1:
                raise
            time.sleep(random.uniform(2, 4))  # Longer delay after error
    
    return None

def extract_phones(text: str) -> List[str]:
    """Extract phone numbers from text"""
    if not text:
        return []
        
    # Remove any extra whitespace
    text = text.strip()
    
    # Split by comma
    phones = [p.strip() for p in text.split(',')]
    
    # Clean each phone number
    cleaned_phones = []
    for phone in phones:
        # Remove parentheses and extra spaces
        cleaned = re.sub(r'[()]', '', phone).strip()
        if cleaned:
            cleaned_phones.append(cleaned)
            
    return cleaned_phones

def extract_listing_details(soup: BeautifulSoup, url: str) -> Optional[Dict]:
    """Extract details from a listing page"""
    try:
        details = {}
        
        # Extract price
        price_elem = soup.find('div', class_='price')
        if price_elem:
            price_text = price_elem.find('span', class_='m')
            if price_text:
                details['price'] = price_text.text.strip()

        # Extract title and description
        title = soup.find('h1', class_='title')
        if title:
            details['title'] = title.text.strip()
            
        desc_elem = soup.find('div', class_='desc')
        if desc_elem:
            details['description'] = desc_elem.text.strip()

        # Extract technical characteristics
        tech_chars = {}
        tech_list = soup.find('dl', class_='technical-characteristics')
        if tech_list:
            for item in tech_list.find_all('dd'):
                label = item.find('span', class_='label')
                if label:
                    key = label.text.strip()
                    value = item.text.replace(key, '').strip()
                    tech_chars[key] = value

        # Extract contact info
        contact_info = {}
        seller_data = soup.find('div', class_='seller-data')
        if seller_data:
            silver_box = seller_data.find('div', class_='silver-box')
            if silver_box:
                name_elem = silver_box.find('p', class_='name-seller')
                if name_elem:
                    name_text = name_elem.find(text=True)
                    if name_text:
                        contact_info['name'] = name_text.strip()

                phone_elem = silver_box.find('p', {'class': 'phone'})
                phone_numbers = []
                if phone_elem:
                    phone_text = phone_elem.get_text(strip=True)
                    if phone_text:
                        print(f"Found phone text: {phone_text}")
                        phone_numbers = extract_phones(phone_text)

        if not phone_numbers:
            return None

        # Format each phone number
        valid_phones = []
        for phone in phone_numbers:
            formatted = format_phone(phone, None, phone)
            if formatted:
                valid_phones.append(formatted)

        if not valid_phones:
            return None

        # Create base item structure
        base_item = {
            'name': contact_info.get('name', ''),
            'website': 'emlak.az',
            'link': url,
            'raw_data': {
                'title': details.get('title'),
                'price': details.get('price'),
                'description': details.get('description'),
                'technical_characteristics': tech_chars
            }
        }

        # Return a list of items, one per valid phone number
        return [{**base_item, 'phone': phone} for phone in valid_phones]

    except Exception as e:
        print(f"Error extracting listing details: {e}")
        return None

def get_listing_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    """Extract all listing links from a page"""
    links = []
    listings = soup.find_all('div', class_='ticket')
    
    for listing in listings:
        link_elem = listing.find('h6', class_='title').find('a') if listing.find('h6', class_='title') else None
        if link_elem and link_elem.get('href'):
            link = urljoin(base_url, link_elem['href'])
            links.append(link)
    
    return links

def scrape() -> List[Dict]:
    """Main scraping function"""
    session = requests.Session()
    base_url = "https://emlak.az"
    items_to_process = []
    stats = ScraperStats()
    
    try:
        pages_to_scrape = [1, 2, 3]
        stats.total_pages = len(pages_to_scrape)
        print(f"Will scrape {len(pages_to_scrape)} pages")
        
        for page in pages_to_scrape:
            try:
                url = f"https://emlak.az/elanlar/?ann_type=1&sort_type=0&page={page}"
                print(f"\nProcessing page {page}/{len(pages_to_scrape)}")
                
                soup = make_request(session, url)
                if not soup:
                    print(f"Failed to get response for page {page}")
                    continue
                
                listing_links = get_listing_links(soup, base_url)
                print(f"Found {len(listing_links)} listings on page {page}")
                
                for idx, link in enumerate(listing_links, 1):
                    try:
                        print(f"Processing listing {idx}/{len(listing_links)}: {link}")
                        
                        listing_soup = make_request(session, link)
                        if not listing_soup:
                            print(f"Failed to get listing details for {link}")
                            continue
                        
                        items = extract_listing_details(listing_soup, link)
                        if items:
                            items_to_process.extend(items)
                            stats.valid_numbers += len(items)
                            if len(items) > 1:
                                stats.multi_phone_items += 1
                            print(f"Successfully processed listing with {len(items)} phone numbers")
                        else:
                            stats.invalid_numbers += 1
                            print(f"No valid phone numbers found for listing {link}")
                            
                        stats.total_listings += 1
                        
                    except Exception as e:
                        print(f"Error processing listing {link}: {e}")
                        continue
                    
            except Exception as e:
                print(f"Error processing page {page}: {e}")
                continue

        # Print final statistics
        stats.print_summary()
        
    except Exception as e:
        print(f"Scraping error: {e}")
    
    return items_to_process