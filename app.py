from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import io
from scraper import GenericScraper
from csv_writer import EventCSVWriter
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

def extract_events_with_ai(html_content, venue_name):
    """Use Claude AI to extract events from HTML."""
    try:
        import anthropic
        
        # Check for API key
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            print("Warning: ANTHROPIC_API_KEY not found in environment")
            return []
        
        # Truncate HTML if too long (keep first 100k chars)
        if len(html_content) > 100000:
            html_content = html_content[:100000]
        
        client = anthropic.Anthropic(api_key=api_key)
        
        prompt = f"""You are a web scraping assistant. Extract all music events from this HTML.

Venue name: {venue_name}

For each event, extract:
- Event Name (required)
- Event Start Time (date and time if available, e.g., "12/6/2024 8:00 PM")
- Event Image URL (full URL)
- Venue Permalink (ticket purchase link or event detail link)
- Description Text (brief description)

Return ONLY valid JSON in this exact format:
[
  {{
    "Event Name": "...",
    "Event Start Time": "...",
    "Event Image URL": "...",
    "Venue Permalink": "...",
    "Description Text": "..."
  }}
]

HTML:
{html_content}"""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        
        # Parse JSON response
        import json
        import re
        
        # Extract JSON from response (in case there's explanatory text)
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            events_data = json.loads(json_match.group(0))
        else:
            events_data = json.loads(response_text)
        
        # Convert to required format
        events = []
        for event_data in events_data:
            event = {
                'Hold Level': '1',
                'Artist': event_data.get('Event Name', ''),
                'Type': 'Confirm',
                'Venue': venue_name,
                'Event Name': event_data.get('Event Name', ''),
                'Buyer': '',
                'Promoter': '',
                'Event End Time': '',
                'Event Start Time': event_data.get('Event Start Time', ''),
                'Event Door Time': '',
                'Event Image URL': event_data.get('Event Image URL', ''),
                'Notes': '',
                'Venue Permalink': event_data.get('Venue Permalink', ''),
                'Description Text': event_data.get('Description Text', ''),
                'Description Image': event_data.get('Event Image URL', ''),
                'Description Video': '',
                'Contacts': '',
                'ID': ''
            }
            if event['Event Name']:
                events.append(event)
        
        print(f"AI extracted {len(events)} events")
        return events
        
    except Exception as e:
        print(f"AI extraction failed: {e}")
        return []

