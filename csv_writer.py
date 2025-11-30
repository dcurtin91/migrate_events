"""
CSV writer module to format and save events in the required format.
"""
import csv
import pandas as pd
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime, timedelta
import re


class EventCSVWriter:
    """Handles writing events to CSV in the required format."""
    
    # Column order matching example.csv
    COLUMNS = [
        'Hold Level',
        'Artist',
        'Type',
        'Venue',
        'Event Name',
        'Buyer',
        'Promoter',
        'Event End Time',
        'Event Start Time',
        'Event Door Time',
        'Event Image URL',
        'Notes',
        'Venue Permalink',
        'Description Text',
        'Description Image',
        'Description Video',
        'Contacts',
        'ID'
    ]
    
    def __init__(self, output_path: str = 'Output/events.csv'):
        """
        Initialize the CSV writer.
        
        Args:
            output_path: Path to output CSV file
        """
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _parse_datetime(self, date_string: str) -> Optional[datetime]:
        """
        Parse various date/time formats into a datetime object.
        
        Args:
            date_string: Date string in various formats
            
        Returns:
            datetime object or None if parsing fails
        """
        if not date_string or pd.isna(date_string) or date_string.strip() == '':
            return None
        
        date_string = str(date_string).strip()
        
        # Try various date formats
        formats = [
            '%m/%d/%Y %I:%M %p',  # 03/18/2023 10:45 PM
            '%m/%d/%Y %I:%M %p %Z',  # 03/18/2023 10:45 PM EST
            '%B %d, %Y %I:%M %p',  # November 26, 2025 5:30 pm
            '%b %d, %Y %I:%M %p',  # Nov 26, 2025 5:30 pm
            '%B %d, %Y',  # November 26, 2025
            '%b %d, %Y',  # Nov 26, 2025
            '%m/%d/%Y',  # 11/26/2025
            '%Y-%m-%d %H:%M:%S',  # ISO format
            '%Y-%m-%dT%H:%M:%S',  # ISO format with T
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue
        
        # Try parsing with dateutil (more flexible)
        try:
            from dateutil import parser
            return parser.parse(date_string)
        except (ImportError, ValueError, TypeError):
            pass
        
        # Try regex-based parsing for formats like "Nov 26, 2025 5:30 pm"
        month_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        # Pattern: "Nov 26, 2025 5:30 pm" or "November 26, 2025 5:30 pm"
        pattern = r'(\w+)\s+(\d{1,2}),?\s+(\d{4})(?:\s+(\d{1,2}):(\d{2})\s*(am|pm))?'
        match = re.search(pattern, date_string, re.IGNORECASE)
        if match:
            month_str, day, year, hour, minute, am_pm = match.groups()
            month = month_map.get(month_str[:3].lower())
            if month:
                day = int(day)
                year = int(year)
                if hour and minute:
                    hour = int(hour)
                    minute = int(minute)
                    if am_pm and am_pm.lower() == 'pm' and hour != 12:
                        hour += 12
                    elif am_pm and am_pm.lower() == 'am' and hour == 12:
                        hour = 0
                    return datetime(year, month, day, hour, minute)
                else:
                    return datetime(year, month, day)
        
        return None
    
    def _format_datetime(self, dt: datetime) -> str:
        """
        Format datetime as MM/DD/YYYY HH:MM PM EST
        Example: 03/18/2023 10:45 PM EST
        
        Args:
            dt: datetime object
            
        Returns:
            Formatted string
        """
        if not dt:
            return ''
        # Format: MM/DD/YYYY HH:MM PM EST
        # Use %#I on Windows or %-I on Unix to remove leading zero from hour
        # But to be cross-platform, we'll format manually
        month = dt.month
        day = dt.day
        year = dt.year
        hour = dt.hour
        minute = dt.minute
        
        # Convert to 12-hour format
        if hour == 0:
            hour_12 = 12
            am_pm = 'AM'
        elif hour < 12:
            hour_12 = hour
            am_pm = 'AM'
        elif hour == 12:
            hour_12 = 12
            am_pm = 'PM'
        else:
            hour_12 = hour - 12
            am_pm = 'PM'
        
        return f"{month:02d}/{day:02d}/{year} {hour_12}:{minute:02d} {am_pm} EST"
    
    def _extract_time_from_text(self, text: str) -> Optional[datetime]:
        """
        Extract datetime from text that might contain "Doors: X // Show: Y" format.
        
        Args:
            text: Text that might contain time information
            
        Returns:
            datetime object or None
        """
        if not text or pd.isna(text):
            return None
        
        text = str(text).strip()
        
        # Try to parse the full text first
        dt = self._parse_datetime(text)
        if dt:
            return dt
        
        # Look for "Show: X" or "Show: X pm" pattern
        show_pattern = re.compile(r'Show:\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)', re.I)
        show_match = show_pattern.search(text)
        
        # Look for "Doors: X" pattern
        doors_pattern = re.compile(r'Doors:\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)', re.I)
        doors_match = doors_pattern.search(text)
        
        # Extract date from the text
        date_pattern = re.compile(r'(\w+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', re.I)
        date_match = date_pattern.search(text)
        
        # If we have a date, try to combine with time
        if date_match:
            date_str = date_match.group(1)
            date_dt = self._parse_datetime(date_str)
            
            if date_dt and show_match:
                # Extract show time
                show_time = show_match.group(1).strip()
                # Parse the time
                time_pattern = re.compile(r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM|am|pm)?', re.I)
                time_match = time_pattern.search(show_time)
                
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2)) if time_match.group(2) else 0
                    am_pm = time_match.group(3)
                    
                    # Convert to 24-hour
                    if am_pm:
                        if am_pm.upper() == 'PM' and hour != 12:
                            hour += 12
                        elif am_pm.upper() == 'AM' and hour == 12:
                            hour = 0
                    elif hour < 12:  # Assume PM if no AM/PM specified and hour < 12
                        hour += 12
                    
                    return datetime(date_dt.year, date_dt.month, date_dt.day, hour, minute)
        
        # If no date found, try to parse just the time and use today's date
        # (This is a fallback - ideally we should have a date)
        if show_match:
            show_time = show_match.group(1).strip()
            time_pattern = re.compile(r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM|am|pm)?', re.I)
            time_match = time_pattern.search(show_time)
            
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                am_pm = time_match.group(3)
                
                if am_pm:
                    if am_pm.upper() == 'PM' and hour != 12:
                        hour += 12
                    elif am_pm.upper() == 'AM' and hour == 12:
                        hour = 0
                elif hour < 12:
                    hour += 12
                
                # Use today as fallback (not ideal, but better than nothing)
                today = datetime.now()
                return datetime(today.year, today.month, today.day, hour, minute)
        
        return None
    
    def _calculate_times(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate door time and end time based on start time.
        - If "Doors:" is found in the text, extract it for door time
        - Otherwise, door time = Start time - 1 hour
        - End time = Start time + 3 hours (always)
        
        Args:
            df: DataFrame with events
            
        Returns:
            DataFrame with calculated times
        """
        df = df.copy()
        
        for idx, row in df.iterrows():
            start_time_str = row.get('Event Start Time', '')
            door_time_str = row.get('Event Door Time', '')
            
            if pd.isna(start_time_str) or start_time_str == '':
                continue
            
            # Extract start time from text
            start_dt = self._extract_time_from_text(start_time_str)
            
            if not start_dt:
                # Try parsing the raw string
                start_dt = self._parse_datetime(start_time_str)
            
            if start_dt:
                # Check if door time is already specified in the start time text
                door_dt = None
                if door_time_str and not pd.isna(door_time_str) and door_time_str.strip():
                    door_dt = self._parse_datetime(door_time_str)
                
                # If no door time found, try to extract from start time text
                if not door_dt:
                    doors_pattern = re.compile(r'Doors:\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)', re.I)
                    doors_match = doors_pattern.search(str(start_time_str))
                    
                    if doors_match:
                        # Extract door time
                        door_time_text = doors_match.group(1).strip()
                        
                        # Get date from start_dt (we already have it parsed)
                        if start_dt:
                            # Parse door time
                            time_pattern = re.compile(r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM|am|pm)?', re.I)
                            time_match = time_pattern.search(door_time_text)
                            
                            if time_match:
                                hour = int(time_match.group(1))
                                minute = int(time_match.group(2)) if time_match.group(2) else 0
                                am_pm = time_match.group(3)
                                
                                if am_pm:
                                    if am_pm.upper() == 'PM' and hour != 12:
                                        hour += 12
                                    elif am_pm.upper() == 'AM' and hour == 12:
                                        hour = 0
                                elif hour < 12:
                                    hour += 12
                                
                                # Use the same date as start time
                                door_dt = datetime(start_dt.year, start_dt.month, start_dt.day, hour, minute)
                
                # If still no door time, calculate as 1 hour before start
                if not door_dt:
                    door_dt = start_dt - timedelta(hours=1)
                
                # Calculate end time (always 3 hours after start)
                end_dt = start_dt + timedelta(hours=3)
                
                # Format all three times
                df.at[idx, 'Event Start Time'] = self._format_datetime(start_dt)
                df.at[idx, 'Event Door Time'] = self._format_datetime(door_dt)
                df.at[idx, 'Event End Time'] = self._format_datetime(end_dt)
        
        return df
    
    def write_events(self, events: List[Dict], append: bool = False):
        """
        Write events to CSV file.
        
        Args:
            events: List of event dictionaries
            append: If True, append to existing file; if False, overwrite
        """
        if not events:
            print("No events to write.")
            return
        
        # Ensure all events have all required columns
        normalized_events = []
        for event in events:
            normalized = {col: event.get(col, '') for col in self.COLUMNS}
            normalized_events.append(normalized)
        
        # Convert to DataFrame for deduplication
        df = pd.DataFrame(normalized_events)
        
        # Filter out invalid events (empty Venue Permalink or empty Event Name)
        initial_count = len(df)
        df = df[df['Venue Permalink'].notna() & (df['Venue Permalink'] != '')]
        df = df[df['Event Name'].notna() & (df['Event Name'] != '')]
        
        if len(df) < initial_count:
            print(f"Filtered out {initial_count - len(df)} invalid events (empty Venue Permalink or Event Name)")
        
        # Remove duplicates based on Venue Permalink (one row per unique permalink)
        before_dedup = len(df)
        df = df.drop_duplicates(subset=['Venue Permalink'], keep='last')
        
        if len(df) < before_dedup:
            print(f"Removed {before_dedup - len(df)} duplicate events (same Venue Permalink)")
        
        # Calculate door time and end time based on start time
        df = self._calculate_times(df)
        
        # Check if file exists and has data
        file_exists = self.output_path.exists() and self.output_path.stat().st_size > 0
        
        if append and file_exists:
            # Read existing data
            try:
                existing_df = pd.read_csv(self.output_path)
                # Filter existing data too
                existing_df = existing_df[existing_df['Venue Permalink'].notna() & (existing_df['Venue Permalink'] != '')]
                existing_df = existing_df[existing_df['Event Name'].notna() & (existing_df['Event Name'] != '')]
                
                # Combine and deduplicate
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['Venue Permalink'], keep='last')
                
                # Calculate times for combined dataframe
                combined_df = self._calculate_times(combined_df)
                
                combined_df.to_csv(self.output_path, index=False, quoting=csv.QUOTE_NONNUMERIC)
                print(f"Appended {len(df)} events to {self.output_path} (total: {len(combined_df)} unique events)")
            except Exception as e:
                print(f"Error appending to existing file: {e}")
                # Fallback to overwrite
                df.to_csv(self.output_path, index=False, quoting=csv.QUOTE_NONNUMERIC)
                print(f"Created new file with {len(df)} events at {self.output_path}")
        else:
            # Write new file
            df.to_csv(self.output_path, index=False, quoting=csv.QUOTE_NONNUMERIC)
            print(f"Wrote {len(df)} unique events to {self.output_path}")
    
    def merge_with_existing(self, events: List[Dict]):
        """
        Merge new events with existing CSV, updating duplicates.
        
        Args:
            events: List of event dictionaries to merge
        """
        normalized_events = []
        for event in events:
            normalized = {col: event.get(col, '') for col in self.COLUMNS}
            normalized_events.append(normalized)
        
        # Convert to DataFrame
        new_df = pd.DataFrame(normalized_events)
        
        # Filter invalid events
        new_df = new_df[new_df['Venue Permalink'].notna() & (new_df['Venue Permalink'] != '')]
        new_df = new_df[new_df['Event Name'].notna() & (new_df['Event Name'] != '')]
        
        # Calculate times
        new_df = self._calculate_times(new_df)
        
        if self.output_path.exists():
            try:
                existing_df = pd.read_csv(self.output_path)
                # Filter existing data
                existing_df = existing_df[existing_df['Venue Permalink'].notna() & (existing_df['Venue Permalink'] != '')]
                existing_df = existing_df[existing_df['Event Name'].notna() & (existing_df['Event Name'] != '')]
                
                # Merge and deduplicate on Venue Permalink
                merged_df = pd.concat([existing_df, new_df], ignore_index=True)
                merged_df = merged_df.drop_duplicates(subset=['Venue Permalink'], keep='last')
                
                # Calculate times for merged dataframe
                merged_df = self._calculate_times(merged_df)
                
                merged_df.to_csv(self.output_path, index=False, quoting=csv.QUOTE_NONNUMERIC)
                print(f"Merged {len(new_df)} events into {self.output_path} (total: {len(merged_df)} unique events)")
            except Exception as e:
                print(f"Error merging: {e}. Creating new file.")
                new_df = new_df.drop_duplicates(subset=['Venue Permalink'], keep='last')
                new_df.to_csv(self.output_path, index=False, quoting=csv.QUOTE_NONNUMERIC)
        else:
            new_df = new_df.drop_duplicates(subset=['Venue Permalink'], keep='last')
            new_df.to_csv(self.output_path, index=False, quoting=csv.QUOTE_NONNUMERIC)
            print(f"Created new file with {len(new_df)} unique events at {self.output_path}")

