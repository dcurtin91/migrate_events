"""
Base scraper class and utilities for venue event scraping.
"""
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import re
import time
from urllib.parse import urljoin, urlparse


class EventScraper:
    """Base class for venue event scrapers."""
    
    def __init__(self, venue_name: str, venue_url: str, delay: float = 1.0):
        """
        Initialize the scraper.
        
        Args:
            venue_name: Name of the venue
            venue_url: Base URL of the venue website
            delay: Delay between requests in seconds (to be respectful)
        """
        self.venue_name = venue_name
        self.venue_url = venue_url
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a webpage."""
        try:
            time.sleep(self.delay)  # Be respectful to servers
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    
    
    def extract_events(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Extract events from a parsed page.
        Override this method for venue-specific extraction logic.
        
        Returns:
            List of event dictionaries with keys matching CSV columns
        """
        events = []
        # This is a generic implementation - should be overridden
        # Look for common event patterns
        event_elements = soup.find_all(['article', 'div', 'a'], class_=re.compile(r'event|show|concert', re.I), inner_text=re.compile(r'buy tickets|get tickets|buy|tickets|rsvp|more info|learn more|read more|view details|details|sold out|live music|', re.I))
        
        for element in event_elements:
            event = self._parse_event_element(element)
            if event:
                events.append(event)
        
        return events
    
    def _parse_event_element(self, element) -> Optional[Dict]:
        """Parse a single event element (generic implementation)."""
        # This is a basic implementation - should be customized per venue
        event = {
            'Hold Level': '1',
            'Artist': '',
            'Type': 'Confirm',
            'Venue': self.venue_name,
            'Event Name': '',
            'Buyer': '',
            'Promoter': '',
            'Event End Time': '',
            'Event Start Time': '',
            'Event Door Time': '',
            'Event Image URL': '',
            'Notes': '',
            'Venue Permalink': '',
            'Description Text': '',
            'Description Image': '',
            'Description Video': '',
            'Contacts': '',
            'ID': ''
        }
        
        # Try to extract event name
        name_elem = element.find(['h1', 'h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|name|event', re.I))
        if name_elem:
            event['Event Name'] = name_elem.get_text(strip=True)
            event['Artist'] = event['Event Name']  # Default to event name if no artist
        
        # Try to extract date/time
        date_elem = element.find(['time', 'span', 'div'], class_=re.compile(r'date|time', re.I))
        if date_elem:
            date_text = date_elem.get_text(strip=True)
            event['Event Start Time'] = self._parse_date(date_text)
        
        # Try to extract image
        img_elem = element.find('img')
        if img_elem and img_elem.get('src'):
            img_url = img_elem['src']
            event['Event Image URL'] = urljoin(self.venue_url, img_url)
            event['Description Image'] = event['Event Image URL']
        
        # Try to extract description
        desc_elem = element.find(['p', 'div'], class_=re.compile(r'description|summary', re.I))
        if desc_elem:
            event['Description Text'] = desc_elem.get_text(strip=True)
        
        return event if event['Event Name'] else None
    
    def _parse_date(self, date_text: str) -> str:
        """
        Parse date text into the format: MM/DD/YYYY HH:MM PM EST
        This is a basic implementation - should be enhanced per venue.
        """
        # Try to extract date information
        # This is a placeholder - real implementation would use dateutil or similar
        return date_text
    
    def scrape(self) -> List[Dict]:
        """
        Main scraping method.
        Returns list of event dictionaries.
        """
        events_page = self.venue_url
        if not events_page:
            print(f"Could not find events page for {self.venue_name}")
            return []
        
        soup = self.fetch_page(events_page)
        if not soup:
            return []
        
        events = self.extract_events(soup)
        print(f"Found {len(events)} events for {self.venue_name}")
        return events


