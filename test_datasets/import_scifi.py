#!/usr/bin/env python
"""
Import Sci-Fi Books dataset from CSV files.
This script parses CSV files for different sci-fi subgenres and creates DigitizedWork entries.

Run from the test_datasets/ directory OR from the project root:
    python test_datasets/import_scifi.py
"""
import os
import sys
import django
from pathlib import Path
import csv
import ast

# Add project root to sys.path so Django can find the ppa package
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ppa.settings")
django.setup()

# Import after django.setup()
from django.db.models.signals import post_save, pre_delete  # noqa: E402
from ppa.archive.models import DigitizedWork, Collection  # noqa: E402

# Disconnect Solr indexing signals to speed up import
post_save.receivers = []
pre_delete.receivers = []

print("🔌 Disconnected Solr indexing signals")

# Path to the dataset — relative to this script's location
DATASET_DIR = Path(__file__).parent / "sci_fi_books"


def parse_genres(genres_str):
    """Parse the genres string which is a dictionary-like string."""
    try:
        # The genres field is a string representation of a dict
        genres_dict = ast.literal_eval(genres_str)
        # Return top 3 genres by count
        sorted_genres = sorted(genres_dict.items(), key=lambda x: x[1], reverse=True)
        return [genre for genre, count in sorted_genres[:3]]
    except (ValueError, SyntaxError):
        return []


def parse_csv_file(csv_file, subgenre):
    """Parse a CSV file and extract book metadata."""
    books = []

    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            book = {}

            # Extract basic fields
            title = row.get("Book_Title", "").strip()
            if not title:
                continue

            book["title"] = title
            book["author"] = row.get("Author_Name", "").strip()

            # Parse year
            year_str = row.get("Year_published", "").strip()
            if year_str and year_str.isdigit():
                book["pub_date"] = int(year_str)

            # Create source_id from title and author
            source_id_base = f"{title}_{book['author']}"[:100]
            book["source_id"] = f"scifi_{subgenre}_{hash(source_id_base) % 1000000}"

            # Store additional metadata
            book["metadata"] = {
                "dataset": "sci_fi_books",
                "subgenre": subgenre,
                "description": row.get("Book_Description", "").strip(),
                "passage": row.get("Book_Description", "").strip(),
                "rating_score": row.get("Rating_score", "").strip(),
                "rating_votes": row.get("Rating_votes", "").strip(),
                "review_number": row.get("Review_number", "").strip(),
                "goodreads_url": row.get("url", "").strip(),
                "language": row.get("Edition_Language", "").strip(),
            }

            # Parse genres
            genres_str = row.get("Genres", "")
            if genres_str:
                genres = parse_genres(genres_str)
                if genres:
                    book["metadata"]["genres"] = genres

            books.append(book)

    return books


def import_books(books, collection_name="Science Fiction Books Collection"):
    """Import books into the database."""

    # Create or get collection
    collection, created = Collection.objects.get_or_create(
        name=collection_name, defaults={"exclude": False}
    )
    print(f"{'✓ Created' if created else '✓ Found'} collection: {collection.name}\n")

    created_count = 0
    updated_count = 0
    skipped_count = 0

    for book_data in books:
        source_id = book_data.pop("source_id")

        try:
            # Get or create the work
            work, created = DigitizedWork.objects.get_or_create(
                source_id=source_id,
                defaults={
                    "title": book_data.get("title", "Untitled"),
                    "author": book_data.get("author", ""),
                    "pub_date": book_data.get("pub_date"),
                    "source": DigitizedWork.OTHER,
                    "metadata": book_data.get("metadata", {}),
                },
            )

            # Add to collection
            work.collections.add(collection)

            if created:
                created_count += 1
                print(f"  ✓ Created: {work.title[:60]}")
                if work.author:
                    print(f"    Author: {work.author[:50]}")
                if work.pub_date:
                    print(f"    Year: {work.pub_date}")
            else:
                updated_count += 1
        except Exception as e:
            skipped_count += 1
            print(f"  ⚠ Skipped: {book_data.get('title', 'Unknown')[:60]} - {str(e)[:50]}")

    return created_count, updated_count, skipped_count


def main():
    print("📚 Sci-Fi Books Dataset Importer")
    print("=" * 50)

    # Check if dataset directory exists
    if not DATASET_DIR.exists():
        print(f"❌ Dataset directory not found: {DATASET_DIR}")
        sys.exit(1)

    # Find all CSV files
    csv_files = list(DATASET_DIR.glob("sf_*.csv"))

    if not csv_files:
        print(f"❌ No CSV files found in: {DATASET_DIR}")
        sys.exit(1)

    print(f"📖 Found {len(csv_files)} CSV files\n")

    total_created = 0
    total_updated = 0
    total_skipped = 0

    # Process each CSV file
    for csv_file in sorted(csv_files):
        # Extract subgenre from filename (e.g., sf_aliens.csv -> aliens)
        subgenre = csv_file.stem.replace("sf_", "")

        print(f"📖 Processing: {csv_file.name} ({subgenre})")

        try:
            books = parse_csv_file(csv_file, subgenre)
            print(f"   Parsed {len(books)} book records")

            # Import to database
            created, updated, skipped = import_books(books, f"Science Fiction - {subgenre.title()}")

            total_created += created
            total_updated += updated
            total_skipped += skipped

            print(f"   Created: {created}, Found: {updated}, Skipped: {skipped}\n")

        except Exception as e:
            print(f"❌ Error processing {csv_file.name}: {e}\n")
            continue

    # Summary
    print("=" * 50)
    print("✅ Import complete!")
    print(f"   Created: {total_created} new records")
    print(f"   Found: {total_updated} existing records")
    print(f"   Skipped: {total_skipped} records")
    print(f"   Total: {DigitizedWork.objects.count()} works in database")

    print("\n📊 Next steps:")
    print("   1. Create a sci-fi adapter configuration:")
    print("      python manage.py adapter create scifi")
    print("   2. Switch to sci-fi adapter in settings:")
    print("      ARCHIVE_ADAPTER = 'scifi'")
    print("   3. Rebuild Solr index:")
    print("      python manage.py index")
    print("   4. View in admin:")
    print("      http://localhost:8000/admin/archive/digitizedwork/")


if __name__ == "__main__":
    main()
