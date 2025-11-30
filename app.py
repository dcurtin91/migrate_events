from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import io
from scraper import GenericScraper
from csv_writer import EventCSVWriter

app = Flask(__name__)
CORS(app)

# HTML template embedded in Flask
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>Event Scraper</title>
  <style>
    body { font-family: Arial; max-width: 600px; margin: 40px auto; padding: 20px; }
    input, button { padding: 10px; font-size: 16px; width: 100%; box-sizing: border-box; }
    button { margin-top: 10px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 4px; }
    button:hover { background: #0056b3; }
    button:disabled { background: #ccc; cursor: not-allowed; }
    #status { margin-top: 15px; padding: 10px; border-radius: 4px; }
    .success { background: #d4edda; color: #155724; }
    .error { background: #f8d7da; color: #721c24; }
    .loading { background: #fff3cd; color: #856404; }
  </style>
</head>

<body>
  <h2>🎵 Event Scraper</h2>
  <input id="url" placeholder="https://hideoutchicago.com/events/" />
  <button onclick="scrape()" id="scrapeBtn">Scrape Events</button>

  <div id="status"></div>

  <script>
    async function scrape() {
      const url = document.getElementById("url").value.trim();
      const statusDiv = document.getElementById("status");
      const btn = document.getElementById("scrapeBtn");
      
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
    
    // Allow Enter key to trigger scrape
    document.getElementById("url").addEventListener("keypress", function(e) {
      if (e.key === "Enter") scrape();
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
        events = scraper.scrape()
        
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

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)