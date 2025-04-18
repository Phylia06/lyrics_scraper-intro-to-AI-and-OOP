from flask import Flask, render_template, request
from playwright.sync_api import Playwright, sync_playwright
from bs4 import BeautifulSoup
import sqlite3
import os
import re
import time
import subprocess

app = Flask(__name__)

# Create or connect to the database
def create_database(db_name="lyrics.db"):
    if not os.path.exists(db_name):
        try:
            conn = sqlite3.connect(db_name)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE Artists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
            """)
            cursor.execute("""
                CREATE TABLE Songs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    artist_id INTEGER NOT NULL,
                    lyrics TEXT NOT NULL,
                    FOREIGN KEY (artist_id) REFERENCES Artists (id)
                )
            """)
            conn.commit()
            print(f"Database '{db_name}' created successfully.")
        except sqlite3.Error as e:
            print(f"Error creating database: {e}")
        finally:
            conn.close()
    else:
        print(f"Database '{db_name}' already exists.")

# Insert lyrics into the database
def insert_lyrics(db_name, artist_name, song_title, lyrics):
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        cursor.execute("INSERT OR IGNORE INTO Artists (name) VALUES (?)", (artist_name,))
        cursor.execute("SELECT id FROM Artists WHERE name = ?", (artist_name,))
        artist_id = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO Songs (title, artist_id, lyrics) 
            VALUES (?, ?, ?)
        """, (song_title, artist_id, lyrics))
        conn.commit()
        print(f"Lyrics for '{song_title}' by '{artist_name}' added to the database.")
    except sqlite3.Error as e:
        print(f"Error inserting lyrics: {e}")
    finally:
        conn.close()

# Fetch lyrics for a specific song
def fetch_lyrics(db_name, artist_name, song_title):
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Songs.lyrics
            FROM Songs
            INNER JOIN Artists ON Songs.artist_id = Artists.id
            WHERE Artists.name = ? AND Songs.title = ?
        """, (artist_name, song_title))
        result = cursor.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        print(f"Error fetching lyrics: {e}")
        return None
    finally:
        conn.close()

# Search for lyrics online
def search_lyrics(playwright: Playwright, artist_name: str, song_title: str):
    base_url = "https://genius.com"
    browser = playwright.chromium.launch(channel="msedge", headless=False)
    context = browser.new_context()
    page = context.new_page()

    try:
        search_query = f"{artist_name} {song_title}".replace(' ', '+')
        search_url = f"{base_url}/search?q={search_query}"
        page.goto(search_url, timeout=0)

        page.wait_for_selector('.column_layout-column_span.column_layout-column_span--primary', timeout=60000)
        top_result = page.query_selector('.column_layout-column_span.column_layout-column_span--primary > div:first-child a')

        if top_result:

            top_result.click()
            page.wait_for_selector('.Lyrics__Container-sc-78fb6627-1', timeout=15000)

            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # Target the lyrics container directly by class name
            lyrics_containers = soup.select('.Lyrics__Container-sc-78fb6627-1')

            # Extract text from all matched containers
            lyrics_list = [container.get_text(separator="\n").strip() for container in lyrics_containers]
            lyrics = "\n\n".join(lyrics_list)


            if lyrics:
                insert_lyrics("lyrics.db", artist_name, song_title, lyrics)
                return lyrics
        else:
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    finally:
        context.close()
        browser.close()

def open_genius_and_select_genre(playwright, genre):
    try:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://genius.com", timeout=60000)

        # Wait and click the main genre container
        page.wait_for_selector('.SquareManySelects__Container-sc-19799187-1', timeout=10000)
        page.click('.SquareManySelects__Container-sc-19799187-1')

        # Wait for genre options to appear
        page.wait_for_selector('.SquareSelectOption__Container-sc-2bb2451-0', timeout=10000)

        # Map genre input to button order
        genre_map = {
            "rap": 0,
            "pop": 1,
            "rnb": 2,
            "rock": 3,
            "country": 4
        }

        index = genre_map.get(genre.lower())
        if index is None:
            return False

        buttons = page.query_selector_all('.SquareSelectOption__Container-sc-2bb2451-0')
        if index < len(buttons):
            buttons[index].click()
            time.sleep(3)  # Allow it to load results
            return True
        else:
            return False
    except Exception as e:
        print(f"Error selecting genre: {e}")
        return False
    finally:
        browser.close()
def explore_genre(playwright, genre="rap"):
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    try:
        page.goto("https://genius.com", timeout=0)

        # Click the dropdown arrow
        arrow = page.query_selector('.SquareSelectTitle__Arrow-sc-c5dbff7d-1.eulDVu')
        if arrow:
            arrow.click()
            page.wait_for_selector('.SquareSelectOption__Container-sc-2bb2451-0.dZxFUu')

            genre_buttons = page.query_selector_all('.SquareSelectOption__Container-sc-2bb2451-0.dZxFUu')
            for button in genre_buttons:
                text = button.inner_text().strip().lower()
                if genre.lower() in text:
                    button.click()
                    print(f"Clicked on genre: {genre}")
                    break
        else:
            print("Dropdown arrow not found.")
        time.sleep(5)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        context.close()
        browser.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    lyrics = None
    message = None
    if request.method == 'POST':
        artist = request.form['artist']
        song = request.form['song']
        lyrics = fetch_lyrics("lyrics.db", artist, song)

        if not lyrics:
            with sync_playwright() as playwright:
                lyrics = search_lyrics(playwright, artist_name=artist, song_title=song)
            if lyrics:
                message = f"Lyrics for '{artist} - {song}' have been fetched and saved!"
            else:
                message = f"Lyrics for '{artist} - {song}' could not be found."

    return render_template('index.html', lyrics=lyrics, message=message)

@app.route('/genre/<name>')
def choose_genre(name):
    with sync_playwright() as playwright:
        song_list = explore_genre(playwright, name)
    return render_template("index.html", selected_genre=name, songs=song_list)

def explore_genre(playwright, genre="rap"):
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    song_titles = []

    try:
        page.goto("https://genius.com", timeout=0)

        # Click the dropdown arrow
        arrow = page.query_selector('.SquareSelectTitle__Arrow-sc-c5dbff7d-1.eulDVu')
        if arrow:
            arrow.click()
            page.wait_for_selector('.SquareSelectOption__Container-sc-2bb2451-0.dZxFUu')

            genre_buttons = page.query_selector_all('.SquareSelectOption__Container-sc-2bb2451-0.dZxFUu')
            for button in genre_buttons:
                text = button.inner_text().strip().lower()
                if genre.lower() in text:
                    button.click()
                    print(f"Clicked on genre: {genre}")
                    break

            time.sleep(5)  # Give time for page to load songs

            # Extract song titles from the genre page
            elements = page.query_selector_all('.ChartSong-desktop__Title-sc-f118d7af-3.iISkTW')
            for el in elements:
                song_titles.append(el.inner_text().strip())

        else:
            print("Dropdown arrow not found.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        context.close()
        browser.close()

    print(f"Extracted songs: {song_titles}")
    return song_titles

if __name__ == "__main__":
    create_database()
    app.run(debug=True)