# HTML template embedded in Flask
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>Event Scraper</title>
  <style>
    body { font-family: Arial; max-width: 600px; margin: 40px auto; padding: 20px; }
    
    /* Tabs */
    .tabs { display: flex; gap: 0; margin-bottom: 20px; border-bottom: 2px solid #ddd; }
    .tab { padding: 12px 24px; cursor: pointer; background: #f5f5f5; border: none; 
           font-size: 16px; border-radius: 4px 4px 0 0; transition: all 0.2s; }
    .tab:hover { background: #e0e0e0; }
    .tab.active { background: #007bff; color: white; font-weight: bold; }
    
    /* Content */
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    
    input, textarea, button { padding: 10px; font-size: 16px; width: 100%; box-sizing: border-box; }
    textarea { min-height: 200px; font-family: monospace; resize: vertical; }
    button { margin-top: 10px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 4px; }
    button:hover { background: #0056b3; }
    button:disabled { background: #ccc; cursor: not-allowed; }
    #status { margin-top: 15px; padding: 10px; border-radius: 4px; }
    .success { background: #d4edda; color: #155724; }
    .error { background: #f8d7da; color: #721c24; }
    .loading { background: #fff3cd; color: #856404; }
    .hint { color: #666; font-size: 14px; margin-top: 5px; }
  </style>
</head>

<body>
  <h2>Event Scraper</h2>
  
  <div class="tabs">
    <button class="tab active" onclick="switchTab('url')">URL</button>
    <button class="tab" onclick="switchTab('html')">HTML</button>
  </div>
  
  <!-- URL Tab -->
  <div id="url-tab" class="tab-content active">
    <input id="url" placeholder="https://hideoutchicago.com/events/" />
    <div class="hint">Enter a venue's events page URL</div>
    <button onclick="scrapeUrl()" id="urlBtn">Scrape Events</button>
  </div>
  
  <!-- HTML Tab -->
  <div id="html-tab" class="tab-content">
    <textarea id="html" placeholder="Paste HTML content here..."></textarea>
    <div class="hint">Paste the HTML from a venue's events page</div>
    <input id="venue-name" placeholder="Venue name (optional)" style="margin-top: 10px;" />
    <button onclick="scrapeHtml()" id="htmlBtn">Scrape Events</button>
  </div>

  <div id="status"></div>

  <script>
    function switchTab(tab) {
      // Update tab buttons
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      event.target.classList.add('active');
      
      // Update content
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      document.getElementById(tab + '-tab').classList.add('active');
      
      // Clear status
      document.getElementById('status').innerText = '';
      document.getElementById('status').className = '';
    }
    
    async function scrapeUrl() {
      const url = document.getElementById("url").value.trim();
      const statusDiv = document.getElementById("status");
      const btn = document.getElementById("urlBtn");
      
      if (!url) {
        statusDiv.className = "error";
        statusDiv.innerText = "Please enter a URL";
        return;
      }

      statusDiv.className = "loading";
      statusDiv.innerText = "Scraping events... This may take a moment.";
      btn.disabled = true;

      try {
        const response = await fetch("/scrape", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url })
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || "Error scraping");
        }

        const blob = await response.blob();
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "events.csv";
        link.click();

        statusDiv.className = "success";
        statusDiv.innerText = "✓ Done! CSV file downloaded.";
      } catch (error) {
        statusDiv.className = "error";
        statusDiv.innerText = "✗ " + error.message;
      } finally {
        btn.disabled = false;
      }
    }
    
    async function scrapeHtml() {
      const html = document.getElementById("html").value.trim();
      const venueName = document.getElementById("venue-name").value.trim() || "venue";
      const statusDiv = document.getElementById("status");
      const btn = document.getElementById("htmlBtn");
      
      if (!html) {
        statusDiv.className = "error";
        statusDiv.innerText = "Please paste HTML content";
        return;
      }

      statusDiv.className = "loading";
      statusDiv.innerText = "Scraping events from HTML... This may take a moment.";
      btn.disabled = true;

      try {
        const response = await fetch("/scrape-html", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ html, venue_name: venueName })
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || "Error scraping");
        }

        const blob = await response.blob();
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = venueName + "_events.csv";
        link.click();

        statusDiv.className = "success";
        statusDiv.innerText = "✓ Done! CSV file downloaded.";
      } catch (error) {
        statusDiv.className = "error";
        statusDiv.innerText = "✗ " + error.message;
      } finally {
        btn.disabled = false;
      }
    }
    
    // Allow Enter key to trigger scrape in URL field
    document.getElementById("url").addEventListener("keypress", function(e) {
      if (e.key === "Enter") scrapeUrl();
    });
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/scrape', methods=['POST'])
def scrape_events():
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'No URL provided'}), 400
        
        # Extract venue name from URL (e.g., hideoutchicago.com -> hideoutchicago)
        try:
            venue_name = url.split('/')[2].split('.')[0].replace('www.', '')
        except:
            venue_name = 'venue'
        
        print(f"Scraping {venue_name} at {url}...")
        
        # Run scraper
        scraper = GenericScraper(venue_name=venue_name, venue_url=url)
        soup = scraper.fetch_page(url)
        
        if not soup:
            return jsonify({'error': 'Could not fetch the page'}), 500
        
        # First, try to extract from JSON-LD structured data
        import json
        events = []
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        
        if json_ld_scripts:
            print(f"Found {len(json_ld_scripts)} JSON-LD scripts, extracting structured data...")
            for script in json_ld_scripts:
                try:
                    event_data = json.loads(script.string)
                    if event_data.get('@type') == 'Event':
                        # Extract event information from JSON-LD
                        event = {
                            'Hold Level': '1',
                            'Artist': event_data.get('name', ''),
                            'Type': 'Confirm',
                            'Venue': event_data.get('location', {}).get('name', venue_name),
                            'Event Name': event_data.get('name', ''),
                            'Buyer': '',
                            'Promoter': '',
                            'Event End Time': event_data.get('endDate', ''),
                            'Event Start Time': event_data.get('startDate', ''),
                            'Event Door Time': '',
                            'Event Image URL': event_data.get('image', ''),
                            'Notes': '',
                            'Venue Permalink': event_data.get('url', ''),
                            'Description Text': event_data.get('description', ''),
                            'Description Image': event_data.get('image', ''),
                            'Description Video': '',
                            'Contacts': '',
                            'ID': ''
                        }
                        events.append(event)
                except (json.JSONDecodeError, AttributeError) as e:
                    print(f"Error parsing JSON-LD: {e}")
                    continue
        
        # If no JSON-LD data found, fall back to generic scraper
        if not events:
            print("No JSON-LD data found, using AI extraction...")
            events = extract_events_with_ai(str(soup), venue_name)
        
        if not events:
            return jsonify({'error': 'No events found. The page structure might not be supported.'}), 404
        
        print(f"Found {len(events)} events")
        
        # Use CSV writer to format events properly (with time calculations)
        writer = EventCSVWriter(output_path='temp_events.csv')
        
        # Create CSV in memory
        output = io.StringIO()
        
        # Write events using the CSV writer's formatting
        import pandas as pd
        import csv
        
        # Normalize events to match expected columns
        normalized_events = []
        for event in events:
            normalized = {col: event.get(col, '') for col in writer.COLUMNS}
            normalized_events.append(normalized)
        
        # Convert to DataFrame and apply processing
        df = pd.DataFrame(normalized_events)
        
        # Filter out invalid events
        df = df[df['Venue Permalink'].notna() & (df['Venue Permalink'] != '')]
        df = df[df['Event Name'].notna() & (df['Event Name'] != '')]
        
        # Remove duplicates
        df = df.drop_duplicates(subset=['Venue Permalink'], keep='last')
        
        # Calculate door and end times
        df = writer._calculate_times(df)
        
        # Write to string
        df.to_csv(output, index=False, quoting=csv.QUOTE_NONNUMERIC)
        
        # Convert to bytes for sending
        output.seek(0)
        byte_output = io.BytesIO(output.getvalue().encode('utf-8'))
        byte_output.seek(0)
        
        print(f"Returning CSV with {len(df)} events")
        
        return send_file(
            byte_output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{venue_name}_events.csv'
        )
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/scrape-html', methods=['POST'])
def scrape_html():
    try:
        data = request.get_json()
        html_content = data.get('html')
        venue_name = data.get('venue_name', 'venue')
        
        if not html_content:
            return jsonify({'error': 'No HTML content provided'}), 400
        
        print(f"Scraping HTML for {venue_name}...")
        
        # Parse HTML directly with BeautifulSoup
        from bs4 import BeautifulSoup
        import json
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # First, try to extract from JSON-LD structured data (common in modern sites)
        events = []
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        
        if json_ld_scripts:
            print(f"Found {len(json_ld_scripts)} JSON-LD scripts, extracting structured data...")
            for script in json_ld_scripts:
                try:
                    event_data = json.loads(script.string)
                    if event_data.get('@type') == 'Event':
                        # Extract event information from JSON-LD
                        event = {
                            'Hold Level': '1',
                            'Artist': event_data.get('name', ''),
                            'Type': 'Confirm',
                            'Venue': event_data.get('location', {}).get('name', venue_name),
                            'Event Name': event_data.get('name', ''),
                            'Buyer': '',
                            'Promoter': '',
                            'Event End Time': event_data.get('endDate', ''),
                            'Event Start Time': event_data.get('startDate', ''),
                            'Event Door Time': '',
                            'Event Image URL': event_data.get('image', ''),
                            'Notes': '',
                            'Venue Permalink': event_data.get('url', ''),
                            'Description Text': event_data.get('description', ''),
                            'Description Image': event_data.get('image', ''),
                            'Description Video': '',
                            'Contacts': '',
                            'ID': ''
                        }
                        events.append(event)
                except (json.JSONDecodeError, AttributeError) as e:
                    print(f"Error parsing JSON-LD: {e}")
                    continue
        
        # If no JSON-LD data found, use AI to parse the HTML
        if not events:
            print("No JSON-LD data found, using AI extraction...")
            events = extract_events_with_ai(html_content, venue_name)
        
        if not events:
            return jsonify({'error': 'No events found in HTML. The structure might not be supported.'}), 404
        
        print(f"Found {len(events)} events")
        
        # Use CSV writer to format events properly
        writer = EventCSVWriter(output_path='temp_events.csv')
        
        # Create CSV in memory
        output = io.StringIO()
        
        # Write events using the CSV writer's formatting
        import pandas as pd
        import csv
        
        # Normalize events
        normalized_events = []
        for event in events:
            normalized = {col: event.get(col, '') for col in writer.COLUMNS}
            normalized_events.append(normalized)
        
        # Convert to DataFrame and apply processing
        df = pd.DataFrame(normalized_events)
        
        # Filter out invalid events
        df = df[df['Venue Permalink'].notna() & (df['Venue Permalink'] != '')]
        df = df[df['Event Name'].notna() & (df['Event Name'] != '')]
        
        # Remove duplicates
        df = df.drop_duplicates(subset=['Venue Permalink'], keep='last')
        
        # Calculate door and end times
        df = writer._calculate_times(df)
        
        # Write to string
        df.to_csv(output, index=False, quoting=csv.QUOTE_NONNUMERIC)
        
        # Convert to bytes for sending
        output.seek(0)
        byte_output = io.BytesIO(output.getvalue().encode('utf-8'))
        byte_output.seek(0)
        
        print(f"Returning CSV with {len(df)} events")
        
        return send_file(
            byte_output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{venue_name}_events.csv'
        )
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)