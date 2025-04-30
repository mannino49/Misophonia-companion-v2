#!/usr/bin/env python3

"""
Misophonia Research Vector Database Dashboard

This script provides a simple dashboard to monitor the progress of the vector database
processing and embedding generation.
"""

import os
import time
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import argparse
import threading
import curses

# Load environment variables
load_dotenv()

# Path to service account key
SERVICE_ACCOUNT_PATH = "./service-account.json"

# Initialize Firebase
def initialize_firebase():
    try:
        # Initialize Firebase
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        return db
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        return None

# Get database stats
def get_stats(db):
    try:
        # Get document count
        docs = db.collection('research_documents').get()
        doc_count = len(list(docs))
        
        # Get raw chunks count (sample)
        raw_chunks = db.collection('research_chunks_raw').limit(1000).get()
        raw_count = len(list(raw_chunks))
        
        # Get processed chunks count (sample)
        processed_chunks = db.collection('research_chunks').limit(1000).get()
        processed_count = len(list(processed_chunks))
        
        # Calculate progress
        progress = 0
        if raw_count > 0:
            progress = (processed_count / raw_count) * 100
        
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'documents': doc_count,
            'raw_chunks_sample': raw_count,
            'processed_chunks_sample': processed_count,
            'progress': progress
        }
    except Exception as e:
        print(f"Error getting stats: {e}")
        return None

# Display dashboard in terminal
def display_dashboard(stdscr, db, interval=30):
    # Clear screen
    stdscr.clear()
    
    # Set up colors
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
    
    # Hide cursor
    curses.curs_set(0)
    
    # Track stats over time
    stats_history = []
    
    try:
        while True:
            # Get current stats
            stats = get_stats(db)
            if stats:
                stats_history.append(stats)
                
                # Clear screen
                stdscr.clear()
                
                # Display header
                stdscr.addstr(0, 0, "Misophonia Research Vector Database Dashboard", curses.A_BOLD)
                stdscr.addstr(1, 0, "=" * 50)
                
                # Display current stats
                stdscr.addstr(3, 0, f"Last Updated: {stats['timestamp']}")
                stdscr.addstr(4, 0, f"Documents Processed: {stats['documents']}")
                stdscr.addstr(5, 0, f"Raw Chunks (sample): {stats['raw_chunks_sample']}")
                stdscr.addstr(6, 0, f"Processed Chunks (sample): {stats['processed_chunks_sample']}")
                
                # Display progress bar
                progress = stats['progress']
                progress_width = 40
                filled_width = int(progress_width * progress / 100)
                bar = "█" * filled_width + "-" * (progress_width - filled_width)
                
                # Choose color based on progress
                color = curses.color_pair(1)  # Green
                if progress < 25:
                    color = curses.color_pair(3)  # Red
                elif progress < 75:
                    color = curses.color_pair(2)  # Yellow
                
                stdscr.addstr(8, 0, f"Embedding Progress: {progress:.2f}%")
                stdscr.addstr(9, 0, f"[{bar}]")
                
                # Display recent activity
                stdscr.addstr(11, 0, "Recent Activity:", curses.A_BOLD)
                for i, hist in enumerate(reversed(stats_history[-5:])):
                    stdscr.addstr(12 + i, 0, f"{hist['timestamp']}: {hist['processed_chunks_sample']} chunks processed")
                
                # Display instructions
                stdscr.addstr(20, 0, "Press 'q' to quit, 's' to save stats", curses.color_pair(4))
                
                # Refresh screen
                stdscr.refresh()
            
            # Check for key press
            stdscr.nodelay(True)
            key = stdscr.getch()
            if key == ord('q'):
                break
            elif key == ord('s'):
                # Save stats to file
                with open('dashboard_stats.json', 'w') as f:
                    json.dump(stats_history, f, indent=2)
                stdscr.addstr(22, 0, "Stats saved to dashboard_stats.json", curses.color_pair(1))
                stdscr.refresh()
                time.sleep(1)
            
            # Wait for next update
            time.sleep(interval)
    except KeyboardInterrupt:
        pass

# Main function
def main():
    parser = argparse.ArgumentParser(description='Misophonia Research Vector Database Dashboard')
    parser.add_argument('--interval', type=int, default=30, help='Update interval in seconds')
    args = parser.parse_args()
    
    # Initialize Firebase
    db = initialize_firebase()
    if not db:
        print("Failed to initialize Firebase. Exiting.")
        return
    
    # Start dashboard
    curses.wrapper(lambda stdscr: display_dashboard(stdscr, db, args.interval))

if __name__ == "__main__":
    main()
