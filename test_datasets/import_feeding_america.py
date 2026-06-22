#!/usr/bin/env python
"""
Import Feeding America cookbook dataset from XML metadata.
This script parses the MARC XML records and creates DigitizedWork entries.

Run from the test_datasets/ directory OR from the project root:
    python test_datasets/import_feeding_america.py
"""
import os
import sys
import django
from pathlib import Path
import xml.etree.ElementTree as ET

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
DATASET_DIR = Path(__file__).parent / "historic_cookbooks"
MARC_XML = DATASET_DIR / "cookbook_records.xml"


def parse_marc_xml(xml_file):
    """Parse MARC XML and extract cookbook metadata."""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Define namespace
    ns = {"marc": "http://www.loc.gov/MARC21/slim"}

    cookbooks = []

    for record in root.findall("marc:record", ns):
        cookbook = {}

        # Extract control number (001) as source_id
        control_001 = record.find('marc:controlfield[@tag="001"]', ns)
        if control_001 is not None:
            cookbook["source_id"] = f"feeding_america_{control_001.text}"

        # Extract author (100$a)
        author_field = record.find('marc:datafield[@tag="100"]', ns)
        if author_field is not None:
            author_subfield = author_field.find('marc:subfield[@code="a"]', ns)
            if author_subfield is not None:
                cookbook["author"] = author_subfield.text.strip()

        # Extract title (245$a and 245$b)
        title_field = record.find('marc:datafield[@tag="245"]', ns)
        if title_field is not None:
            title_a = title_field.find('marc:subfield[@code="a"]', ns)
            title_b = title_field.find('marc:subfield[@code="b"]', ns)

            title_parts = []
            if title_a is not None:
                title_parts.append(title_a.text.strip())
            if title_b is not None:
                title_parts.append(title_b.text.strip())

            cookbook["title"] = " ".join(title_parts)

        # Extract publication info (260)
        pub_field = record.find('marc:datafield[@tag="260"]', ns)
        if pub_field is not None:
            # Place (260$a)
            place = pub_field.find('marc:subfield[@code="a"]', ns)
            if place is not None:
                cookbook["pub_place"] = place.text.strip().rstrip(",")

            # Publisher (260$b)
            publisher = pub_field.find('marc:subfield[@code="b"]', ns)
            if publisher is not None:
                cookbook["publisher"] = publisher.text.strip().rstrip(",")

            # Date (260$c)
            date = pub_field.find('marc:subfield[@code="c"]', ns)
            if date is not None:
                date_text = date.text.strip().rstrip(".")
                import re

                year_match = re.search(r"\d{4}", date_text)
                if year_match:
                    cookbook["pub_date"] = int(year_match.group())

        # Extract abstract/summary (520$a) for passage
        summary_field = record.find('marc:datafield[@tag="520"]', ns)
        if summary_field is not None:
            summary_subfield = summary_field.find('marc:subfield[@code="a"]', ns)
            if summary_subfield is not None:
                cookbook["passage"] = summary_subfield.text.strip()

        # Only add if we have at least a title
        if "title" in cookbook and "source_id" in cookbook:
            cookbooks.append(cookbook)

    return cookbooks


def import_cookbooks(cookbooks, collection_name="Feeding America Historical Cookbooks"):
    """Import cookbooks into the database."""

    # Create or get collection
    collection, created = Collection.objects.get_or_create(
        name=collection_name, defaults={"exclude": False}
    )
    print(f"{'✓ Created' if created else '✓ Found'} collection: {collection.name}\n")

    created_count = 0
    updated_count = 0

    for cb_data in cookbooks:
        source_id = cb_data.pop("source_id")

        # Get or create the work
        work, created = DigitizedWork.objects.get_or_create(
            source_id=source_id,
            defaults={
                "title": cb_data.get("title", "Untitled"),
                "author": cb_data.get("author", ""),
                "pub_date": cb_data.get("pub_date"),
                "pub_place": cb_data.get("pub_place", ""),
                "publisher": cb_data.get("publisher", ""),
                "source": DigitizedWork.OTHER,
                "metadata": {
                    "dataset": "feeding_america",
                    "source": "MSU Libraries Special Collections",
                    "passage": cb_data.get("passage", ""),
                },
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
            print(f"  ✓ Found: {work.title[:60]}")

    return created_count, updated_count


def main():
    print("📚 Feeding America Dataset Importer")
    print("=" * 50)

    # Check if dataset exists
    if not MARC_XML.exists():
        print(f"❌ Dataset not found: {MARC_XML}")
        print(f"   Please ensure the dataset is in: {DATASET_DIR}")
        sys.exit(1)

    print(f"📖 Reading MARC XML: {MARC_XML.name}")

    # Parse XML
    try:
        cookbooks = parse_marc_xml(MARC_XML)
        print(f"✓ Parsed {len(cookbooks)} cookbook records\n")
    except Exception as e:
        print(f"❌ Error parsing XML: {e}")
        sys.exit(1)

    # Import to database
    print("💾 Importing to database...")
    created, updated = import_cookbooks(cookbooks)

    # Summary
    print("\n" + "=" * 50)
    print("✅ Import complete!")
    print(f"   Created: {created} new records")
    print(f"   Found: {updated} existing records")
    print(f"   Total: {DigitizedWork.objects.count()} works in database")

    print("\n📊 Next steps:")
    print("   1. Switch to feeding_america adapter in settings:")
    print("      ARCHIVE_ADAPTER = 'feeding_america'")
    print("   2. Run the development server:")
    print("      python manage.py runserver")
    print("   3. View in admin:")
    print("      http://localhost:8000/admin/archive/digitizedwork/")


if __name__ == "__main__":
    main()
