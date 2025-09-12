import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urlencode, parse_qs
import time
import json
import re

def generate_headers():
    """Generate appropriate headers for requests"""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

def get_page_content(url, max_retries=3):
    """Get webpage content with retry mechanism"""
    for attempt in range(max_retries):
        try:
            headers = generate_headers()
            response = requests.get(url, headers=headers, timeout=20, verify=False)
            response.raise_for_status()
            return response.text, True
        except Exception as e:
            print(f"Error fetching {url} (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None, False

def clean_filename(name):
    """Clean string to make it safe for filenames"""
    # Remove invalid characters
    clean_name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace multiple spaces with single space
    clean_name = re.sub(r'\s+', ' ', clean_name)
    # Trim and limit length
    return clean_name.strip()[:100]

def save_html(content, filepath):
    """Save HTML content to file"""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Error saving {filepath}: {e}")
        return False

def create_main_index(batches, base_dir):
    """Create the main index.html file that mimics the original UI"""
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>KD Live - All Batches</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .header { text-align: center; margin-bottom: 30px; }
            .batch-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
            .batch-card { background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
            .batch-image { width: 100%; height: 180px; object-fit: cover; }
            .batch-content { padding: 15px; }
            .batch-title { margin-top: 0; color: #333; }
            .batch-link { display: block; text-align: center; padding: 10px; background: #4CAF50; color: white; text-decoration: none; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>KD Live - All Batches</h1>
            <p>Select a batch to view its contents</p>
        </div>
        <div class="batch-grid">
            {% for batch in batches %}
            <div class="batch-card">
                {% if batch.image %}
                <img src="{{ batch.image }}" alt="{{ batch.name }}" class="batch-image">
                {% endif %}
                <div class="batch-content">
                    <h3 class="batch-title">{{ batch.name }}</h3>
                    <a href="{{ batch.folder_name }}/index.html" class="batch-link">Open Batch</a>
                </div>
            </div>
            {% endfor %}
        </div>
    </body>
    </html>
    """
    
    from jinja2 import Template
    template = Template(html_template)
    
    # Add folder name to each batch
    for batch in batches:
        batch['folder_name'] = clean_filename(batch['name'])
    
    html_content = template.render(batches=batches)
    index_path = os.path.join(base_dir, "index.html")
    save_html(html_content, index_path)
    print(f"Created main index.html at {index_path}")

def extract_batches(main_url):
    """Extract all batches from the main page"""
    print(f"Fetching batches from: {main_url}")
    content, success = get_page_content(main_url)
    if not success:
        return []
    
    soup = BeautifulSoup(content, 'html.parser')
    batches = []
    
    # Find all batch items
    batch_divs = soup.find_all('div', class_='batch-item')
    
    for batch_div in batch_divs:
        try:
            # Extract batch name
            batch_name = batch_div.get('data-batch-name', '')
            if not batch_name:
                title_elem = batch_div.find('h3', class_='batch-title')
                if title_elem:
                    batch_name = title_elem.get_text().strip()
            
            # Extract batch link
            link_elem = batch_div.find('a', class_='study-btn')
            if link_elem and 'href' in link_elem.attrs:
                batch_link = urljoin(main_url, link_elem['href'])
                
                # Extract image if available
                img_elem = batch_div.find('img', class_='batch-image')
                img_src = img_elem['src'] if img_elem and 'src' in img_elem.attrs else ''
                if img_src and not img_src.startswith(('http', '//')):
                    img_src = urljoin(main_url, img_src)
                
                batches.append({
                    'name': batch_name,
                    'link': batch_link,
                    'image': img_src
                })
                
        except Exception as e:
            print(f"Error processing batch: {e}")
            continue
    
    return batches

def extract_chapters(batch_url, batch_name):
    """Extract all chapters from a batch page"""
    print(f"Fetching chapters from: {batch_url}")
    content, success = get_page_content(batch_url)
    if not success:
        return []
    
    soup = BeautifulSoup(content, 'html.parser')
    chapters = []
    
    # Find all chapter cards
    chapter_divs = soup.find_all('div', class_='chapter-card')
    
    for chapter_div in chapter_divs:
        try:
            # Extract chapter name
            title_elem = chapter_div.find('h3', class_='chapter-title')
            chapter_name = title_elem.get_text().strip() if title_elem else "Unknown Chapter"
            
            # Extract chapter link from onclick attribute
            onclick_attr = chapter_div.get('onclick', '')
            chapter_link = None
            
            if 'window.location.href' in onclick_attr:
                # Extract URL from JavaScript
                match = re.search(r"window\.location\.href='([^']+)'", onclick_attr)
                if match:
                    chapter_link = urljoin(batch_url, match.group(1))
            
            # If no link found, try to find a link element
            if not chapter_link:
                link_elem = chapter_div.find('a')
                if link_elem and 'href' in link_elem.attrs:
                    chapter_link = urljoin(batch_url, link_elem['href'])
            
            # Extract stats
            stats = {
                'videos': 0,
                'notes': 0
            }
            
            stats_div = chapter_div.find('div', class_='stats')
            if stats_div:
                stat_items = stats_div.find_all('div', class_='stat-item')
                for item in stat_items:
                    text = item.get_text()
                    if 'Videos' in text:
                        stats['videos'] = int(re.search(r'\d+', text).group() if re.search(r'\d+', text) else 0)
                    elif 'Notes' in text:
                        stats['notes'] = int(re.search(r'\d+', text).group() if re.search(r'\d+', text) else 0)
            
            # Extract image
            img_elem = chapter_div.find('img', class_='chapter-image')
            img_src = img_elem['src'] if img_elem and 'src' in img_elem.attrs else ''
            if img_src and not img_src.startswith(('http', '//')):
                img_src = urljoin(batch_url, img_src)
            
            chapters.append({
                'name': chapter_name,
                'link': chapter_link,
                'image': img_src,
                'stats': stats
            })
            
        except Exception as e:
            print(f"Error processing chapter: {e}")
            continue
    
    return chapters

def create_batch_index(batch, chapters, batch_folder_path):
    """Create index.html for a batch that lists all chapters"""
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{{ batch.name }} - KD Live</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .header { text-align: center; margin-bottom: 30px; }
            .back-btn { display: inline-block; margin-bottom: 20px; padding: 10px 15px; background: #4CAF50; color: white; text-decoration: none; border-radius: 5px; }
            .chapter-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
            .chapter-card { background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
            .chapter-image { width: 100%; height: 180px; object-fit: cover; }
            .chapter-content { padding: 15px; }
            .chapter-title { margin-top: 0; color: #333; }
            .chapter-stats { display: flex; justify-content: space-between; margin: 10px 0; }
            .stat { background: #f0f0f0; padding: 5px 10px; border-radius: 15px; font-size: 14px; }
            .chapter-links { display: flex; gap: 10px; }
            .chapter-link { flex: 1; text-align: center; padding: 10px; background: #4CAF50; color: white; text-decoration: none; border-radius: 5px; }
        </style>
    </head>
    <body>
        <a href="../index.html" class="back-btn">← Back to All Batches</a>
        <div class="header">
            <h1>{{ batch.name }}</h1>
            <p>Select a chapter to view lectures and notes</p>
        </div>
        <div class="chapter-grid">
            {% for chapter in chapters %}
            <div class="chapter-card">
                {% if chapter.image %}
                <img src="{{ chapter.image }}" alt="{{ chapter.name }}" class="chapter-image">
                {% endif %}
                <div class="chapter-content">
                    <h3 class="chapter-title">{{ chapter.name }}</h3>
                    <div class="chapter-stats">
                        <span class="stat">{{ chapter.stats.videos }} Videos</span>
                        <span class="stat">{{ chapter.stats.notes }} Notes</span>
                    </div>
                    <div class="chapter-links">
                        <a href="{{ chapter.folder_name }}/Lectures/index.html" class="chapter-link">Lectures</a>
                        <a href="{{ chapter.folder_name }}/Notes/index.html" class="chapter-link">Notes</a>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </body>
    </html>
    """
    
    from jinja2 import Template
    template = Template(html_template)
    
    # Add folder name to each chapter
    for chapter in chapters:
        chapter['folder_name'] = clean_filename(chapter['name'])
    
    html_content = template.render(batch=batch, chapters=chapters)
    index_path = os.path.join(batch_folder_path, "index.html")
    save_html(html_content, index_path)
    print(f"Created batch index.html at {index_path}")

def create_chapter_views(chapter, chapter_folder_path):
    """Create lectures and notes views for a chapter"""
    # Create Lectures folder and index.html
    lectures_folder = os.path.join(chapter_folder_path, "Lectures")
    os.makedirs(lectures_folder, exist_ok=True)
    
    # Generate lectures URL
    if chapter['link']:
        parsed_url = urlparse(chapter['link'])
        query_params = parse_qs(parsed_url.query)
        query_params['view'] = ['lectures']
        lectures_url = parsed_url._replace(query=urlencode(query_params, doseq=True)).geturl()
        
        # Fetch and save lectures page
        lectures_content, success = get_page_content(lectures_url)
        if success:
            lectures_index_path = os.path.join(lectures_folder, "index.html")
            save_html(lectures_content, lectures_index_path)
            print(f"Created lectures index.html at {lectures_index_path}")
    
    # Create Notes folder and index.html
    notes_folder = os.path.join(chapter_folder_path, "Notes")
    os.makedirs(notes_folder, exist_ok=True)
    
    # Generate notes URL
    if chapter['link']:
        parsed_url = urlparse(chapter['link'])
        query_params = parse_qs(parsed_url.query)
        query_params['view'] = ['notes']
        notes_url = parsed_url._replace(query=urlencode(query_params, doseq=True)).geturl()
        
        # Fetch and save notes page
        notes_content, success = get_page_content(notes_url)
        if success:
            notes_index_path = os.path.join(notes_folder, "index.html")
            save_html(notes_content, notes_index_path)
            print(f"Created notes index.html at {notes_index_path}")

def create_batch_structure(main_url, base_dir):
    """Create the complete folder structure for all batches"""
    batches = extract_batches(main_url)
    
    if not batches:
        print("No batches found!")
        return
    
    print(f"Found {len(batches)} batches")
    
    # Create main index.html
    create_main_index(batches, base_dir)
    
    for batch in batches:
        try:
            # Create batch folder
            batch_folder_name = clean_filename(batch['name'])
            batch_folder_path = os.path.join(base_dir, batch_folder_name)
            os.makedirs(batch_folder_path, exist_ok=True)
            
            print(f"\nProcessing batch: {batch['name']}")
            print(f"Folder: {batch_folder_path}")
            
            # Get batch page content and save as HTML
            batch_content, success = get_page_content(batch['link'])
            if success:
                batch_html_path = os.path.join(batch_folder_path, "batch_details.html")
                save_html(batch_content, batch_html_path)
                print(f"Saved batch HTML: {batch_html_path}")
            
            # Extract and process chapters
            chapters = extract_chapters(batch['link'], batch['name'])
            
            # Create batch index.html
            create_batch_index(batch, chapters, batch_folder_path)
            
            for chapter in chapters:
                # Create chapter subfolder
                chapter_folder_name = clean_filename(chapter['name'])
                chapter_folder_path = os.path.join(batch_folder_path, chapter_folder_name)
                os.makedirs(chapter_folder_path, exist_ok=True)
                
                print(f"  Processing chapter: {chapter['name']}")
                print(f"  Folder: {chapter_folder_path}")
                
                # Create lectures and notes views
                create_chapter_views(chapter, chapter_folder_path)
            
            # Add a small delay to be respectful to the server
            time.sleep(1)
            
        except Exception as e:
            print(f"Error processing batch {batch['name']}: {e}")
            continue

def main():
    # Base URL and directory
    main_url = "https://all.studystark.site/kdlive/"
    base_dir = "/storage/emulated/0/KD_BEST/"
    
    # Create base directory if it doesn't exist
    os.makedirs(base_dir, exist_ok=True)
    
    print("=" * 60)
    print("COMPLETE WEB SCRAPER WITH FOLDER STRUCTURE")
    print("=" * 60)
    print(f"Main URL: {main_url}")
    print(f"Base Directory: {base_dir}")
    print("=" * 60)
    
    # Start the scraping process
    create_batch_structure(main_url, base_dir)
    
    print("\n" + "=" * 60)
    print("SCRAPING COMPLETED!")
    print("=" * 60)

if __name__ == "__main__":
    # Disable SSL warnings for easier debugging
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    main()