class GenericScraper(EventScraper):
   
    
    def extract_events(self, soup: BeautifulSoup) -> List[Dict]:
        """Enhanced generic extraction with more patterns."""
        events = []
        
        # Look for various event container patterns
        selectors = [
            {'class': re.compile(r'event', re.I)},
            {'class': re.compile(r'show', re.I)},
            {'class': re.compile(r'concert', re.I)},
            {'class': re.compile(r'listing', re.I)},
            {'class': re.compile(r'post', re.I)},
            {'class': re.compile(r'card', re.I)},
            {'itemtype': re.compile(r'Event', re.I)},
            {'data-event': True},
        ]
        
        event_elements = []
        for selector in selectors:
            found = soup.find_all(['article', 'div', 'li', 'section'], selector)
            event_elements.extend(found)
        
        # Also look for "Buy Tickets" links and find their parent containers
        buy_ticket_links = soup.find_all('a', string=re.compile(r'buy\s+tickets?|get\s+tickets?', re.I))
        for link in buy_ticket_links:
            # Find parent container (go up to find event container)
            parent = link.parent
            for _ in range(5):  # Go up max 5 levels
                if parent and parent.name in ['article', 'div', 'li', 'section']:
                    # Check if this looks like an event container
                    parent_classes = parent.get('class', [])
                    if any(keyword in ' '.join(parent_classes).lower() for keyword in 
                          ['event', 'post', 'card', 'listing', 'show', 'concert']):
                        if parent not in event_elements:
                            event_elements.append(parent)
                        break
                parent = parent.parent if parent else None
                if not parent:
                    break
        
        # Remove duplicates
        seen = set()
        unique_elements = []
        for elem in event_elements:
            elem_id = id(elem)
            if elem_id not in seen:
                seen.add(elem_id)
                unique_elements.append(elem)
        
        for element in unique_elements:
            event = self._parse_event_element_enhanced(element)
            if event and event['Event Name']:
                events.append(event)
        
        return events
    
    def _parse_event_element_enhanced(self, element) -> Optional[Dict]:
        """Enhanced event parsing with more extraction patterns."""
        event = {
            'Hold Level': '1',
            'Artist': '',
            'Type': 'Confirm',
            'Venue': self.venue_name,
            'Event Name': '',
            'Buyer': '',
            'Promoter': '',
            'Event End Time': '',
            'Event Start Time': '',
            'Event Door Time': '',
            'Event Image URL': '',
            'Notes': '',
            'Venue Permalink': '',
            'Description Text': '',
            'Description Image': '',
            'Description Video': '',
            'Contacts': '',
            'ID': ''
        }
        
        # Extract event name from various possible locations
        name_selectors = [
            ('h1', {'class': re.compile(r'title|name|event', re.I)}),
            ('h2', {'class': re.compile(r'title|name|event', re.I)}),
            ('h3', {'class': re.compile(r'title|name|event', re.I)}),
            ('a', {'class': re.compile(r'title|name|event', re.I)}),
            ('span', {'class': re.compile(r'title|name|event', re.I)}),
            ('div', {'class': re.compile(r'title|name|event', re.I)}),
            ('h1', {}),
            ('h2', {}),
        ]
        
        # Filter out invalid event names
        invalid_names = ['buy tickets', 'get tickets', 'buy', 'tickets', 'rsvp', 'more info', 
                        'learn more', 'read more', 'view details', 'details', 'sold out']
        
        for tag, attrs in name_selectors:
            name_elem = element.find(tag, attrs) if attrs else element.find(tag)
            if name_elem:
                name = name_elem.get_text(strip=True)
                # Skip if it's an invalid name
                if name and len(name) > 3 and name.lower() not in invalid_names:
                    event['Event Name'] = name
                    event['Artist'] = name  # Default
                    break
        # Try to extract 'Venue Permalink' from buttons or links with 'Get Tickets', 'Buy Tickets', or 'Buy' text
        button_texts = ['get tickets', 'buy tickets', 'buy', 'sold out']
        venue_permalink = ''
        # Search for <a> and <button> tags
        for tag in ['a', 'button']:
            for btn in element.find_all(tag):
                btn_text = btn.get_text(strip=True).lower()
                if any(text in btn_text for text in button_texts):
                    href = btn.get('href')
                    if href:
                        venue_permalink = urljoin(self.venue_url, href)
                        break
            if venue_permalink:
                break
        if venue_permalink:
            event['Venue Permalink'] = venue_permalink
        # Extract date/time - look more thoroughly
        date_selectors = [
            ('time', {}),
            ('span', {'class': re.compile(r'date|time|when', re.I)}),
            ('div', {'class': re.compile(r'date|time|when', re.I)}),
            ('p', {'class': re.compile(r'date|time|when', re.I)}),
            ('div', {'class': re.compile(r'meta|info', re.I)}),
        ]
        
        # First try to get datetime attribute from time tag
        time_elem = element.find('time')
        if time_elem:
            datetime_attr = time_elem.get('datetime')
            if datetime_attr:
                event['Event Start Time'] = datetime_attr
            else:
                date_text = time_elem.get_text(strip=True)
                if date_text:
                    event['Event Start Time'] = date_text
        
        # If no time tag, look for other date elements
        if not event['Event Start Time']:
            for tag, attrs in date_selectors:
                date_elem = element.find(tag, attrs) if attrs else element.find(tag)
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    # Filter out invalid date text (like "Buy Tickets")
                    if date_text and date_text.lower() not in ['buy tickets', 'get tickets', 'buy', 'sold out']:
                        event['Event Start Time'] = date_text
                        break
        
        # Also search the entire element text for date patterns
        if not event['Event Start Time'] or 'Show:' in event['Event Start Time'] or 'Doors:' in event['Event Start Time']:
            full_text = element.get_text(separator=' | ')
            # Look for date patterns like "Monday, November 25, 2024" or "11/25/2024"
            date_patterns = [
                re.compile(r'(\w+day,?\s+\w+\s+\d{1,2},?\s+\d{4})', re.I),  # Monday, November 25, 2024
                re.compile(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', re.I),  # 11/25/2024 or 11-25-2024
                re.compile(r'(\w+\s+\d{1,2},?\s+\d{4})', re.I),  # November 25, 2024
            ]
            
            found_date = None
            for pattern in date_patterns:
                match = pattern.search(full_text)
                if match:
                    found_date = match.group(1)
                    break
            
            # Also look for time patterns
            time_pattern = re.compile(r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))', re.I)
            time_match = time_pattern.search(full_text)
            found_time = time_match.group(1) if time_match else None
            
            # Combine date and time if found
            if found_date:
                if found_time:
                    event['Event Start Time'] = f"{found_date} {found_time}"
                else:
                    event['Event Start Time'] = found_date
            elif found_time and not event['Event Start Time']:
                event['Event Start Time'] = found_time
        
        # Extract image - look more thoroughly, including background images
        img_elem = element.find('img')
        if img_elem:
            img_url = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy-src') or img_elem.get('data-original')
            if img_url and not img_url.startswith('data:') and 'placeholder' not in img_url.lower():
                event['Event Image URL'] = urljoin(self.venue_url, img_url)
                event['Description Image'] = event['Event Image URL']
        
        # Also check for background images in style attributes
        if not event['Event Image URL']:
            # Check element and parent elements for background-image
            check_elem = element
            for _ in range(3):
                if check_elem:
                    style = check_elem.get('style', '')
                    if style and 'background-image' in style:
                        bg_match = re.search(r'background-image:\s*url\(["\']?([^"\']+)["\']?\)', style, re.I)
                        if bg_match:
                            img_url = bg_match.group(1)
                            if not img_url.startswith('data:'):
                                event['Event Image URL'] = urljoin(self.venue_url, img_url)
                                event['Description Image'] = event['Event Image URL']
                                break
                    check_elem = check_elem.parent if check_elem else None
                else:
                    break
        
        # Extract description
        desc_selectors = [
            ('p', {'class': re.compile(r'description|summary|excerpt', re.I)}),
            ('div', {'class': re.compile(r'description|summary|excerpt', re.I)}),
            ('p', {}),
        ]
        
        for tag, attrs in desc_selectors:
            desc_elem = element.find(tag, attrs) if attrs else element.find(tag)
            if desc_elem:
                desc = desc_elem.get_text(strip=True)
                if desc and len(desc) > 10:  # Valid description
                    event['Description Text'] = desc
                    break
        
        return event if event['Event Name'] else None

